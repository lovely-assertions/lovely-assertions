# Controlling output

A failure message is bounded, and it renders your types with `repr`. When one is
too short, `formatting()` raises the bounds for a block; when it renders your
types badly, `register_formatter()` teaches it how they read.

## Bounds: `formatting()`

Every rendering in the library is capped. A collection prints its first few items
and counts the rest; one value prints about a terminal line; a diff prints a
screenful; a difference report descends a couple of levels into nested structure.

```python
from lovely_assertions import expect, AssertionFailure

audit_rows = list(range(60))
try:
    expect(audit_rows).contains(999)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected audit_rows to contain 999, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (50 more)].
```

Those defaults are chosen for the message you **skim** — the one that says at a
glance which assertion went wrong. They are exactly wrong for the message you are
**debugging**: a sixty-element list showing the first ten is least helpful
precisely when the row that matters is the sixtieth, which is the moment you are
looking.

So the bounds become a scope:

```python
from lovely_assertions import expect, formatting, AssertionFailure

audit_rows = list(range(60))
try:
    with formatting(max_items=20):
        expect(audit_rows).contains(999)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected audit_rows to contain 999, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, ... (40 more)].
```

| Option | Bounds |
|---|---|
| `max_items` | items shown from a collection |
| `max_chars` | characters shown for one value |
| `max_diff_lines` | lines shown in a unified diff |
| `max_depth` | levels a difference report descends into nested structure |

Exactly the assertions that were failing before still fail. The scope changes
what a failure *says*, never whether it happens.

### Nesting composes

`None` leaves a bound alone, and a scope resolves against whatever is in force
when it is **entered**:

```python
from lovely_assertions import expect, formatting

with formatting(max_chars=500):
    with formatting(max_items=100) as options:
        print(options.max_items, options.max_chars)
```

```text
100 500
```

Asking for one bound is not a request to reset the others — so a context manager
built in a fixture composes with whatever scope the test happens to be inside.

### A bad limit is reported

```python
from lovely_assertions import formatting

try:
    formatting(max_items=0)
except ValueError as error:
    print(error)
```

```text
max_items must be at least 1, not 0
```

`max_items=0` would announce a failure and then decline to say anything about it.
That is a bug in the test, not a rendering preference.

### Scoping is per context, not per process

The options in force live in a `ContextVar`, so one thread's or one asyncio
task's rendering never reaches another's messages. That is also why there is no
global setter: shared assertion state that each test mutates stops being safe the
moment the suite runs in parallel.

Nothing here costs a passing assertion anything — the `ContextVar` is read on the
failure path only.

## Rendering: `register_formatter()`

`repr` is the right default and a poor one for domain objects. A message reading
`<myapp.orders.Order object at 0x10f3a2d90>` hands you a memory address in place
of the thing you are trying to understand.

### `ObjectFormatter` — render an object through chosen attributes

```python
from lovely_assertions import expect, register_formatter, ObjectFormatter, AssertionFailure


class Order:
    def __init__(self, id: str, total: int) -> None:
        self.id = id
        self.total = total


register_formatter(ObjectFormatter(Order, "id", "total"))

placed = Order("ord-118", 4200)
try:
    expect(placed).is_equal_to(Order("ord-119", 4200))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected placed to equal Order(id='ord-119', total=4200), but was Order(id='ord-118', total=4200).
```

At least one attribute name is required: `ObjectFormatter(Order)` would render
`Order()`, which is less than `repr` already gives you. Subclasses are claimed
too, and the heading names the *runtime* type, so a subclass still says which one
it is.

### `IterableFormatter` — render a domain collection as its contents

```python
from lovely_assertions import expect, register_formatter, IterableFormatter, format_value


class OrderBook:
    def __init__(self, *orders: int) -> None:
        self.orders = list(orders)

    def __iter__(self):
        return iter(self.orders)


register_formatter(IterableFormatter(OrderBook, max_items=3))
print(format_value(OrderBook(1, 2, 3, 4, 5)))
```

```text
OrderBook[1, 2, 3, ... (more)]
```

That `max_items` is the formatter's own, fixed when you register it —
`formatting(max_items=...)` does not move it. Its default matches the one
`formatting()` starts from, so pass it only when this type has a reason to print
differently from everything else.

It claims the types you give it **and their subclasses**, not every iterable — a
formatter that claimed every iterable would sit in front of the whole registry,
and `repr` is the right rendering for a list of integers.

It says `(more)` rather than `(2 more)` there because `OrderBook` defines no
`__len__`, so there is no count to state — give your type a `__len__` and the
number appears. Items are rendered through the registry too, so a nested type
with its own formatter reads through that one.

### Writing your own

A formatter is any object with `can_handle` and `format`. That is the exported
`ValueFormatter` protocol, and it is structural — nothing has to inherit from
anything:

```python
from lovely_assertions import expect, register_formatter, AssertionFailure


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyFormatter:
    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Money)

    def format(self, value: object, /) -> str:
        assert isinstance(value, Money)
        return f"EUR {value.cents / 100:.2f}"


register_formatter(MoneyFormatter())

price = Money(1250)
try:
    expect(price).is_equal_to(Money(999))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected price to equal EUR 9.99, but was EUR 12.50.
```

### Where to register

**Once, at import — in a `conftest` module body — and never per test.** Global
assertion state that each test edits stops being safe the moment the suite runs
in parallel, which is why registering the *same formatter object* twice raises
`ValueError`: the only way that happens is configuration running per test rather
than once.

Registration is **first-come-wins**. A later registration does not displace an
earlier one, because then a message would depend on which module happened to be
imported first.

To override a rendering for one block, pass the formatter to a
[soft scope](soft-assertions.md). There is no way to scope a formatter without
the rest of that scope: failures inside are collected and reported together on
exit rather than raising at the first one, which is why the output below opens
with a count.

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure


class Terse:
    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, list)

    def format(self, value: object, /) -> str:
        assert isinstance(value, list)
        return f"<{len(value)} rows>"


audit_rows = [1, 2, 3]
try:
    with soft_assertions(formatters=(Terse(),)):
        expect(audit_rows).is_equal_to([1, 2])
except AssertionFailure as failure:
    print(failure)
```

```text
1 assertion failed:
  (1) Expected audit_rows to equal <2 rows>, but was <3 rows>.
        lengths differ: 3 items, expected 2
        extra items: [3]
```

Scoped formatters are consulted **before** the global ones, innermost scope
outwards, and this is the only sanctioned way to change rendering per test.
`formatting()` bounds how much is printed; it does not take formatters.

### It never raises

Formatters are user code, and user code has bugs. One that throws is skipped
exactly as if it had declined — and so is one that returns anything but a `str`,
which is what a forgotten `return` looks like. Either way the next formatter is
asked, with no error and no warning, so if a rendering did not change, check that
`format` returns a string. A value nothing claims falls back to `repr`, and one
whose `repr` also throws is named by its type. Turning your failing test into an
error raised inside the assertion library is the worst outcome available.

### `format_value`

The same function the library uses, exported so a formatter can render its own
parts through the registry — which is how a list of orders gets the order
formatter. That re-entry is bounded at a fixed depth — past it a value renders as
`...` — and no scope moves it: `formatting(max_depth=...)` bounds a difference
report, not this.

---

**See also:** [failure messages](../concepts/failure-messages.md) ·
[extending](extending.md) · [soft assertions](soft-assertions.md) ·
[performance](../concepts/performance.md)
