# Extending

Your domain has assertions this library cannot have: `is_shippable`,
`is_settled`, `has_valid_signature`. Write them, and they get subject naming,
soft scopes, `because=` and the whole inherited catalogue — the same machinery
the built-in assertions use, because it *is* the same machinery.

## A subject of your own

```python
from typing import Self

from lovely_assertions import Expect, custom_assertion, expect, AssertionFailure


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __repr__(self) -> str:
        return f"Money({self.cents})"


class MoneyExpect(Expect[Money]):
    __slots__ = ()

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents} cents", because)


refund = Money(-50)
try:
    expect(refund, as_=MoneyExpect).is_positive()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected refund to be positive, but was -50 cents.
```

Note what you did not have to write: the word `Expected`, the subject's name, the
full stop. Those are added in one place, which is what makes everything below
work for your assertion without you wiring any of it up.

And `because=` already works:

```python
from typing import Self

from lovely_assertions import Expect, custom_assertion, expect, AssertionFailure


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyExpect(Expect[Money]):
    __slots__ = ()

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents} cents", because)


refund = Money(-50)
try:
    expect(refund, as_=MoneyExpect).is_positive(because="refunds are stored positive")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected refund to be positive, but was -50 cents because refunds are stored positive.
```

## The five rules

**1. Subclass `Expect[T]` and give it `__slots__ = ()`.** A subject holds one
attribute and is allocated once per assertion; a `__dict__` on each one is
measurable across a real suite.

**2. Decorate every assertion with `@custom_assertion`.** Without it, your
method's own frame is taken for the caller's, and the message names a local of
yours instead of the variable the test asserted on:

```python
from typing import Self

from lovely_assertions import Expect, expect, AssertionFailure


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class Unmarked(Expect[Money]):
    __slots__ = ()

    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail("to be positive", because)


refund = Money(-50)
try:
    expect(refund, as_=Unmarked).is_positive()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to be positive.
```

`the value` instead of `refund`. The decorator is signature-transparent — it
keeps your exact type, `Self` return and keyword-only `because` included.

**3. Test, then `return self` — or `self._fail(...)`.** In that order. A passing
assertion must be a comparison and a return, so build the message **inside** the
failure branch. Passing an f-string as an *argument* to a helper builds it on the
happy path too, which is the mistake this rule exists to prevent:

<!-- docs-test: skip - shows the wrong shape, so running it would prove nothing -->

```python
# Wrong: the message is built on every call, passing or failing.
return self._check(self._subject.cents > 0, f"to be positive, but was {...}")
```

**4. Write the *middle* of a sentence.** Lower case, no leading `Expected`, no
trailing full stop, and say both halves — what you wanted **and** what was there.
`"to be positive"` is half a message; `"to be positive, but was -50 cents"` is a
whole one. See [the grammar](../concepts/failure-messages.md).

**5. Accept `because: str = ""` as keyword-only, and pass it to `_fail`.** Users
expect it on every assertion, including yours.

## Two ways to reach your subject

### `as_=` — explicit and statically typed

<!-- docs-test: skip - the call shape on its own, shown in full in the examples above -->

```python
expect(refund, as_=MoneyExpect).is_positive()
```

A type checker knows exactly what comes back, so completion and narrowing work
exactly as they do for the built-in subjects. **This is the route to prefer.**

### `register()` — automatic, and not statically narrowable

<!-- docs-test: expect-error - register() is invisible to a checker, which is exactly what this section documents -->

```python
from typing import Self

from lovely_assertions import Expect, custom_assertion, expect, register, AssertionFailure


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyExpect(Expect[Money]):
    __slots__ = ()

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents} cents", because)


register(Money, MoneyExpect)

refund = Money(-50)
try:
    expect(refund).is_positive()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected refund to be positive, but was -50 cents.
```

