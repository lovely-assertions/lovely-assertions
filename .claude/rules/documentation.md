---
paths:
  - "docs/**/*.md"
  - "README.md"
  - "tests/test_documentation.py"
  - "scripts/generate_reference.py"
---

# Documentation — executable, and routed by reader

**The documentation is executable, and that is the point.** Every `python` block
under `docs/` is run by `tests/test_documentation.py`, and every `text` block
that follows one is compared against what it actually produced — the failure
message if it raised, otherwise what it printed. A page cannot drift from the
library without failing the build.

So: **never quote a message you have not run.** Not one you remember, not one you
derived from reading the source, not one that is "obviously" what it prints.
Write the block, run the page, paste what came back.

## How a page runs

- Blocks share the page's namespace in document order, so a later block can use
  a name an earlier one bound.
- Pages run in an **empty directory**, which is why a filesystem example can
  create the files it needs. Nothing volatile may appear in a quoted result: a
  temporary path, a wall-clock date, a set's iteration order, a memory address.
- `bash` and `console` blocks are never executed.
- A block that genuinely cannot run is marked `<!-- docs-test: skip - why -->` on
  the line above the fence, with a real reason. A block that is *supposed* to
  fail a type checker is marked `<!-- docs-test: expect-error - why -->`.
- Both exemption lists are pinned by count, so a new entry cannot join them
  unnoticed, and a stale one fails.

The harness also refuses: a snippet that fails without quoting the failure, a
fence hidden inside a blockquote (where the fence regex would not see it), an
internal link that no longer resolves, and an example that does not type-check
under both checkers. If you find a way to write a broken page that the harness
accepts, that is a harness bug and it gets a test.

## Structure — four parts, routed by reader

`docs/README.md` routes; start there and keep it accurate.

- **`getting-started/`** — a linear introduction, read once, in order.
- **`guides/`** — task-oriented, one per subject or per feature. A reader arrives
  here already knowing what they want to assert.
- **`reference/assertions.md`** — **generated**. Never hand-edit it; run
  `uv run python scripts/generate_reference.py`. It reads the method docstrings
  and the `# -- group name ---` banners out of the source, so those banners are
  structure rather than decoration. A test fails if the checked-in file drifted.
- **`concepts/`** — why it is built this way. Dispatch, messages, performance,
  typing divergences.

## Prose

**Accessible to a junior reader and honest with a senior one**, in the same page,
without a "beginners" ghetto: state the thing plainly first, then the constraint
that makes it interesting. Neither audience is served by hedging.

**Say the limitation out loud.** The caller's variable does not narrow; a `Mock`
defeats static dispatch; an unordered comparison has a pairing budget and raises
when it is exceeded. A page that implies more than the library delivers costs a
reader an afternoon, and this project's whole claim is that it does not do that.

**English only.** No volatile numbers — assertion counts, timings, file counts —
in prose that nothing regenerates; state the contract instead.

**When two things are close, say which to reach for.** The distinction between
neighbours is the most common reason someone opened the page at all.
