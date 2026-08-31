# Type-checker divergences

Where pyright and mypy disagree about this library, what is suppressed in the
shipped source, and the decision behind each one.

pyright is the reference checker. mypy is run alongside it, both at their
strictest settings, and both are required green before anything is committed.

Where the two genuinely disagree, the API keeps the shape pyright can express and
the disagreement is written down here. **The API is never shaved down to make a
checker happy** — that would trade the library's actual value for a green tick.

This page is also a ledger with teeth:

- a test fails if the source uses a suppression code that has no entry below, and
  fails on any bare `# type: ignore` or `# pyright: ignore` with no rule code;
- pyright runs with `reportUnnecessaryTypeIgnoreComment` as an error, and mypy
  with `warn_unused_ignores`, so an entry cannot outlive the divergence it
  covers — the suppression starts failing the build the day the checker improves;
- pyright runs with `enableTypeIgnoreComments` off, so a `# type: ignore` written
  for mypy can never silence pyright by accident. Each checker is suppressed only
  by its own syntax.

Nothing here changes what the library *does*. If you are reading it to decide
whether to adopt the package, the summary is: both checkers work, one of them is
occasionally less precise, and every place that is true is listed below.

---

## Suppressions in the shipped source

Three codes, and that is the whole list.

### `overload-overlap` (mypy) / `reportOverlappingOverload` (pyright)

**Where:** three `expect()` overloads — `bool`, `str` and `Mapping`.

**Why it fires:** `bool` is a subclass of `int`, `str` is a `Sequence[str]`, and
a `Mapping` is a `Collection` of its keys. Each of the three therefore shadows
part of a later overload with a different return type, which is exactly the
pattern these rules exist to warn about.

**Why it stays:** first-match-wins ordering *is* the dispatch contract.
`expect(True)` must be a `BoolExpect` and not a `NumericExpect`; `expect("x")`
must be a `StringExpect` and not a `SequenceExpect[str]`. The overlap is the
mechanism, so each checker that reports it is told per line that it is intended:
the `bool` and `str` overloads carry both suppressions, while the `Mapping` one
carries mypy's alone — pyright does not report that pair, and adding its
suppression there would fail the build, since `reportUnnecessaryTypeIgnoreComment`
is an error here. The runtime dispatch walks the identical order, and that table is
pinned twice: statically in `typing_tests/positive/dispatch.py`, at runtime in
`tests/test_narrowing.py`. Nothing compares the two lists, so keeping them in
step is discipline rather than a guard. See [Typed dispatch](typed-dispatch.md).

### `reportPrivateUsage` (pyright)

**Where:** three call sites. One reads `sys._getframe`, which is underscored but
is the documented, allocation-free way to walk the stack — `inspect.currentframe`
is a thin wrapper that would drag the whole `inspect` module in on the first
failure for no gain. The other two report a continuation's failure through the
subject it came from, so the message carries that subject's name rather than the
continuation's.

**Why they stay:** each is deliberate, each is internal to the package, and none
reaches anything a user can see.

---

## Real disagreements between the two checkers

### mypy widens a multi-member union when `None` is removed

Given `value: int | str | None`, `is_not_none()` is declared
`(self: Expect[S | None]) -> Expect[S]`.

| Checker | Solves `S` to | Verdict |
|---------|---------------|---------|
| pyright | `int \| str` | correct |
| mypy | `object` | widened |

mypy handles the single-member case (`str | None` → `str`) correctly. It loses
precision only when more than one member remains after `None` is removed.

**Decision:** keep the signature. pyright resolves it exactly, and mypy's answer
is still *sound* — merely imprecise. The one affected assertion in the typed test
corpus carries a suppression that mypy's `warn_unused_ignores` will flag the day
mypy improves.

### A mock is statically assignable to everything

