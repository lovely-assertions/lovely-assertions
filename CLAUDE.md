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
  `ast`, `linecache`, `dataclasses` and `uuid` are imported *inside* the function
  that needs them — a failure path for `difflib`, `ast` and `linecache`, and for
  the other three the one assertion that cannot answer without the module. The
  subjects that assert on `datetime`, `enum` and `pathlib` values are typed
  against those modules under `TYPE_CHECKING` and dispatched by name, so
  `import lovely_assertions` pulls in none of the three. `datetime` and `pathlib`
  are then never imported at all; `enum` is, lazily, by the flag assertions and
  by enum-by-name equivalence, which cannot do their work without it.
- **A passing assertion is a comparison plus `return self`.** No frame
  inspection, no `ContextVar` read, no allocation, no message built, `because`
  never read. An f-string message outside the failure branch is a defect, not a
  style preference — and a message passed as a *helper argument* is built on the
  happy path too.
- **Both checkers, both strict, zero errors.** pyright is the reference; mypy is
  matrixed alongside it. A typing limitation is documented and lived with, never
  worked around by dropping an overload or widening a return to `Any`.
- **The failure message is the product.** An assertion whose message says less
  than the comparison it replaces is worse than no assertion at all.
- **`AssertionFailure` derives from `AssertionError`**, so pytest and unittest
  count it as a failure rather than an error.
- **English only** — code, comments, docstrings, test names, commit messages,
  and every page under `docs/`.
- **The documentation is executable.** Every `python` block on a hand-written
  page — all of `docs/` bar the generated reference, plus the repo's own
  `README.md` — is run by `tests/test_documentation.py` and type-checked by a
  second pyright pass, and every `text` block after one is compared against what
  it produced. A page cannot drift from the library without failing the build.

## Architecture

`expect()` is a typed dispatcher, not a class. Its `@overload` chain and the
runtime chain in `_subjects.py` — the exact-type table, then the `issubclass`
ladder in `_resolve_shape` — are one table written twice; change one and change
the other in the same edit, or the checker and the runtime disagree about which
subject a value gets. `tests/test_narrowing.py` walks the pair.

A subject is assembled from mixins, one file per family of question, over
`Expect[T]` (`_core/__init__.py`), which is itself such an assembly. Every mixin
is an `ExpectBase[T]` with empty `__slots__` and every assertion returns `Self`,
so the wrapper stays one allocation and a chain crossing three seams still ends
with the concrete subject's whole catalogue.

Every assertion is a comparison followed by `return self`, `self._fail(...)`, or
`self._fail_narrowing(...)` where it was meant to narrow — that one reports, then
hands back a stand-in that absorbs the rest of the chain, so a soft scope shows
one root cause rather than a cascade. Both reach `report_failure`
(`_core/_routing.py`), the single place a failure is rendered and routed, which
is what makes soft scopes, subject naming and `because` work everywhere without
per-assertion wiring.

Most subjects and helpers are packages — `_bool`, `_engine`, `_exceptions` and
`_subjects` are the ones still small enough to be one module. In a package,
`__init__.py` carries the "why", assembles the class, declares `__all__`, and is
the only way in; its siblings are private to it. A name that crosses a file
boundary therefore drops its leading underscore — pyright strict refuses to
import one that keeps it — while one read only where it is written keeps it.
Imports still point one way: subject packages take `_core` and the shared helpers
(`_exceptions`, `_formatters`, `_formatting`, `_text`, `_occurrence`), while
`_diff` and `_equivalence` are reached only through `_engine`, whose lazy
re-exports keep that machinery out of `import lovely_assertions` until an
assertion reaches for it. Two edges point back — `_core/_found.py` into
`_subjects`, `_names/_expressions.py` into `_core` — and both are function-scoped
to break a cycle and commented as such. Add no third on any other terms.

## Commands

Everything runs through `uv`, against the interpreter `.python-version` pins —
implicitly below, spelled out as `--python` by the `quality-gate` skill.

