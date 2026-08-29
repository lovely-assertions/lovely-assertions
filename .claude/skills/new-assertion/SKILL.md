---
name: new-assertion
description: Adds an assertion to a lovely-assertions subject and wires every place it has to appear — the method, both typing corpora, the runtime tests that pin its failure message, the regenerated reference, and the guide page. Use when adding a check to the catalogue.
argument-hint: '<subject> <method> "<what it asserts>"'
arguments: [subject, method, purpose]
---

Add `$method` to the `$subject` subject (it asserts: $purpose). Follow every step
— the value of this skill is that nothing gets forgotten. **Adding an assertion
is four edits, not one**, and the four are easy to do three of.

Before anything else, read `.claude/rules/code-style.md`,
`.claude/rules/failure-messages.md` and `.claude/rules/typing.md`.

## 0. Does it earn its place?

An assertion earns its place **by the sentence it prints when it fails**. Write
that sentence first, before the code:

```
Expected {subject name} {expectation}[ because {reason}].
```

If it says no more than the comparison a reader would have written by hand, stop
— the assertion is not worth adding, and saying so is a better outcome than
adding it. Check the existing catalogue for a neighbour that already covers it;
if there is a near-neighbour, the two docstrings must each say which to reach for.

## 1. The method

In the subject module that owns `$subject`, under the right
`# -- group name ---` banner (the generated reference reads those banners):

- Compare, `return self` on success, `return self._fail(...)` on failure. Never
  raise `AssertionFailure` directly, and **never build the message outside the
  failure branch** — including as an argument to a helper, because Python
  evaluates arguments eagerly. A passing assertion costs a comparison and a
  `return self`.
- The value under test is **positional-only** (`/`); `because: str = ""` is
  **keyword-only** and passed straight through to `_fail`, never interpolated.
- Returns `Self`, or the narrowed subject type if it narrows. Never `None`.
- `@override` if it overrides. `__slots__` on any new class.
- Render values through the formatter registry, never a raw `repr` at the call
  site, or a user's registered formatter is silently skipped for this one
  assertion. Keep the detail block bounded.
- Docstring: first line imperative, complete on its own, starting with
  "Assert ..." — the reference quotes it verbatim. Then the contract: what it
  accepts, what it returns, what it raises, and the degenerate cases (empty,
  `None`, NaN, unhashable, a strange `__eq__`).
- A caller who misused the API gets `ValueError`/`TypeError` naming what was
  received and what would be valid — not an `AssertionFailure`.

If the assertion is offered on a new subject, or changes which subject a value
gets: the `@overload` chain in `_subjects.py` and the runtime `if`/`elif` there
are **one table written twice**. Edit both in the same change, in the same order.

## 2. Runtime tests — `tests/test_<subject>.py`

- **Pin the sentence.** `pytest.raises(AssertionFailure, match=...)`, or an exact
  comparison against `str(excinfo.value)`. A test that only checks *that* it
  failed is passing on the thing this library exists to get right.
- Cover the happy path, the failure, `because=`, the degenerate cases the
  docstring promises, and behaviour inside a soft-assertion scope.
- **Then break it.** Mutate the comparison you just wrote and confirm the test
  goes red. A guard you have not tried to break is not a guard.
- AAA blocks separated by blank lines; `test_<unit>_<condition>_<expected>`.
- Shared doubles come from `tests/conftest.py` — never fork a private copy.

## 3. Typing corpora

- `typing_tests/positive/<subject>.py` — the call type-checks, and `assert_type`
  pins what it returns. If it narrows, pin the narrowed `.subject`.
- `typing_tests/negative/<subject>_negative.py` — at least one case that both
  checkers must **reject**: the method on a subject that should not offer it, or
  a wrong argument type. The negative corpus is the half that proves the positive
  one means anything.

## 4. Reference, docs and changelog

- `uv run python scripts/generate_reference.py` — a test fails if
  `docs/reference/assertions.md` has drifted. Never hand-edit that file.
- Add it to the guide page for its subject under `docs/guides/`, with a runnable
  example. **Run the page** and paste the real output into the `text` block;
  every one of them is compared against what the library actually prints.
- Public symbol? `src/lovely_assertions/__init__.py` **and** `__all__` — both, or
  neither; a test asserts they match.
- A `CHANGELOG.md` entry under `## [Unreleased]`, written for a reader who will
  never see the diff.

## 5. Verify

```
uv run --python 3.13 pytest tests/test_<subject>.py -q
uv run --python 3.13 ruff format . && uv run --python 3.13 ruff check .
uv run --python 3.13 pyright && uv run --python 3.13 mypy
uv run --python 3.13 pytest
```

Report results honestly — red output is a finding, not a detail to omit.
