---
paths:
  - "docs/**/*.md"
  - "README.md"
  - "tests/test_documentation.py"
  - "tests/test_packaging.py"
  - "scripts/generate_reference.py"
---

# Documentation — executable, and routed by reader

**The documentation is executable, and that is the point.** Every `python` block
on every hand-written page is run by `tests/test_documentation.py`, and the
`text` block immediately after one is compared against what it actually
produced: the failure message if it raised, otherwise what it printed. A page
cannot drift from the library without failing the build. Hand-written means the
tree under `docs/` *and* the repository's `README.md` — it is the wheel's long
description, it was the one page nothing executed, and it drifted. The generated
`reference/assertions.md` is the single exclusion, because its generator already
runs every example it quotes.

So: **never quote a message you have not run.** Not one you remember, not one you
derived from reading the source, not one that is "obviously" what it prints.
Write the block, run the page, paste what came back.

## How a page runs

- Blocks share the page's namespace in document order, so a later block can use
  a name an earlier one bound.
- **Each page runs alone, in its own interpreter, from a real file on disk.** The
  separate process is why a page that registers a formatter does not quietly
  change the messages every page after it quotes — a failure would otherwise land
  on whichever page came next rather than on the page with the mistake in it. The
  real file is why the messages are the real ones: subject naming reads the
  caller's source through `linecache`, and code handed to `exec` has no source,
  so every message would fall back to `the value`.
- The working directory is **empty**, which is why a filesystem example can
  create the files it needs, and why one can assert about a file that is not
  there. Nothing volatile may appear in a quoted result: a temporary path, a
  wall-clock date, a set's iteration order, a memory address.
- `bash` and `console` blocks are never executed.
- A block that genuinely cannot run is marked `<!-- docs-test: skip - why -->` on
  the line above the fence — the last non-blank one, and only that one — with a
  real reason, which the directive's own syntax requires. A block that is
  *supposed* to fail a type checker is marked
  `<!-- docs-test: expect-error - why -->`.
- **The two are not flavours of one thing.** A `skip` block is left out of the
  execution, out of the type-check and out of the page's namespace, so a later
  block cannot use a name it bound. An `expect-error` block runs normally and its
  quoted result is compared like any other's; only its lines are permitted to
  fail the checker.
- Neither directive is collected into a list, and nothing pins how many there
  are. Staleness is caught only in part: a `skip` on a block that was never going
  to run anyway is refused, and an `expect-error` is refused once *nothing* the
  page permits still errors. A `skip` on a `python` block that would now run
  clean, or one of two `expect-error` blocks on the same page going quiet, is
  invisible. Deleting an exemption once its reason expires is discipline here,
  not a guard.

The harness also refuses: a snippet that fails without quoting the failure, a
fence hidden inside a blockquote (where the fence regex would not see it), an
internal link that no longer resolves — anchors included, checked against the
headings of the page they point into — and an example pyright rejects. Only
pyright reads the pages, in strict mode less the suppressions that stitching a
page's blocks into one module requires, and pinned to the floor of the supported
Python range: mypy and the newer row of the matrix never see them. And only an
`AssertionFailure` is caught per block — any other exception aborts the page and
is reported as a page that does not run, rather than as the block that failed. If
you find a way to write a broken page that the harness accepts, that is a harness
bug and it gets a test.

## Structure — four parts, routed by reader

`docs/README.md` routes; start there and keep it accurate. Its links are checked
for resolution, never for coverage, so a page nothing links to ships in silence:
adding a page means adding its route by hand.

- **`getting-started/`** — a linear introduction, read once, in order.
- **`guides/`** — task-oriented, one per subject or per feature. A reader arrives
  here already knowing what they want to assert.
- **`reference/`** — `reference/assertions.md` is **generated**: never hand-edit
  it, run `uv run python scripts/generate_reference.py`. The
  `reference/README.md` beside it is hand-written and runs under the harness like
  every other page. The generator reads the *first* line of each method
  docstring — a summary that runs on past it is dropped without comment — and the
  `# -- group name ---` banners out of the source, so those banners are structure
  rather than decoration. A subject's class body holds only what that class
  declares, so what it gains from the mixins it is assembled from reaches the
  catalogue through `SHARED_BASES` in the generator, which also supplies the
  group title for a mixin file carrying no banner of its own. A mixin nobody
  registers there contributes nothing to the page; `tests/test_packaging.py`
  catches that by walking the subject's MRO, and it is also where the check that
  the checked-in file has not drifted lives. Name a mixin class `*Assertions` or
  `*Base` — that suffix is the whole of how the generator recognises a seam and
  keeps it out of the printed `class ...` line, and one named otherwise leaks a
  private class into the reference.
- **`concepts/`** — why it is built this way. The design goals, dispatch,
  messages, performance, typing divergences.

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