- `uv sync` — install the package plus the dev group.
- `uv run pytest` — the whole suite, including the harness that shells out to the
  real pyright and mypy over `typing_tests/`, and the one that runs and
  type-checks every documentation example.
- `uv run ruff format . && uv run ruff check .` — format, then lint.
- `uv run pyright` — must stay at zero errors. `--pythonversion 3.14` for the other row
  of the matrix.
- `uv run mypy` — same bar.
- `uv run pyright --verifytypes lovely_assertions --ignoreexternal` — the
  `py.typed` completeness score, which must read 100%; CI parses the JSON and
  fails below it. `--ignoreexternal` is not optional, since typeshed's own gaps
  otherwise dominate the number.
- `uv run pytest --cov` — the same suite, traced, held to the floor in
  `[tool.coverage.report]`. Not a substitute for the untraced run: several
  performance invariants read a measurement that cannot be taken while
  `sys.settrace` is active and skip themselves. CI runs both.
- `uv run python -m benchmarks` — timings, printed for a human, never asserted.
- `uv sync --group fuzz --python 3.13 && uv run python -m fuzz.fuzz_hostile
  -max_total_time=60` — one of the drivers in `fuzz/`, which CI matrixes over,
  Linux x86_64 only. Atheris ships no other wheels, which is why the group is
  opt-in and why everything that decides anything lives in `fuzz/properties.py`:
  `tests/test_fuzzing.py` runs the same properties over a seeded corpus on every
  platform, in the ordinary suite.
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
  code. The summary *is* the changelog entry, and it is also what decides the
  next **version number**: release-please derives both from the commit log, so
  `CHANGELOG.md` and `__version__` are written by a bot and never by hand — write
  it for a reader who will never see the diff. An entry that needs a paragraph
  gets one: the commit body is carried through verbatim. A CI gate on every pull
  request checks the form.
- **Every gate green before a commit**: ruff, pyright, mypy, pytest. A commit
  that leaves the tree red is not a smaller commit, it is a broken one.
- `__version__` in `src/lovely_assertions/__init__.py` is the single source of
  truth for the version; the wheel takes it from there and a test pins the pair.
  It is rewritten by release-please, which finds the line by the
  `# x-release-please-version` marker on it and records the same number in
  `.release-please-manifest.json`. Drop the marker or edit the number by hand and
  the two silently disagree, so a test pins that pair too.

## Gotchas

- **Adding an assertion is never one edit**: the method; runtime tests pinning
  the failure sentence, the only one of these that protects the message; its
  typed tests in `typing_tests/positive/` and a rejection case in
  `typing_tests/negative/`; a regenerated `docs/reference/assertions.md`; and the
  guide page for its subject. A new *mixin file* also needs a `SHARED_BASES` row
  in `scripts/generate_reference.py`, or its assertions reach no page. A public
  export needs three rows in `src/lovely_assertions/__init__.py` — the
  `TYPE_CHECKING` re-export, `_HOME` and `__all__` — since it resolves lazily.
- **`__slots__` on every class**, every mixin included — an assembled subject
  with one `__dict__` anywhere in its bases has one. A subject holds a single
  attribute and is allocated per assertion; that `__dict__` is measurable.
- **Do not "simplify" the dispatch chain.** The `issubclass` ladder in
  `_subjects.py`, the early returns in `_names/_expressions.py` and the
  message-form classifier in `tests/test_happy_path.py` are tables, one branch
  per case. Ruff's `PLR0911` is turned off for exactly those files, with the
  reason inline.
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
  table; `new-assertion` walks every edit adding an assertion actually needs.
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
  fence, and one a checker must *reject* `<!-- docs-test: expect-error - why -->`;
  an exemption that has stopped covering an error fails too. Pages run in an empty
  directory, so a path example can create its own files; nothing volatile (a temp
  path, a wall-clock date, a set's iteration order) may appear in a quoted result.
