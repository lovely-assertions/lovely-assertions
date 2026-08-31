---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
  - "benchmarks/**/*.py"
---

# Comments & docstrings — self-contained, contract first, why not what

Everything in `src/` ships. A docstring here is what an IDE shows on hover and
what a reader consults instead of opening the body, so it is written for a
stranger who has **only the installed package** — no repository, no design notes,
no conversation. `scripts/` and `benchmarks/` ship nowhere, and their only reader
has the repository open: those two may name the test that asserts what they
measure or the page they generate. Everything else here holds for all three.

## Hard rules

1. **Never cite anything a reader of the wheel cannot open.** No spec sections,
   no page under `docs/`, no numbered decisions, no milestones, no divergence
   identifiers, no test-file names, no "as decided earlier". If deleting a
   citation would lose real information, write the one or two sentences of the
   idea in its place. This applies to `# noqa` justifications too. A name the
   same wheel contains is not a citation: a `:func:` or `:meth:` role pointing at
   another module of the package is a link the reader can follow, and the one the
   `__tracebackhide__` block in every module uses. `test_source_conventions.py`
   tokenizes every comment and docstring under `src/` and rejects the spellings it
   knows, but that list is finite — it catches a `docs/<page>.md` and not the
   `docs/<section>/<page>.md` nearly every page is — so the rule is wider than its
   guard, and it does not look at `scripts/` or `benchmarks/` at all.
2. **No development history.** A comment states what is true now, never what the
   code used to be, what was tried, or when something changed. That record is the
   commit log's job, and a docstring that keeps it goes stale silently. Nothing
   checks this and nothing will: every regex for it — "used to", "no longer",
   "previously" — also matches ordinary English about values, so a guard would
   cost more in contorted wording than it saves. It is a review rule. A file move
   is where it goes wrong: the sentence explaining that something *used to* live
   somewhere else is history, however fresh.
3. **Explain why, not what.** Comments carry constraints, invariants, costs and
   non-obvious causes — "read once per comparison, not once per node, because the
   cache token can change mid-walk". Never paraphrase the next line. Delete
   narration on sight.
4. **English only**, and no volatile numbers (counts, timings, benchmark
   figures). State the contract; the number drifts, the contract does not.

## The docstring bar

A public method documents its **contract**: what it asserts, what it accepts,
what it returns for chaining, what it raises, and the degenerate cases — empty
input, `None`, NaN, an unhashable element, a subject that defines `__eq__`
strangely. A reader must be able to call it correctly without opening the body.

- **First line is a sentence, imperative, and complete on its own.** It is the
  only part of the docstring the generated reference carries, so it cannot start
  mid-thought or depend on the paragraph below it.
- **Docstrings are reStructuredText, and that first line is translated.**
  `scripts/generate_reference.py` rewrites ``literals`` as Markdown code spans,
  the `:meth:`/`:attr:`/`:class:`/`:func:`/`:data:`/`:exc:` roles as code spans
  naming their target, and ` -- ` as an em dash. Anything else in that line
  passes through raw into the published reference.
- **Assertions start with "Assert ...", and the first line ends with a full
  stop** — `"""Assert the subject starts with ``prefix``."""` — so the catalogue
  reads as a list of claims. A guard enforces both, but it recognises an
  assertion by whether the body itself calls `_fail` or `_fail_narrowing`, so one
  that delegates to another assertion is held to the rule by review alone.
- **A `>>>` example is executed**, against the module's own globals plus
  everything the package exports — so an example may use any public name without
  importing it, and one on a private helper may use its neighbours.
  `IGNORE_EXCEPTION_DETAIL` is deliberately off: the text of a failure message is
  the thing this library is for. An example that cannot run, because it needs a
  class the reader is meant to supply, is marked `# doctest: +SKIP`.
- **When two assertions are close, the docstring says which to reach for.** The
  distinction between neighbours is the most common reason to open one at all.
- A private helper gets a docstring when its name does not already answer "what
  does this return, and when is it wrong to call it". Not before.

## Module and inline comments

- **A package's `__init__.py` and a leaf module owe different docstrings.** The
  `__init__.py` is the family's orientation page: the rules that hold across every
  file beneath it, the import-time cost the family is careful to avoid, the traps
  that cut across seams. A leaf states the one concern it owns and the design
  tension inside it, and does not restate the family's rules. Both say what they
  deliberately do not own.
- **Name a module by its import path, never by a filename** — `_core`, or
  `lovely_assertions._diff`, not `_core.py`. A module that becomes a package
  turns every filename in prose into a dangling pointer.
  `tests/test_internal_docs.py` catches the ones that name a path; it cannot
  catch a sentence that is merely no longer true.
- **`#:` documents a value** — a module-level constant, a class-level annotation
  or slot declaration, an attribute set in `__init__`. It is where Sphinx looks
  and a plain `#` comment is not, and it is also where the reference generator
  looks: for a constant the reference lists, it reads the block above the
  *annotated* module-level assignment and publishes its first sentence as that
  name's description. So that first sentence is user-facing prose held to the
  same stands-alone bar as a docstring's first line, and dropping the annotation
  stops the generator rather than quietly dropping the row. A group of related
  constants shares one block above the first of them rather than repeating it.
- An inline comment sits **above** the line it explains. It trails only as part of
  a machine-read directive — `# noqa`, `# type: ignore`, `# pyright: ignore`,
  `# pragma: no cover`, the release-please version marker — carrying whatever
  reason that directive's own syntax has room for. Prose that is not attached to
  a directive goes above.
- **Every `# noqa` carries a reason in plain language**, not a pointer to where
  the reason is written down: in parentheses after the rule code, or in a comment
  on the line above when the line already carries a second directive and has no
  room. The guard accepts either placement and nothing else.
