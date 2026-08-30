# CLAUDE.md — lovely-assertions

Guidance for anyone changing this repo: the cross-cutting invariants and the
commands you cannot guess by reading the code. Per-area detail loads on demand
from `.claude/rules/` when you touch matching files.

<!--
Maintainer note (stripped before this file enters context — costs no tokens):
Keep this under ~200 lines and free of anything inferable from the source. It
loads in full every session, and length costs adherence. Per-area conventions
belong in .claude/rules/, which is path-scoped and loads only when relevant.
-->

## What this is

A fluent assertion library for Python tests — `expect(value).is_equal_to(...)`.
Its competitor is pytest's own `assert` rewriting, which already prints a decent
diff, so this library has to win elsewhere. It claims exactly three things:

- **Typed discoverability** — `expect(x).` offers only the assertions valid for
  the type of `x`. A `str` subject has no `is_positive`.
- **Real narrowing** — `expect(raw).is_not_none().subject` is a `str` to both
  checkers, not an `object`.
- **Failure messages that explain** — a sentence naming the subject, what was
  expected and what was actually there. Not a diff.

Break any of the three and the package has no reason to exist.

## Invariants — hold these in every session

These are what a change most often breaks, and none is visible from a single file.

- **Zero runtime dependencies, permanently. Python ≥ 3.13.** `re`, `difflib`,
  `ast`, `linecache`, `dataclasses` and `uuid` are imported *inside* the branch
  that needs them, which is always a failure path. The subjects that assert on
  `datetime`, `enum` and `pathlib` values are typed against those modules under
  `TYPE_CHECKING` and dispatched by name, so `import lovely_assertions` pulls in
  none of the three. `datetime` and `pathlib` are then never imported at all;
  `enum` is, lazily, by the flag assertions and by enum-by-name equivalence,
  which cannot do their work without it.
- **A passing assertion is a comparison plus `return self`.** No frame
  inspection, no `ContextVar` read, no allocation, no message built, `because`
  never evaluated. An f-string message outside the failure branch is a defect,
  not a style preference — and a message passed as a *helper argument* is built
  on the happy path too.
- **Both checkers, both strict, zero errors.** pyright is the reference; mypy is
  matrixed alongside it. A typing limitation is documented and lived with, never
  worked around by dropping an overload or widening a return to `Any`.
- **The failure message is the product.** An assertion whose message says less
  than the comparison it replaces is worse than no assertion at all.
- **`AssertionFailure` derives from `AssertionError`**, so pytest and unittest
  count it as a failure rather than an error.
- **English only** — code, comments, docstrings, test names, commit messages,
  and every page under `docs/`.
- **The documentation is executable.** Every `python` block under `docs/` is run
  by `tests/test_documentation.py`, and every `text` block after one is compared
  against what it actually produced. A page cannot drift from the library
  without failing the build.

## Architecture

`expect()` is a typed dispatcher, not a class. Its `@overload` chain and the
runtime branch order in `_subjects.py` are one table written twice; change one
and change the other in the same edit, or the checker and the runtime disagree
about which subject a value gets.

Subjects form a single-inheritance chain rooted at `Expect[T]` (`_core.py`):
every assertion is a comparison followed by `return self` or `self._fail(...)`.
`_fail` is the only place a failure is reported, which is what makes soft scopes,
subject naming and `because` work everywhere without per-assertion wiring.

Module layout is flat and one-way: `_core` knows nothing about its subclasses,
subject modules import from `_core` and the shared helpers (`_reflection`,
`_formatting`, `_diff`, `_equivalence`, `_text`), and `_subjects` is the only
module that assembles them. Don't add an import that points back up the chain.

## Commands

Everything runs through `uv`, with the interpreter pinned explicitly.

- `uv sync` — install the package plus the dev group.
- `uv run pytest` — the whole suite, including the harness that shells out to the
  real pyright and mypy over `typing_tests/`.
- `uv run ruff format . && uv run ruff check .` — format, then lint.
- `uv run pyright` — must stay at zero errors. `--pythonversion 3.14` for the other row
  of the matrix.
- `uv run mypy` — same bar.
- `uv run pyright --verifytypes lovely_assertions --ignoreexternal` — the
  `py.typed` completeness score; `--ignoreexternal` is not optional, since
  typeshed's own gaps otherwise dominate the number.
- `uv run pytest --cov` — the same suite, traced, held to the floor in
  `[tool.coverage.report]`. Not a substitute for the untraced run: several
  performance invariants read a measurement that cannot be taken while
  `sys.settrace` is active and skip themselves. CI runs both.
