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
no conversation.

## Hard rules

1. **Never cite anything the reader cannot see.** No spec sections, no
   `docs/*.md` paths, no numbered decisions, no milestones, no divergence
   identifiers, no test-file names, no "as decided earlier". If deleting a
   citation would lose real information, write the one or two sentences of the
   idea in its place. This applies to `# noqa` justifications too.
2. **No development history.** A comment states what is true now, never what the
   code used to be, what was tried, or when something changed. That record is the
   commit log's job, and a docstring that keeps it goes stale silently.
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

- **First line is a sentence, imperative, and complete on its own.** The
  generated reference quotes it verbatim as the method's description, so it
  cannot start mid-thought or depend on the paragraph below it.
- **Assertions start with "Assert ..."** — `"""Assert the subject starts with
  ``prefix``."""` — so the catalogue reads as a list of claims.
- **When two assertions are close, the docstring says which to reach for.** The
  distinction between neighbours is the most common reason to open one at all.
- A private helper gets a docstring when its name does not already answer "what
  does this return, and when is it wrong to call it". Not before.

## Module and inline comments

- **Module docstrings state what the module owns and what it deliberately does
  not**, plus any import-time cost it is careful to avoid.
- **`#:` documents a module-level constant** — editors pick an attribute
  docstring up on hover, and a plain `#` comment they ignore. A group of related
  constants shares one block above the first of them rather than repeating it.
- An inline comment sits **above** the line it explains, not trailing it, unless
  it is a `# noqa` code or a two-word unit.
- **Every `# noqa` carries a reason in plain language**, not a pointer to where
  the reason is written down.
