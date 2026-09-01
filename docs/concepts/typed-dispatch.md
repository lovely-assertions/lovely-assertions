# Typed dispatch

How a value becomes a subject, why the order matters, and what keeps the static
answer and the runtime answer the same.

> Looking for **which** subject a given value gets? That table is in the
> reference: [Which subject you get](../reference/assertions.md#which-subject-you-get).
> This page is about how it works and why it is built that way.

## `expect()` is a function, not a class

The obvious design is a class you construct: `Expect("hello")`. It is not as
impossible as it looks — `__new__` can be overloaded, and both checkers will
happily tell you that `Expect("hello")` is a `StringExpect`.

What breaks is **your** subclasses. Constructing one routes through the base's
dispatch, so `MoneyExpect(some_money)` hands back whatever the dispatch decided
for that value — not a `MoneyExpect`. A library whose extension story is
`class MoneyExpect(Expect[Money])` cannot have a base class that hijacks
construction.

So `expect()` is an **overloaded function** instead. Its declared return type
varies with its argument's type, and that is what your editor reads to decide
what to offer after the dot:

```python
from lovely_assertions import expect

print(type(expect("hello")).__name__)
print(type(expect(3)).__name__)
print(type(expect([1, 2])).__name__)
print(type(expect({"a": 1})).__name__)
```

```text
StringExpect
NumericExpect
SequenceExpect
MappingExpect
```

Each of those is a real class with its own catalogue, all descending from
`Expect[T]`, so the generic assertions are inherited once and the specific ones
are added where they belong.

## One table, written twice

There is a static half and a runtime half, and they have to agree:

- **The static half** — the `@overload` chain on `expect()`. This is what a type
  checker reads, and it is the only thing your editor consults.
- **The runtime fast path** — an exact-type table, keyed on `type(value)` by
  identity, so the four calls above are decided by a dict lookup rather than by
  the chain below. A subclass of a built-in is not an exact match and falls
  through.
- **The runtime fallback** — an ordered `if`/`elif` chain for everything the
  table misses: subclasses, ABCs, and your own types.

The two sides are one table written twice: whichever of its two routes the
runtime takes, it has to land on the subject the overloads promised. If they
drift, a checker promises one catalogue while the runtime builds another, and you
get an `AttributeError` on a line that type-checked — precisely the failure this
library exists to prevent. Changing one without the other is the single easiest
way to break the package.

## First match wins, narrow before broad

The overload chain and the runtime fallback are both ordered, and the first match
wins. The order is the mechanism, not tidiness, because Python's type hierarchy
overlaps in ways that would otherwise give the wrong answer:

| Because | The dispatch has to |
|---|---|
| `bool` is a subclass of `int` | put `bool` before `int \| float` in the overloads, and give it a row in the exact-type table — the fallback chain behind that table answers `NumericExpect` |
| `str` is a `Sequence[str]` | put `str` before `Sequence`, or `expect("x")` is a `SequenceExpect[str]` |
| an `IntEnum` member is an `int` | put enums before numbers, or `has_name` is out of reach |
| an `Enum` class is iterable through its metaclass | put classes before collections |
| a `Mapping` is a `Collection` | put `Mapping` before `Sequence` before `Collection` |

```python
from lovely_assertions import expect

print(type(expect(True)).__name__)
print(type(expect(1)).__name__)
print(type(expect("x")).__name__)
print(type(expect(b"x")).__name__)
print(type(expect({1, 2})).__name__)
```

```text
BoolExpect
NumericExpect
StringExpect
SequenceExpect
CollectionExpect
```

`bytes` landing on `SequenceExpect` is worth a second look: `bytes` really is a
`Sequence[int]`, so its elements are integers, and `expect(b"abc").contains(97)`
is the assertion that follows from that.

## Types the library refuses to import

`expect()` answers correctly for `datetime`, `Path`, `Enum`, `Decimal` and
`Fraction` **without importing** `datetime`, `pathlib`, `enum`, `decimal` or
`fractions`. Importing this package must not drag in modules your test session
was not going to use, so those subjects are typed against their types under
`TYPE_CHECKING` and matched by name at runtime.

The consequence is a good one: a test suite that never mentions a `Path` never
pays for `pathlib` because of this library.

## The dispatch remembers

Resolving a type walks a chain of checks. Doing that on every `expect()` call
would be waste, so the answer is remembered per type — and remembering has to be
*sound*, because the answer really can change underneath you.

Most of the chain reads a fixed MRO: `issubclass` cannot change its mind once a
type exists. But `Sequence.register(YourClass)` genuinely does change the answer
after the fact. Every such registration bumps `abc.get_cache_token()` — which is
exactly what that token is for, and what `functools.singledispatch` guards on —
so when it moves, the remembered answers are discarded rather than reasoned
about.

## The one place the two halves do not agree

A mock. `unittest.mock`'s `NonCallableMock` has an `Any` in its MRO in typeshed,
which makes a mock statically assignable to *every* parameter type:

```python
from unittest.mock import Mock

flag: bool = Mock()  # a type checker accepts this
count: int = Mock()  # and this
print("a mock satisfies every type")
```

```text
a mock satisfies every type
```

Every concrete overload of `expect()` therefore accepts a mock, so an overload
written for mocks has to lead the chain to be reached at all — and one that does
lead it overlaps a great many of the others, which pyright reports per pair. The
static answer is bought with a pile of suppressions and is only useful where a
parameter is *declared* `Mock`, which in a real suite it often is not.

So the library ships no static overload, and the runtime is left to be right on
its own: it checks for a mock first and builds a `MockExpect`. Leaving the
runtime wrong as well would cost something real and buy nothing.

```python
from unittest.mock import Mock
from lovely_assertions import expect

print(type(expect(Mock())).__name__)
```

```text
MockExpect
```

When you want the static answer too, name it: `expect(fetch, as_=MockExpect)`.
See [Mocks](../guides/mocks.md).

## Your own types

Two routes reach a subject of your own, and the difference between them is a
dispatch question.

**`as_=` is an overload of `expect()` itself.** The checker knows exactly what
comes back — `expect(order, as_=OrderExpect)` is an `OrderExpect` statically and
at runtime — so there is no second table to keep in step.

**`register()` moves the runtime table only.** No checker reads a runtime
registration, so a plain `expect(order)` builds your subject when the test runs
while a checker goes on saying `Expect[Order]`. Registering *over* a built-in is
refused outright: it would make the runtime answer differently from the overload
chain, which is the one disagreement this design cannot survive.

Both routes, with a worked subject, are in [Extending](../guides/extending.md).

---

See also: [Design goals](design-goals.md) · [Performance](performance.md) ·
[Type-checker divergences](typing-divergences.md)