typeshed puts an `Any` in `NonCallableMock`'s MRO, so every concrete overload of
`expect()` accepts a mock and whichever comes first claims it —
[Typed dispatch](typed-dispatch.md#the-one-place-the-two-halves-do-not-agree)
demonstrates it.

**Decision:** ship no static overload, and dispatch to `MockExpect` at runtime
anyway — the one place the two tables deliberately disagree. An overload written
for mocks is reached only by leading the chain, where it overlaps most of the
others and draws a `reportOverlappingOverload` per pair. Those suppressions would
pay only where a parameter is *declared* `Mock` — which in a real suite it often
is not, a mock usually arriving from a fixture or an inferred assignment.
`expect(mock, as_=MockExpect)` is the typed route — see
[Mocks](../guides/mocks.md).

`NotImplemented` is the second value with this property, found by sweeping exotic
subjects through both checkers and diffing the answers against the runtime.
Nothing is done about it and nothing should be; what would be wrong is a ledger
claiming this is the *one* such value when a short sweep finds a second.

---

## Choices made for soundness rather than for a checker

These look like they could have gone the other way. The reasoning is recorded so
it does not have to be rediscovered.

### `is_not_none()` returns `Expect[S]`, not a re-specialised subject

It is technically possible to overload `is_not_none` so that
`expect(maybe_text).is_not_none()` returns a `StringExpect` rather than an
`Expect[str]`, and both checkers accept it. It was tried and reverted.

The problem is user subclasses. A `class Mine(Expect[str])` also matches
`self: Expect[str | None]`, so it would be handed back labelled `StringExpect` —
a lie the checker would then propagate. `Expect[S]` is a supertype of whatever
the object really is, so the widening is always sound, and it costs nothing.

The documented pattern is to rebind and re-enter:

```python
from lovely_assertions import expect

raw: str | None = "ada"
name = expect(raw).is_not_none().subject
expect(name).starts_with("a")
print("rebound")
```

```text
rebound
```

### `.subject` on a sequence returns `Sequence[E]`, not `list[E]`

One subject class covers lists, tuples and every other sequence, which is what
makes the catalogue work at all. The cost is that `.subject` hands back the
abstract type. The element type — the part carrying the information — survives
intact.

### An enum member is an enum before it is anything else

An `IntEnum` member really is an `int` and a `StrEnum` member really is a `str`,
so the dispatch could route them to `NumericExpect` and `StringExpect`. It does
not: every enum member gets `EnumExpect`.

The alternative — plain enums here, mixin enums with their mixin's catalogue —
makes the subject depend on a choice the enum's *author* made, which nobody
reading a test can be expected to hold in their head. It would also put
`has_name` and `has_value` out of reach on exactly the enums people write most.

The cost is paid where it is cheapest: `is_greater_than` on an `IntEnum` member
is a checker error rather than a runtime surprise. `is_equal_to`, `is_in` and
`is_one_of` live on the generic subject and still work, and
`expect(level.value)` asks for the mixin's catalogue in one unambiguous move.

### `date` and `datetime` cannot be kept apart by the type system

`datetime` subclasses `date`, so a `datetime` is assignable everywhere a `date`
is — and *ordering* the two raises `TypeError` in CPython, while `==` quietly
answers `False`. No bound can exclude a subtype, and the same hole exists for
naive versus aware datetimes, which the type system cannot see at all.

So the assertions that order the two, or measure the distance between them,
catch both and raise a `TypeError` naming which side is which. That is
deliberately *not* an assertion failure: neither is a fact about the value under
test, both are bugs in the test itself, and reporting them as
`Expected deadline to be before ...` would send you looking in the wrong place.
`is_equal_to` is left alone, because `==` across the pair is well defined: a
`date` that is not the `datetime` you expected is an ordinary failure, and the
message prints both reprs so the mix is visible in it.

### `Found`'s third parameter is a promise, not a proof

`Found[P, V, A]` lets an assertion say what `.which` hands back, and `A` is not
tied to `V` by anything. A producer that declares one type and returns another
type-checks, and `.which` then raises `AttributeError`.

Bounding it was tried and rejected on measurement: pyright stops applying the
default once the parameter has a bound, so `.which` evaluates to an unsolved type
variable and a dozen typed assertions go red. The bound would reject a spelling
nobody writes and break the one everybody writes.

Tying `A` to `V` properly needs a mapping from a value type to its subject that
the type system can evaluate — which is the same thing `expect()`'s overloads
are, and they cannot be reused as a constraint. So it stays a promise the
producer makes, and every producer inside the library is a pinned typed
assertion. If you [write your own](../guides/extending.md), this is your
responsibility.

---

See also: [Typed dispatch](typed-dispatch.md) · [Design goals](design-goals.md)
