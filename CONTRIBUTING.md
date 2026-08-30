# Contributing

Thanks for looking. This document is the short version of what the gates
enforce, so you can find out here rather than from a red build.

By taking part you agree to the [code of conduct](CODE_OF_CONDUCT.md). The short
version of that one: be decent to people, and criticise the code.

## Getting set up

Everything runs through [uv](https://docs.astral.sh/uv/), with the interpreter
pinned explicitly:

```bash
uv sync
```

Then, all of which must be green before a commit:

```bash
uv run ruff format . && uv run ruff check . && uv run pyright && uv run mypy && uv run pytest
```

That last one is the slow part: it includes a harness that shells out to the
real pyright and mypy over `typing_tests/`, and another that executes every
Python block in `docs/`.

Optionally, to get the fast half of that on every commit:

```bash
uvx pre-commit install --install-hooks
```

The hooks run the *locked* ruff through `uv run`, not a second copy pinned
somewhere else, so a hook can never format a file in a way CI then rejects.

## The three things this library claims

A change that breaks one of them is not a trade-off, it is a regression:

1. **Typed discoverability.** `expect(x).` offers only the assertions valid for
   the type of `x`. A `str` subject has no `is_positive`.
2. **Real narrowing.** `expect(raw).is_not_none().subject` is a `str` to both
   pyright and mypy, not an `object`.
3. **Failure messages that explain.** A sentence naming the subject, what was
   expected, and what was actually there. Not a diff.

## What a change usually touches

Adding an assertion is four edits, not one:

- the method itself, in the subject module that owns it;
- typed cases in `typing_tests/positive/`, and a rejection case in
  `typing_tests/negative/`;
- runtime tests in `tests/`, pinning the **failure message**, not merely that it
  failed;
- a regenerated `docs/reference/assertions.md`
  (`uv run python scripts/generate_reference.py`) — a test fails if the
  checked-in file has drifted.

A public name needs both `__init__.py` and `__all__`; a test asserts they match.

## Conventions worth knowing before you write code

- **Zero runtime dependencies, permanently.** `project.dependencies` stays
  empty. Development tooling goes in `[dependency-groups]`.
- **A passing assertion is a comparison plus `return self`.** No frame
  inspection, no message built, `because` never interpolated. An f-string
  outside the failure branch is a defect — and a message passed as a *helper
  argument* is built on the happy path too, because Python evaluates arguments
  eagerly.
- **Both checkers, both strict.** pyright is the reference; mypy runs beside it.
  A genuine divergence is documented and lived with, never worked around by
  dropping an overload or widening a return to `Any`.
- **English only** — code, comments, docstrings, test names, commit messages,
  and every page under `docs/`.
- **Tests assert on the sentence.** `pytest.raises(AssertionFailure, match=...)`.
  A test that only checks *that* it failed is passing on the thing this library
  exists to get right.
- **A guard you have not tried to break is not a guard.** Before trusting a new
  test, mutate the code it protects and confirm it goes red.

The full set lives in `CLAUDE.md` and `.claude/rules/`, which are written for
whoever is editing a given area and load by path.

## Commits and pull requests

**`main` is protected, and nothing reaches it except through a pull request.**
Nobody outside the org has push access here, so the path is a fork:

```bash
gh repo fork lovely-assertions/lovely-assertions --clone
```

Branch from `main` in your fork, push there, and open the pull request against
`lovely-assertions/lovely-assertions`. What has to happen before it can merge:

| | |
|---|---|
| `CI success` | green, and the branch up to date with `main` |
| Review | one approval, from a code owner (`.github/CODEOWNERS`) |
| Conversations | every review thread resolved |
| Merge method | squash only — `main` keeps a linear history |

A push to the branch after an approval dismisses that approval, so the thing
that was reviewed is the thing that merges.

**The squashed commit is what lands, and the PR title becomes its subject.** So
the *title* is the Conventional Commit that matters — a CI gate checks it — and it
is what `CHANGELOG.md` is generated from. A title that is not one would be dropped
from the changelog silently, which is why it is a gate rather than a convention.

The PR body becomes the commit body and is published in the changelog too, up to
the `---` the template puts before its checklist. Write both for a reader who will
never see the diff.

Your individual commit subjects are also checked, but they are discarded by the
squash: that gate is for whoever reads the branch a commit at a time during
review, not for `main`.

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope):
summary`, with the scope naming an area of the code. A CI gate checks every
commit on a pull request. The summary becomes the changelog entry, so write it
for a reader who will never see the diff — and leave the full stop off, because
it is a title rather than a sentence.

```
feat(string): assert a subject is a well-formed identifier
fix(diff): keep the hunk header honest when the window is clipped
docs(guides): say what `excluding_missing` actually turns off
```

**`CHANGELOG.md` is generated from those subjects** by
[git-cliff](https://git-cliff.org) — don't edit it. If an entry needs more than a
line, put the explanation in the **commit body**; the template carries it through
verbatim. `chore`, `ci`, `style` and `test` commits are left out of the changelog
on purpose: a reader wants to know what changed about the package.

```bash
uvx git-cliff==2.13.1 -o CHANGELOG.md   # regenerate, at release time
uvx git-cliff==2.13.1 --unreleased      # preview what your commits will say
```

## What CI runs

One required status check, `CI success`, collapses everything below into a
single result:

| Gate | What it proves |
|---|---|
| `ruff` | formatting and lint, on everything |
| `pyright + mypy` | both checkers strict, on 3.13 and 3.14, plus 100% `py.typed` completeness |
| `pytest` | the suite on Linux, macOS and Windows × 3.13 and 3.14 — untraced, so the performance invariants actually run |
| `coverage` | the same suite traced on all three platforms, combined, held to the floor in `pyproject.toml` |
| `SonarQube Cloud` | static analysis over the combined coverage report |
| `build` | the wheel carries `py.typed`, declares no dependencies, renders on PyPI, and contains nothing it should not |
| `conventional commits` | every commit subject on the pull request |

Weekly, in `Scheduled`: the benchmarks (printed, never asserted), the three
fuzzing targets (see below), the suite on the next Python beta (allowed to
fail), and the suite against the *lowest* declared version of every dev tool —
because a floor nobody runs is a guess.

Weekly, in `Security`: `zizmor` over the repository and `pip-audit` over the
locked development tree. The zizmor target is `.` rather than
`.github/workflows/` on purpose — it also reads `dependabot.yml` and the
pre-commit configuration, so the narrower target reports a clean tree that CI
then fails.

## Fuzzing

Three targets under [`fuzz/`](fuzz/README.md), driven by Atheris, each pointed
at a promise this library makes in prose: that a failing comparison raises
`AssertionFailure` and nothing else, that the string catalogue survives
arbitrary text, and — the one worth having — that a value whose `__repr__`,
`__eq__` or `__hash__` misbehaves cannot turn a failure into an error.

Atheris publishes manylinux x86_64 wheels and nothing else, so the deciding
code lives in plain functions in `fuzz/properties.py` rather than in the
drivers. `tests/test_fuzzing.py` runs those same functions over a seeded corpus
on every platform, on every ordinary `uv run pytest`. You do not need Atheris to
exercise the properties; it only drives them harder.

On Linux, to drive one target for real:

```bash
uv sync --group fuzz --python 3.13 && uv run python -m fuzz.fuzz_hostile -max_total_time=60
```

This is not decoration. The hostile target found a real defect on its first
serious run: `render_items` bounded *how many* items a message listed and never
how large one could be, so ten items could produce half a megabyte against the
library's own "bounded, always" rule.

## Releasing

Maintainers only. `__version__` in `src/lovely_assertions/__init__.py` is the
single source of truth; the wheel takes it from there.

1. Bump `__version__`.
2. Regenerate the changelog: `uvx git-cliff==2.13.1 --tag vX.Y.Z -o CHANGELOG.md`,
   and commit it with the bump — through a pull request, like everything else.
3. Tag `vX.Y.Z` on `main` and push the tag.
4. **Approve the deployment.** The `pypi` environment requires a reviewer, so the
   publish job waits for a human before anything reaches the index. That gate is
   the last point at which a mistaken tag costs nothing: a version number on PyPI
   cannot be reused, even after it is yanked.

Two badges are deliberately absent from `README.md`, for the same reason: a
badge for something that does not exist yet renders as an error rather than as
"not set up", and an error on the front page is worse than a gap.

Add the PyPI one on the **first release**:

```markdown
[![PyPI](https://img.shields.io/pypi/v/lovely-assertions)](https://pypi.org/project/lovely-assertions/)
```

Add the SonarQube Cloud ones once the project exists there and `SONAR_TOKEN` is
set as a repository secret — until then the scan job skips itself with a warning
and these render "Project not found":

> **Turning the CI scan on means turning Automatic Analysis off**, in the
> project's settings on sonarcloud.io. The two modes are mutually exclusive, and
> only the CI scan reads `sonar-project.properties`. Under Automatic Analysis the
> dashboard grades `tests/` and `typing_tests/` as production code, does not
> honour the `typing_tests/negative/` exclusion, and scans `.github/` — which is
> why it reports thousands of findings about fixtures. The file has the details.

```markdown
[![Quality gate](https://sonarcloud.io/api/project_badges/measure?project=lovely-assertions_lovely-assertions&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=lovely-assertions_lovely-assertions)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=lovely-assertions_lovely-assertions&metric=coverage)](https://sonarcloud.io/summary/new_code?id=lovely-assertions_lovely-assertions)
```

The release workflow builds, checks the tag against `__version__`, runs the
suite against the *installed wheel*, attaches a signed build provenance
attestation, waits for the environment approval, publishes to PyPI through
Trusted Publishing, and opens the GitHub release with notes rendered from the
commits in the tag. Nothing is uploaded by hand and no API token exists.

The `pypi` environment accepts only a `v*` tag, so a real release cannot be cut
from a branch by accident. `testpypi` also accepts `main`, because a rehearsal is
dispatched from a branch — that is the whole point of it.

To rehearse it, run the workflow manually with `target: testpypi`.
