# Types and enums

Two subjects that both come up when you are asserting about *shape* rather than
about a value.

## Classes: `TypeExpect`

`expect(SomeClass)` gives you a `TypeExpect` — a class is a class before it is
anything else, callable or iterable though it may be:

```python
from enum import Enum

from lovely_assertions import expect


class Colour(Enum):
    RED = "red"


print(type(expect(Colour)).__name__, type(expect(int)).__name__)
```

```text
TypeExpect TypeExpect
```

### Inheritance

```python
from lovely_assertions import expect, AssertionFailure


class Base:
    pass


class Child(Base):
    pass


expect(Child).is_subclass_of(Base)

try:
    expect(Child).is_subclass_of(str)
except AssertionFailure as failure:
    print(failure)

try:
    expect(Child).is_not_subclass_of(Base)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Child to be a subclass of str, but it inherits from Base, object.
Expected Child not to be a subclass of Base, but Base is one of its base classes.
```

The first message **lists the actual bases**, which is usually where the answer
is. `is_subclass_of` takes one type, never a tuple.

### Protocols

```python
from typing import Protocol, runtime_checkable

from lovely_assertions import expect, AssertionFailure


@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...


class Child:
    pass


try:
    expect(Child).implements(Closeable)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Child to implement Closeable, but it does not define 'close'.
```

It names the **missing member**, not just "does not implement".

The protocol must be `@runtime_checkable`, or this raises `TypeError` at the call
— that is Python's rule, not this library's, and it is a caller mistake rather
than a finding about the class. A *data* protocol (one with non-method members)
cannot be checked against a class at all, even when decorated.

### Members

```python
from lovely_assertions import expect, AssertionFailure


class Child:
    pass


try:
    expect(Child).has_method("close")
except AssertionFailure as failure:
    print(failure)

try:
    expect(Child).has_attribute("timeout")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Child to have a method 'close', but no such attribute is defined on the class.
Expected Child to have the attribute 'timeout', but no such attribute is defined on the class.
```

`does_not_have_attribute` and `does_not_implement` are the complements.
`has_attribute(...).which` hands you what `getattr` on the class returns: the
value for a plain attribute, and the `property` object itself for a property —
there is no instance for it to compute one from. An attribute assigned in
`__init__` belongs to instances and is not found here at all.

### Abstractness

```python
from abc import ABC, abstractmethod

from lovely_assertions import expect, AssertionFailure


class Storage(ABC):
    @abstractmethod
    def put(self) -> None: ...


try:
    expect(Storage).is_not_abstract()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Storage not to be abstract, but it leaves 'put' unimplemented.
```

`is_abstract` is not "was declared with `ABC`" — it is "has unimplemented
abstract methods", and the message names them. It is not a claim about
instantiability: a `Protocol` leaves nothing unimplemented and still refuses
construction, and so does any class whose `__init__` turns callers away. For
"this cannot be built", reach for `expect(Storage).raises(TypeError)`, which
makes the call.

### Callables

`TypeExpect` extends `CallableExpect`, so a class also has `raises`,
`raises_exactly`, `does_not_raise`, `warns` and `does_not_warn` — for asserting
about the constructor. The assertion does the calling itself, and it calls with
no arguments, so it asks about a constructor that takes none. Where the
constructor takes arguments, wrap it:
`expect(lambda: Order(-1)).raises(ValueError)`. Left unwrapped,
`expect(Order).raises(TypeError)` passes on the argument you did not supply
rather than on anything the test meant. See [exceptions](exceptions.md).

## Enum members: `EnumExpect`

```python
from enum import Enum

from lovely_assertions import expect, AssertionFailure


class Colour(Enum):
    RED = "red"
    GREEN = "green"


expect(Colour.RED).has_name("RED").and_.has_value("red")

try:
    expect(Colour.RED).has_name("GREEN")
except AssertionFailure as failure:
    print(failure)

try:
    expect(Colour.RED).has_value("green")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Colour.RED to be named 'GREEN', but Colour.RED is named 'RED'.
Expected Colour.RED to have value 'green', but Colour.RED has value 'red'.
```