- `uv run python -m benchmarks` — timings, printed for a human, never asserted.
- `uv sync --group fuzz --python 3.13 && uv run python -m fuzz.fuzz_hostile
  -max_total_time=60` — one fuzzing target, Linux x86_64 only. Atheris ships no
  other wheels, which is why the group is opt-in and why everything that decides
  anything lives in `fuzz/properties.py`: `tests/test_fuzzing.py` runs the same
  properties over a seeded corpus on every platform, in the ordinary suite.
- `uv run python scripts/generate_reference.py` — regenerates
  `docs/reference/assertions.md` from the source. Run it after touching any
  assertion signature or docstring first line; a test fails if the checked-in
  file has drifted.
- `uvx zizmor==1.29.0 --persona regular .` — the security audit CI runs, and it must
  stay clean. The target is the repository and not `.github/workflows/`: zizmor also
  reads `dependabot.yml` and the pre-commit configuration, so the narrower target
  reports a clean tree that CI then fails.

## Repo etiquette

- **Conventional Commits** (`type(scope): summary`), scope naming an area of the
  code. The summary *is* the changelog entry — `CHANGELOG.md` is generated from
  the commit log by git-cliff (`cliff.toml`) and is never hand-edited — so write
  it for a reader who will never see the diff. An entry that needs a paragraph
  gets one: the commit body is carried through verbatim. A CI gate on every pull
  request checks the form.
- **Every gate green before a commit**: ruff, pyright, mypy, pytest. A commit
  that leaves the tree red is not a smaller commit, it is a broken one.
- `__version__` in `src/lovely_assertions/__init__.py` is the single source of
  truth for the version; the wheel takes it from there and a test pins the pair.

## Gotchas

- **Adding an assertion is four edits, not one**: the method, its typed tests in
  `typing_tests/positive/`, a rejection case in `typing_tests/negative/`, and a
  regenerated `docs/reference/assertions.md`. Public exports need `__init__.py`
  *and* `__all__`.
- **`__slots__` on every class**, including subject subclasses. A subject holds
  one attribute and is allocated per assertion; a `__dict__` per subject is
  measurable.
- **Do not "simplify" the dispatch chain.** The long `if`/`elif` in `_subjects`,
  the early returns in `_names` and the message-form classifier in
  `tests/test_happy_path.py` are tables, one branch per case. Ruff's `PLR0911`
  is turned off for exactly those three files, with the reason inline.
- **A fuzzing property belongs in `fuzz/properties.py`, never in a driver.** The
  drivers are thin on purpose: Atheris runs on Linux x86_64 alone, so a property
  written inside one is a property nobody else can run. Adding a property means
  adding it to a driver too — `tests/test_fuzzing.py` fails when one is orphaned.
- **`benchmarks/` measures, `tests/test_performance_invariants.py` asserts.**
  Anything wall-clock-dependent belongs in the first; only claims that hold on
  any machine — no allocation on a passing assertion, a bounded import — belong
  in the second.
- **No volatile numbers** in `CLAUDE.md`, `README.md` or docstrings (test counts,
  timings, file counts). They drift silently. State the contract instead.

## Where the rest lives

- **`.claude/rules/*.md`** — per-area conventions, loaded when you touch matching
  files: code style, performance, typing and failure-message grammar for `src/`;
  comments and docstrings; testing for `tests/` and `typing_tests/`; the
  executable-docs conventions for `docs/`; dependencies and packaging for
  `pyproject.toml`; and the hardening conventions for `.github/`.
- **`.claude/skills/`** — `quality-gate` runs every local gate and reports one
  table; `new-assertion` walks the four edits adding an assertion actually needs.
  **`.claude/agents/standards-reviewer.md`** reviews a diff against all of the
  above.
- **`docs/`** — the user documentation, in English, and executable. Four parts:
  `getting-started/` (a linear introduction), `guides/` (task-oriented, one per
  subject or feature), `reference/assertions.md` (**generated** — never hand-edit
  it, run the script), and `concepts/` (why it is built this way). Start from
  `docs/README.md`, which routes by reader.
- **Writing a page**: a `python` block runs, sharing the page's namespace in
  document order; a `text` block after one is its expected output — the failure
  message if it raised, otherwise what it printed. Never quote a message you
  have not run. `bash` and `console` blocks are never executed. A block that
  cannot run is marked `<!-- docs-test: skip - why -->` on the line above the
  fence. Pages run in an empty directory, so a path example can create its own
  files; nothing volatile (a temp path, a wall-clock date, a set's iteration
  order) may appear in a quoted result.
