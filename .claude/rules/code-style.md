---
paths:
  - "src/**/*.py"
---

# Core code style — one shape, repeated

**The assertion idiom.** Every assertion is the same three lines: compare, return
`self` on success, `return self._fail(...)` on failure. `_fail` is the single
place a failure is reported — that is what gives soft scopes, subject naming and
`because` to every assertion at once. Never raise `AssertionFailure` directly
from an assertion, and never build the message before the failure branch.

```python
def starts_with(self, prefix: str, /, *, because: str = "") -> Self:
    """Assert the subject starts with ``prefix``."""
    if self._subject.startswith(prefix):
        return self
    return self._fail(f"to start with {prefix!r}, but was {...}", because)
```

**Signatures.**
- The value under test is **positional-only** (`/`), so a subject named `prefix`
  cannot collide with the parameter.
- `because: str = ""` is **keyword-only** on every assertion, passed straight
  through to `_fail`, never interpolated.
- An assertion that narrows returns the narrowed subject type; one that does not
  returns `Self`. Nothing returns `None`.

**Classes.**
- `__slots__` on every class, always — a subject is allocated per assertion.
- Subject state is exactly `_subject` and `_name`. Anything else belongs in a
  helper, not on the wrapper.
- `@override` on every method that overrides one. Both checkers require it in
  `src/`, and it costs nothing at runtime.

**Module boundaries.** Imports point one way: `_core` knows nothing of its
subclasses, subject modules import from `_core` and the shared helpers, and
`_subjects` is the only module that assembles them. Absolute imports only.

**Naming.** An assertion's negation mirrors its positive form and carries the
negation where the positive carries its verb: `is_not_`, `does_not_`, `has_no_`,
`was_not_`, `contains_no_`. Configuration methods are not assertions and read as
what they do (`excluding`, `ignoring_order`). A private module is `_name.py`; a
private helper is `_name`. Public names are re-exported from the package root and
listed in `__all__` — both, or neither.

**Errors.** `AssertionFailure` is for a failed assertion. A caller who misused
the API — an empty variadic, a matcher where a value belongs, a formatter for a
type already registered — gets `ValueError` or `TypeError` with a message naming
what was received and what would be valid.

Catch the type you can actually name. The one place `except Exception` is right
is where the library is running **someone else's code** — a `__repr__`, an
`__eq__`, a registered formatter, a caller's predicate — behind a documented
promise not to raise: rendering a value must never turn a failure message into an
error, and a comparison must never turn a difference into one. Those sites carry
a comment naming the promise they are keeping. Anywhere else it hides a bug.

**Layout.** `ruff format` is the floor. Group a subject's methods under
`# -- group name ---` banners; those banners are structure, not decoration, and
the generated reference reads them. One responsibility per function.