`does_not_have_name` and `does_not_have_value` are the complements.

An **alias** is a second spelling of one member, not a member of its own. Add
`CRIMSON = "red"` to `Colour` and `Colour.CRIMSON` *is* `Colour.RED`, so
`has_name("CRIMSON")` fails and `does_not_have_name("CRIMSON")` passes. The
failure names `Colour.RED`, which is the member it was handed.

### Comparing across enumerations

```python
from enum import Enum

from lovely_assertions import expect, AssertionFailure


class Colour(Enum):
    RED = "red"
    GREEN = "green"


try:
    expect(Colour.RED).has_same_value_as(Colour.GREEN)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Colour.RED to have the same value as Colour.GREEN, but had value 'red' rather than 'green'.
```

`has_same_value_as` and `has_same_name_as` compare *across* enumerations, so two
members of unrelated enums can match where `is_equal_to` says they differ. That
last part holds for a plain `Enum` like `Colour` only: an `IntEnum` or `StrEnum`
member compares equal to anything carrying the same payload, so `is_equal_to`
matches it against a member of an unrelated enumeration — and against the bare
`1` or `"red"` it wraps. `is_same_as` is the one that always tells two members
apart.

### Flags

```python
from enum import Flag, auto

from lovely_assertions import expect, AssertionFailure


class Perm(Flag):
    READ = auto()
    WRITE = auto()


expect(Perm.READ | Perm.WRITE).has_flag(Perm.READ)

try:
    expect(Perm.READ).has_flag(Perm.WRITE)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Perm.READ to have flag Perm.WRITE, but was Perm.READ.
```

A **composite** operand is all-or-nothing: `has_flag(READ | WRITE)` requires
both, so `does_not_have_flag(READ | WRITE)` passes for a value holding only
`READ`. And the empty flag is a subset of everything, so `has_flag(Perm(0))`
asserts nothing while `does_not_have_flag(Perm(0))` can never pass.

"Either of these" is a different claim and gets a different spelling:
`satisfies_any(lambda it: it.has_flag(Perm.READ), lambda it: it.has_flag(Perm.WRITE))`,
one branch per flag.

The flag assertions raise `TypeError` on a plain `Enum` or a foreign `Flag` — a
caller mistake, not a finding.

### `IntEnum` and `StrEnum` members

**An enum member is an enum before it is anything else.** An `IntEnum` member
really is an `int`, and a `StrEnum` member really is a `str`, but both get
`EnumExpect`:

<!-- docs-test: expect-error - the checker error IS the lesson: an enum member does not get the numeric catalogue -->

```python
from enum import IntEnum

from lovely_assertions import expect


class Level(IntEnum):
    LOW = 1
    HIGH = 2


print(type(expect(Level.LOW)).__name__)
try:
    expect(Level.LOW).is_greater_than(0)
except AttributeError as error:
    print(error)
```

```text
EnumExpect
'EnumExpect' object has no attribute 'is_greater_than'
```

You find this out from the checker rather than from a failing test — run it
anyway and you get the `AttributeError` above.
[Typed dispatch](../concepts/typed-dispatch.md) has the reason the order is this
way.

`is_equal_to`, `is_in` and `is_one_of` are on the generic subject and still work,
and asking for the mixin's catalogue is one unambiguous move:

```python
from enum import IntEnum

from lovely_assertions import expect


class Level(IntEnum):
    LOW = 1
    HIGH = 2


expect(Level.LOW.value).is_greater_than(0)
print("the mixin's catalogue, asked for explicitly")
```

```text
the mixin's catalogue, asked for explicitly
```

---

**See also:** [any value](any-value.md) · [typed dispatch](../concepts/typed-dispatch.md) ·
[exceptions](exceptions.md)
