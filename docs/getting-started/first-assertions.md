# Your first assertions

Every assertion has the same shape: the value under test, then what should be
true of it. Learn the shape once and the rest of the library is a catalogue.

Written out, it is:

```
expect(the value under test).what_should_be_true(the expectation)
```

`expect()` wraps the value in a **subject** — an object carrying the assertions
that make sense for that value. The subject is chosen from the value's type, so
you never look for a method that could not apply.

## The shape, five times

```python
from lovely_assertions import expect

expect("db-01.internal").ends_with(".internal")
expect(42).is_between(1, 100)
expect([3, 1, 2]).has_length(3)
expect({"host": "db-01"}).contains_key("host")
expect(None).is_none()
print("all five passed")
```

```text
all five passed
```

A passing assertion does nothing visible. It returns its subject so you can keep
going, and that is the whole cost of it — a comparison and a return.

## Different values, different catalogues

You do not memorise a global list; you type `expect(value).` and read what your
editor offers.

```python
from lovely_assertions import expect

expect("hello").is_lower()  # a string subject knows about case
expect(3.5).is_positive()  # a number subject knows about sign
expect([1, 2]).contains_no_duplicates()  # a collection subject knows about duplicates
expect({"a": 1}).contains_value(1)  # a mapping subject knows about values
print("each of these exists only where it makes sense")
```

```text
each of these exists only where it makes sense
```

A large shared core sits under all of them: `is_equal_to`, `is_none`,
`is_instance_of` and their neighbours are on every subject. What the value's type
buys you is what gets added on top of that.

`expect("hello").is_positive()` is not a runtime surprise waiting for you — it is
an error your type checker reports before you run anything, because
`StringExpect` has no such method. Which subject a value gets is decided by
[one ordered table](../concepts/typed-dispatch.md), and the full catalogue for each
is in [the reference](../reference/assertions.md).

## Saying why

Any assertion takes `because=`. Your reason is appended to the end of the
sentence rather than spliced into it, so it cannot break the message. Word it as
a lower-case clause with no trailing full stop: the library ends the sentence
itself, so a full stop of your own comes out doubled. A leading "because" is
stripped, so writing one is harmless and pointless.

```python
from lovely_assertions import expect, AssertionFailure

basket_total = 0
try:
    expect(basket_total).is_greater_than(0, because="an empty basket cannot ship")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected basket_total to be greater than 0, but was 0 because an empty basket cannot ship.
```

Use it for the fact a reader of the failure would otherwise have to go and find:
the rule, the ticket, the invariant. Do not use it to restate the assertion —
`because="it should be greater than zero"` adds a line and no information.

A string literal there is free: the library never reads it unless the assertion
fails. An expression is not — `because=explain()` is an ordinary argument, so
Python runs it on every pass. Keep it a literal, and leave it in.

## Chaining

Every assertion returns something you can keep asserting on — usually the same
subject, sometimes a narrower one — so they compose left to right. `and_` is a
no-op property that exists only to make the chain read as a sentence.

```python
from lovely_assertions import expect

hostname = "db-01.internal"
expect(hostname).starts_with("db-").and_.ends_with(".internal").and_.has_length(14)
print("chained")
```

```text
chained
```

The chain stops at the first failure, exactly as separate statements would. To
collect *every* failure in a block instead, see
[soft assertions](../guides/soft-assertions.md).

## In a test

There is no plugin, no fixture and no base class. `expect` is a function you
import, and its failures are `AssertionError` subclasses, so pytest, `unittest`
and anything else that understands a failed assertion already understand these.

```python
from dataclasses import dataclass, field

from lovely_assertions import expect


@dataclass
class Order:
    id: str
    lines: list[str] = field(default_factory=list)
    total: int = 0


def test_a_new_order_is_not_shippable() -> None:
    order = Order(id="ord-118")

    expect(order.id).starts_with("ord-")
    expect(order.lines).is_empty()
    expect(order.total).is_equal_to(0, because="nothing has been added yet")


test_a_new_order_is_not_shippable()
print("passed")
```

```text
passed
```

Mix it freely with plain `assert`. This library is not a framework you commit to
— it is a function, used where it earns its place and skipped where a bare
`assert x == y` already says everything.

## What to read next

- [Reading a failure](reading-failures.md) — the half of the library you bought it for.
- [Chaining and narrowing](chaining-and-narrowing.md) — how types flow through a chain.
- [Any value](../guides/any-value.md) — the assertions available on *every* subject.
