---
name: quality-gate
description: Runs lovely-assertions' full local quality gate — format, lint, both strict type checkers, the whole suite including the docs and typing-surface harnesses, coverage against its floor, py.typed completeness, the generated reference, and the packaging contract — and reports a pass/fail table with concrete fixes. Use before committing, before tagging a release, or whenever asked whether the repo is green.
disable-model-invocation: false
allowed-tools: Bash(uv run *) Bash(uv lock *) Bash(uv build *) Bash(uvx *) Bash(git status *) Bash(git diff *)
---

Run **every** gate below, even if an early one fails — the report must show the
whole picture, not stop at the first red. For each gate record: pass/fail, the
exact failing output (trimmed to the relevant lines), and the concrete fix.

Pin the interpreter explicitly on every command.

## Gates

1. **Format** — `uv run --python 3.13 ruff format --check .`
2. **Lint** — `uv run --python 3.13 ruff check .`
3. **Types (reference checker)** — `uv run --python 3.13 pyright`, then
   `uv run --python 3.13 pyright --pythonversion 3.14`. Zero errors on both rows.
4. **Types (second opinion)** — `uv run --python 3.13 mypy`, then
   `uv run --python 3.13 mypy --python-version 3.14`. Same bar. A divergence
   between the two is documented and lived with, never fixed by shaving the API —
   if you are about to suggest dropping an overload or widening a return to
   `Any`, that is the wrong fix and the report should say so.
5. **Suite** — `uv run --python 3.13 pytest`. This is the slow one: it includes
   the harness that shells out to the real pyright and mypy over `typing_tests/`,
   and the harness that executes every `python` block under `docs/` and compares
   every quoted result. Run it **untraced** — several performance invariants skip
   themselves while `sys.settrace` is active, so a coverage run is not a
   substitute for this one.
6. **Coverage floor** — `uv run --python 3.13 pytest --cov -q`. `fail_under` in
   `[tool.coverage.report]` is the floor. If it fails, the fix is a test, never a
   lower floor and never a `# pragma: no cover`.
7. **Typed-surface completeness** —
   `uv run --python 3.13 pyright --verifytypes lovely_assertions --ignoreexternal`.
   Must report 100%. `--ignoreexternal` is not optional: without it typeshed's own
   gaps dominate the number and the gate measures the wrong tree.
8. **Generated reference** — `uv run --python 3.13 python scripts/generate_reference.py`,
   then `git diff --exit-code docs/reference/assertions.md`. A dirty diff means
   the checked-in file had drifted; commit the regenerated one.
9. **Packaging contract** — `uv build`, then confirm by opening the wheel that it
   contains `lovely_assertions/py.typed` and that its `METADATA` has no
   `Requires-Dist` line at all. Zero runtime dependencies is the contract, and
   the wheel is what a user installs.
10. **Lockfile** — `uv lock --check`.
11. **Security audit** — `uvx zizmor==1.29.0 --persona regular .`. Must stay clean.
    The target is the repository, matching CI: zizmor also audits `dependabot.yml`
    and the pre-commit configuration, so `.github/workflows/` alone reports a false
    green.

## Report

One table: `gate | status | one-line detail`. Below it, the prioritized fix list,
worst first, each anchored at `file:line`. End with a one-line verdict:
**green / green-with-warnings / red**. Never soften a red — if any gate fails the
verdict is red and the first fix is the blocker.
