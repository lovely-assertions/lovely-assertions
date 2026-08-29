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
`has_attribute(...).which` hands you the **descriptor**, not a computed value —
you are asking about the class, not an instance.

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
abstract methods", which is the property that actually stops you instantiating
it. The message names the method.

### Callables

`TypeExpect` extends `CallableExpect`, so a class also has `raises`,
`raises_exactly`, `does_not_raise`, `warns` and `does_not_warn` — for asserting
about the constructor. See [exceptions](exceptions.md).

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
members of unrelated enums can match where `is_equal_to` correctly says they are
different objects. Both answers are right; pick the question you meant.

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

The flag assertions raise `TypeError` on a plain `Enum` or a foreign `Flag` — a
caller mistake, not a finding.

## The gotcha worth knowing

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

The alternative — plain enums here, mixin enums with their mixin's catalogue —
would make the subject depend on a choice the enum's *author* made, which nobody
reading a test can be expected to hold in their head. It would also put
`has_name` and `has_value` out of reach on exactly the enums people write most.

The cost is paid where it is cheapest: this is a **checker error**, not a runtime
surprise. `is_equal_to`, `is_in` and `is_one_of` are on the generic subject and
still work, and asking for the mixin's catalogue is one unambiguous move:

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

An **alias** resolves to its canonical member, so `has_name` reports the
canonical spelling rather than the one you wrote.

---

**See also:** [any value](any-value.md) · [typed dispatch](../concepts/typed-dispatch.md) ·
[exceptions](exceptions.md)
