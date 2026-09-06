# Changes

Every other assertion here is about a value. These two are about what an
**action did** to one.

```python
from lovely_assertions import expect_change


class Ledger:
    def __init__(self) -> None:
        self.rows: list[str] = []

    def count(self) -> int:
        return len(self.rows)


ledger = Ledger()

with expect_change(ledger.count).by(1):
    ledger.rows.append("a")

print("one row appeared")
```

```text
one row appeared
```

> Full signatures:
> [`expect_change`](../reference/assertions.md#elsewhere-in-the-public-api).

## What it replaces

Three statements, whose order is a discipline nobody checks:

```python
from lovely_assertions import expect


class Ledger:
    def __init__(self) -> None:
        self.rows: list[str] = []

    def count(self) -> int:
        return len(self.rows)


ledger = Ledger()

before = ledger.count()
ledger.rows.append("b")
expect(ledger.count() - before).is_equal_to(1)
```

Sample after the action instead of before and the test passes for the wrong
reason. The block removes the choice — there is no way to write the samples the
wrong way round.

The message is the rest of the case. Subtracting first throws the starting value
away, so the hand-written form has one sentence for two different bugs:

```python
from lovely_assertions import expect, AssertionFailure


class Ledger:
    def __init__(self) -> None:
        self.rows: list[str] = []

    def count(self) -> int:
        return len(self.rows)


rows = Ledger()
before = rows.count()
rows.rows.extend(["a", "b"])

try:
    expect(rows.count() - before).is_equal_to(1)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected rows.count() - before to equal 1, but was 2.
```

An action that did nothing and an action that did twice too much both arrive as
a claim about one number. Here they are two sentences, and both name where the
value started:

```python
from lovely_assertions import expect_change, AssertionFailure


class Ledger:
    def __init__(self) -> None:
        self.rows: list[str] = []

    def count(self) -> int:
        return len(self.rows)


empty = Ledger()
try:
    with expect_change(empty.count).by(1):
        pass
except AssertionFailure as failure:
    print(failure)

busy = Ledger()
try:
    with expect_change(busy.count).by(1):
        busy.rows.extend(["a", "b"])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected empty.count to increase by 1, but it did not move from 0.
Expected busy.count to increase by 1, but it went from 0 to 2 (a change of 2).
```

## The four claims

| | Asserts |
|---|---|
| `with expect_change(probe):` | the value moved, whatever it moved to |
| `.to(value)` | it moved, **and** it ended up here |
| `.by(amount)` | it moved, **and** it moved exactly this far |
| `with expect_no_change(probe):` | it did not move |

`.to(...)` is the one to reach for when a destination alone would look right.
A value that was already `"shipped"` never moved, and only this catches it:

```python
from lovely_assertions import expect_change, AssertionFailure

order = {"state": "pending"}
try:
    with expect_change(lambda: order["state"]).to("shipped"):
        pass
except AssertionFailure as failure:
    print(failure)
```

```text
Expected lambda: order["state"] to change to 'shipped', but it did not move from 'pending'.
```

`expect_no_change` is the assertion a test means when the point is that work was
*not* done:

```python
from decimal import Decimal

from lovely_assertions import expect_no_change, AssertionFailure

balance = [Decimal("10.00")]
try:
    with expect_no_change(lambda: balance[0], because="a retry must not charge twice"):
        balance[0] += Decimal("7.00")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected lambda: balance[0] not to change, but it went from Decimal('10.00') to Decimal('17.00') because a retry must not charge twice.
```

It has no `.to` and no `.by`, and that is enforced by the type checker rather
than at runtime: a destination and an amount both narrow a claim that something
moved, and this one claims the opposite.

## The probe is a callable

It is called twice — once before the block, once after — so a *value* would be
sampled once and never re-read. `ledger.count` and `lambda: order["state"]` are
probes; `ledger.count()` and `order["state"]` are not, and both checkers say so.

Nothing else is called. A passing block costs those two calls and one
comparison.

## Which probes get `.by(...)`

`.by(...)` needs a difference, so it is offered where one can be taken: `int`,
`float`, `Decimal`, `Fraction`, `datetime` and `timedelta`. A `str` probe has no
`.by`, for the reason a `str` subject has no `is_positive`.

Two instants differ by a **duration**, so the amount is a `timedelta` and not a
`datetime`:

```python
from datetime import UTC, datetime, timedelta

from lovely_assertions import expect_change

clock = [datetime(2024, 1, 1, tzinfo=UTC)]

with expect_change(lambda: clock[0]).by(timedelta(hours=1)):
    clock[0] += timedelta(hours=1)

print("an hour passed")
```

```text
an hour passed
```

`bool` is deliberately excluded, the way `bool` leads the dispatch table ahead of
`int`: a flag that went from `False` to `True` did not "increase by 1".

## Gotchas

### A probe must not hand back the thing it is watching

`lambda: order.items` returns *the list itself*, so a block that appends to it
holds one object as both samples. Nothing can be observed — and rather than
report a value that is standing in for both, this is refused outright:

```python
from lovely_assertions import expect_change, AssertionFailure

items: list[str] = []
try:
    with expect_change(lambda: items):
        items.append("widget")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected lambda: items to change, but the probe returned the same list both times, so nothing could be observed -- sample a value instead, as in lambda: list(...) or lambda: len(...).
```

`expect_no_change` is refused the same way, and that is the sharper half: over
one mutable object it is not passing because nothing happened, it is passing
because it looked at the same object twice. Sample a value —
`lambda: list(items)` or `lambda: len(items)` — and the assertion checks
something again.

The test is hashability, not identity. Two reads of an immutable value are
legitimately one object, and a small `int` or an interned string always is.

### A scope you never enter asserts nothing

`expect_change(ledger.count).by(1)` without a `with` runs, returns and checks
nothing — and unlike a half-written chain it reads as a *finished* sentence, so
a reviewer's eye slides over it. It warns from its finaliser, the way CPython
warns about a coroutine nobody awaited:

<!-- docs-test: skip - the warning arrives whenever the collector runs, so a page cannot quote it reliably -->

```python
expect_change(ledger.count).by(1)  # RuntimeWarning: asserted nothing
```

Late is enough: under `-W error` a silently-green test still goes red.

### An exception in the block is the finding

Nothing is reported when the block raises. That exception is what went wrong,
and a second failure about a block that never finished would bury it.

---

**See also:** [any value](any-value.md) · [numbers](numbers.md) ·
[soft assertions](soft-assertions.md)
