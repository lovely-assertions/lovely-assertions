# Numbers and booleans

`expect(3)` and `expect(3.5)` give you a `NumericExpect`; `expect(True)` gives you
a `BoolExpect`. `Decimal` and `Fraction` get an `OrderedExpect`, which is the
comparison half without the float-specific assertions.

> Full signatures: [`NumericExpect`](../reference/assertions.md#numericexpect),
> [`OrderedExpect[T]`](../reference/assertions.md#orderedexpectt),
> [`BoolExpect`](../reference/assertions.md#boolexpect).

## Comparisons

```python
from lovely_assertions import expect, AssertionFailure

response_ms = 1250
expect(response_ms).is_greater_than(1000)
expect(response_ms).is_less_than_or_equal_to(2000)

try:
    expect(response_ms).is_greater_than(2000)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected response_ms to be greater than 2000, but was 1250.
```

All four are there: `is_greater_than`, `is_greater_than_or_equal_to`,
`is_less_than`, `is_less_than_or_equal_to`.

## Ranges

The difference between these two is the one people get wrong, so the message says
which you asked for:

```python
from lovely_assertions import expect, AssertionFailure

response_ms = 1250
try:
    expect(response_ms).is_between(0, 1000)
except AssertionFailure as failure:
    print(failure)

try:
    expect(1000).is_strictly_between(0, 1000)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected response_ms to be between 0 and 1000 inclusive, but was 1250.
Expected 1000 to be strictly between 0 and 1000, but was 1000.
```

`is_between` includes both bounds; `is_strictly_between` excludes them.
`is_not_between` is the complement of the inclusive one.

Bounds that describe no range are a bug in the test rather than a fact about the
value, so all three assertions raise `ValueError` instead of failing: an inverted
`low > high`, a NaN at either end, and — for `is_strictly_between` alone —
`low == high`. Wrapping the call in `except AssertionFailure` will not catch it.

## Sign and zero

```python
from lovely_assertions import expect, AssertionFailure

balance = -3
expect(balance).is_negative()
expect(balance).is_not_zero()

try:
    expect(balance).is_positive()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected balance to be positive, but was -3.
```

`is_positive` is `> 0` and `is_negative` is `< 0`, so zero is neither. Use
`is_zero` / `is_not_zero` for that question. These say more than `is_truthy`,
which would flatten `0`, `""`, `[]` and `None` into one answer.

## Floating point: `is_close_to`

Never assert `==` on a float you computed. `is_close_to` is the assertion for it,
and its four calling forms are `pytest.approx`'s four, deliberately — with the
absolute tolerance spelled `tol` rather than `abs`:

| Call | The subject must be within |
|---|---|
| `is_close_to(x)` | one part in a million of `x`, floored near zero |
| `is_close_to(x, tol=t)` | `t`, an absolute distance |
| `is_close_to(x, rel=r)` | `r × abs(x)`, floored at `1e-12` so the answer near zero stays an approximation |
| `is_close_to(x, tol=t, rel=r)` | **either** one — a relative band with an absolute floor |

```python
from lovely_assertions import expect

ratio = 0.1 + 0.2
expect(ratio).is_close_to(0.3)
print("0.1 + 0.2 is close enough to 0.3")
```

```text
0.1 + 0.2 is close enough to 0.3
```

The default is what `pytest.approx(x)` means, and it is the default because
requiring an explicit tolerance would make the commonest assertion in numeric
testing the one you have to look up.

When it fails, the message gives you the distance — which is what tells you
whether your tolerance is wrong or your maths is:

```python
from lovely_assertions import expect, AssertionFailure

ratio = 0.1 + 0.2
try:
    expect(ratio).is_close_to(0.4, tol=0.001)
except AssertionFailure as failure:
    print(failure)

try:
    expect(1005).is_close_to(1000, rel=0.001)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected ratio to be within 0.001 of 0.4, but 0.30000000000000004 was 0.09999999999999998 away.
Expected 1005 to be within 1.0 of 1000 (a relative tolerance of 0.001), but 1005 was 5 away.
```

The second message resolves the relative tolerance into the absolute one it
worked out to — `within 1.0` — so you do not have to do that arithmetic in your
head to see whether `rel=0.001` was the right ask.

**`tol` and `rel` together mean *within either*, not within both.** Within both
would just be the narrower of the two, which you could have written as a single
`tol`. Within either is the combination that earns its place: a relative band for
large values with an absolute floor for small ones. For a pure relative tolerance
with no floor, write `rel=r, tol=0`. A negative or NaN `tol` or `rel` is refused
with `ValueError`, as a malformed range is.

`is_not_close_to` is the complement, and it also tells you the distance:

```python
from lovely_assertions import expect, AssertionFailure

ratio = 0.1 + 0.2
try:
    expect(ratio).is_not_close_to(0.3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected ratio not to be within 3e-07 of 0.3 (the default relative tolerance of 1e-06), but was 0.30000000000000004, only 5.551115123125783e-17 away.
```

## `nan` and `inf`

```python
from lovely_assertions import expect, AssertionFailure

expect(float("nan")).is_nan()
expect(float("inf")).is_infinite()
expect(1.0).is_not_nan()

try:
    expect(1.0).is_nan()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected 1.0 to be NaN, but was 1.0.
```

These exist because `nan != nan`. `assert value == float("nan")` can never pass,
and `assert value != float("nan")` can never fail — the second is the one that
hurts, a test that stays green for every value there is, NaN included. Neither
spelling asks the question; `is_nan` and `is_not_nan` do.

`is_infinite` holds for `-inf` as well as `inf`, and `is_not_infinite` completes
the four. The two pairs are independent: a NaN passes `is_not_infinite`, and
either infinity passes `is_not_nan`.

## Decimal and Fraction

They get `OrderedExpect`: everything above except the six float-specific ones —
`is_close_to`, `is_nan`, `is_infinite` and their negations — which do not apply.

```python
from decimal import Decimal

from lovely_assertions import expect, AssertionFailure

price = Decimal("1.5")
expect(price).is_between(Decimal("1"), Decimal("2"))

try:
    expect(price).is_greater_than(Decimal("2"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected price to be greater than Decimal('2'), but was Decimal('1.5').
```

`decimal` and `fractions` are never imported by this library — the dispatch
recognises those types by name. Importing this package does not import them.

## Booleans

`expect(True)` is a `BoolExpect`, not a `NumericExpect`, even though `bool` is a
subclass of `int`. The dispatch puts `bool` first on purpose — see
[Typed dispatch](../concepts/typed-dispatch.md).

```python
from lovely_assertions import expect, AssertionFailure

is_shippable = False
expect(is_shippable).is_false()

try:
    expect(is_shippable).is_true()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected is_shippable to be True, but was False.
```

`is_not_true` and `is_not_false` complete the four. On a `bool` they say nothing
new — `is_not_true` is `is_false`, `is_not_false` is `is_true` — and each is
kept because it reads differently from its mirror: `is_false` states what the
value is, `is_not_true` what it must not have become. They only decide
differently on a subject built by hand around something that is not a `bool`,
since `expect()` routes nothing else here.

`is_true` is `is True`, not truthiness — `expect(1).is_true()` is a type error,
because `expect(1)` is not a `BoolExpect`. For truthiness, use `is_truthy` from
[the universal catalogue](any-value.md#truthiness).

### `implies`

The assertion for a conditional invariant — "if this, then that" — which is
otherwise written as an `if` around an `assert`:

```python
from lovely_assertions import expect, AssertionFailure

has_discount_code = True
discount_applied = False
try:
    expect(has_discount_code).implies(discount_applied)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected has_discount_code to imply the consequent, but was True while the consequent was False.
```

It passes whenever the subject is false — three of the four rows pass — and
fails only when the subject held and the consequent did not. The message names
both sides, which `if a: assert b` cannot. One difference from that `if`:
`implies` takes a value, so the consequent is computed before the assertion runs,
whatever the subject is.

---

**See also:** [any value](any-value.md) · [dates and times](dates-and-times.md)
for `timedelta` comparisons · [matchers](matchers.md) for `close_to` inside a
larger expectation.