A plain `expect(refund)` now builds a `MoneyExpect` **at runtime**. A type
checker still reads the declared overload set and says `Expect[Money]`, so
`is_positive` is a checker error even though it works. That is a limitation of
the language rather than an oversight — no checker can see a runtime
registration — and it is why `as_=` exists.

Use `register()` when the values arrive from somewhere the annotations do not
reach, and `as_=` when you want the checking.

### Registration is refused twice over

<!-- docs-test: expect-error - registering over a built-in, refused by the checker as well as at runtime -->

```python
from lovely_assertions import Expect, register


class Money:
    __slots__ = ()


class MoneyExpect(Expect[Money]):
    __slots__ = ()


register(Money, MoneyExpect)
try:
    register(Money, MoneyExpect)
except ValueError as error:
    print(error)

try:
    register(str, MoneyExpect)
except ValueError as error:
    print(error)
```

```text
Money is already registered
str already has a subject; registering over it would put the runtime out of step with the static overloads of expect(), which go on answering StringExpect. Use expect(value, as_=YourExpect) where you need your own, or subclass StringExpect and register a type that has no subject yet
```

Registering *over* a built-in would make the runtime disagree with the overload
chain — the one thing [the dispatch design](../concepts/typed-dispatch.md) cannot
survive.

## Assertions that find something

Return a `Found` when your assertion locates a value the caller may want to keep
asserting on. `Found[P, V]` gives them `.and_` (back to your subject), `.which`
(a subject over the found value) and `.subject` (the raw value):

```python
from typing import Self

from lovely_assertions import Expect, Found, custom_assertion, expect


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyExpect(Expect[Money]):
    __slots__ = ()

    @custom_assertion
    def has_cents(self, expected: int, /, *, because: str = "") -> "Found[Self, int]":
        if self._subject.cents == expected:
            return Found(self, self._subject.cents)
        return self._fail_narrowing(
            f"to have {expected} cents, but had {self._subject.cents}", because
        )

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents} cents", because)


expect(Money(50), as_=MoneyExpect).has_cents(50).and_.is_positive()
print("found, then continued")
```

```text
found, then continued
```

Use `_fail_narrowing` rather than `_fail` on an assertion that was supposed to
produce a narrowed subject: there is no narrowed subject to return, so a soft
scope gets a stand-in that absorbs the rest of the chain instead of a wrapper
whose static type is now a lie.

`Found`'s third parameter lets you promise what `.which` hands back —
`Found[Self, str, StringExpect]`. **It is a promise, not a proof**: nothing ties
it to the value type, so declaring one thing and returning another type-checks
and then raises `AttributeError`. That is your responsibility, and
[the reasoning is recorded](../concepts/typing-divergences.md#founds-third-parameter-is-a-promise-not-a-proof).

## Making your types read well in messages

Independently of assertions, teach every message how your types render:

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

Full detail in [Controlling output](controlling-output.md).

## What you inherit

Everything on [`Expect[T]`](any-value.md): `is_equal_to`, `is_none`, `satisfies`,
`described_as`, `.and_`, `.subject`, and the rest. You can also subclass a
*specific* subject — `class OrderListExpect(SequenceExpect[Order])` — and inherit
the whole sequence catalogue alongside your own assertions.

And everything cross-cutting works without you doing anything:
[soft scopes](soft-assertions.md) collect your failures,
[`formatting()`](controlling-output.md) bounds your rendered values, and
`because=` attaches to your sentence. All of it because there is exactly one
place a failure is reported, and you called it.

## Gotcha: `@custom_assertion` on a plain function

The decorator tells the name recovery to skip *your* frame and look at the
caller's. That works for a method on a subject. On a standalone helper function
that wraps an assertion, there is no subject-building call in the caller's
statement to recover, so the name is lost entirely rather than improved. Write
domain assertions as methods on a subject.

---

**See also:** [failure messages](../concepts/failure-messages.md) ·
[typed dispatch](../concepts/typed-dispatch.md) ·
[controlling output](controlling-output.md)
