<!--
This pull request's **title** becomes the commit subject on `main`, because merges
are squash-only. It is also what CHANGELOG.md is generated from, so it has to be a
Conventional Commit -- `type(scope): summary`, no full stop -- and it has to read
well to somebody who will never see this diff. A CI gate checks it.

Everything above the `---` becomes the commit body and is published verbatim in
CHANGELOG.md, so write it as prose a stranger can read. Everything below the `---`
is for the review and is stripped out. Headings stay bold rather than `##`: an `##`
would nest a heading inside a changelog list item.
-->

**What this changes**

<!-- One paragraph. What is different afterwards, and for whom. -->

**Why**

<!-- The problem, not the patch. If it is a bug, what the old behaviour cost. -->

---

## Checklist

- [ ] The title above is a Conventional Commit and reads as the changelog entry it will become
- [ ] `uv run ruff format . && uv run ruff check .`
- [ ] `uv run pyright && uv run mypy` — both strict, both clean
- [ ] `uv run pytest`

If this adds or changes an assertion:

- [ ] Tests pin the **failure message**, not merely that it failed
- [ ] Cases in `typing_tests/positive/`, and a rejection case in `typing_tests/negative/`
- [ ] `uv run python scripts/generate_reference.py` re-run and the result committed
- [ ] A new guard was verified by breaking the code it protects and watching it go red
