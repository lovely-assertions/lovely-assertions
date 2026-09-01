# Structural equivalence

`is_equal_to` asks one question — `__eq__` — and a great many Python types answer
it by identity, by type, or not at all.

`is_equivalent_to` asks a different one: **do these two graphs hold the same
information?**

```python
from dataclasses import dataclass

from lovely_assertions import expect


@dataclass
class Address:
    city: str
    postcode: str


@dataclass
class Customer:
    name: str
    address: Address


saved = Customer("Ada", Address("Lyon", "69001"))
expect(saved).is_equivalent_to(Customer("Ada", Address("Lyon", "69001")))
print("equivalent")
```

```text
equivalent
```

It walks both sides member by member and understands dataclasses, `NamedTuple`s,
`attrs` classes and pydantic models, mappings and collections, and anything else
with `__slots__` or a `__dict__`. Neither `attrs` nor pydantic is imported to do
it — the shapes are recognised by what they leave on the class.

## Why not just `==`

Three situations where `==` is the wrong question:

- The object never defined `__eq__`, so `==` is identity and a perfectly correct
  result compares unequal to itself-rebuilt.
- The values carry fields nobody is testing — a generated `id`, a `created_at`.
- The difference you want reported is *several* differences, and `==` gives you
  one boolean.

## Many differences at once, each with a path

```python
from dataclasses import dataclass

from lovely_assertions import expect, AssertionFailure


@dataclass
class Address:
    city: str
    postcode: str


@dataclass
class Customer:
    name: str
    address: Address


saved = Customer("Ada", Address("Lyon", "69001"))
try:
    expect(saved).is_equivalent_to(Customer("Ada", Address("Paris", "75001")))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected saved to be equivalent to Customer(name='Ada', address=Address(city='Paris', postcode='75001')).
  address.city: 'Lyon' instead of 'Paris'
  address.postcode: '69001' instead of '75001'
  (compared with strict ordering, maximum depth 10)
```

Two findings, each with the **dotted path** that locates it in the graph — and
the trailing line states the configuration it compared under, so you are never
guessing which rules were in force. A path from a failure message is a path you
can paste into `excluding_path`.

Ten differences are printed and two hundred are collected. Past either bound the
message says so on its own line — `... (n more differences)`, `... (the
comparison stopped at 200 differences)`. `formatting(max_items=...)` raises the
first; see [controlling output](controlling-output.md#bounds-formatting). The
second is not an option, because a caller who could raise it could hang a test
run.

`is_not_equivalent_to` is the complement, and takes the same `options=`. Use it
to assert that a transformation actually changed something — a redaction that
redacted, a normalisation that normalised.

## Configuring it

`equivalency()` builds an immutable options object. Every method returns a new
one, so a configuration can be named at module scope and shared across a suite
without a test being able to change it underneath another.

```python
from lovely_assertions import expect, equivalency

created_response = {"id": "6f1e", "created_at": "2026-01-04", "email": "ada@example.com"}

expect(created_response).is_equivalent_to(
    {"id": "whatever", "created_at": "whenever", "email": "ada@example.com"},
    options=equivalency().excluding("id", "created_at"),
)
print("ignored the generated fields")
```

```text
ignored the generated fields
```

`excluding("id")` drops the field from the comparison and so asserts nothing
about it; a [matcher](matchers.md) keeps it and checks its shape, so
`{"id": any_instance_of(int)}` still says the id is an integer. Exclude what the
test has no opinion about, match what it does.

By default the expectation is a **subset** *of a record*: fields the subject has
and the expectation does not mention are ignored, and fields the expectation
names and the subject lacks are reported. The two options below move each of
those independently.

A **mapping is decided the other way, and neither option touches it**: both
directions are always reported, so an unexpected key fails. A record is a shape
you declared and a mapping is data you were handed, and a stray key in the second
is the more likely bug.

| Method | Effect |
|---|---|
| `excluding(*names)` | ignore members by name, at any depth |
| `excluding_path(*paths)` | ignore these paths **and everything beneath them**, e.g. `address` |
| `including(*names)` | compare only these members — `excluding` still wins where the two disagree |
| `excluding_missing()` | ignore members the **expectation** names that the subject does not have |
| `ignoring_order()` | compare collections as multisets |
| `with_max_depth(n)` | descend at most `n` levels; below that, compare with `==` |
| `using(kind, comparator)` | compare values of `kind` with your own function |
| `comparing_all_members()` | also fail on members the **subject** has that the expectation does not mention |
| `comparing_enums_by_name()` | match enum members by name rather than value |

The depth default is ten levels — the `maximum depth 10` every failure message on
this page is reporting. Below it the walk stops taking values apart and compares
with `==` instead, and says so where that comparison fails: `(not taken apart:
the maximum depth of 10 stops here)`. A graph deeper than ten whose leaves never
defined `__eq__` therefore fails against a rebuilt copy of itself — the very case
equivalence exists to cure — until `with_max_depth()` is raised past it.

### Order

**Strict ordering is the default**, which is deliberately the opposite of
FluentAssertions:

```python
from lovely_assertions import expect, equivalency, AssertionFailure

response = {"tags": [1, 2]}
try:
    expect(response).is_equivalent_to({"tags": [2, 1]})
except AssertionFailure as failure:
    print(failure)
```

```text
Expected response to be equivalent to {'tags': [2, 1]}.
  tags[0]: 1 instead of 2
  tags[1]: 2 instead of 1
  (compared with strict ordering, maximum depth 10)
```

```python
from lovely_assertions import expect, equivalency

response = {"tags": [1, 2]}
expect(response).is_equivalent_to({"tags": [2, 1]}, options=equivalency().ignoring_order())
print("and now it passes")
```

```text
and now it passes
```

A list has an order; ignoring it silently would let a genuinely reordered result
pass. Ask for `ignoring_order()` where order is not part of the contract.

### Tolerance

`close_within` builds a comparator for `using`, and covers floats and datetimes
with one function because Python already makes them one problem:

```python
from lovely_assertions import expect, equivalency, close_within

measured = {"ratio": 0.1 + 0.2}
expect(measured).is_equivalent_to(
    {"ratio": 0.3},
    options=equivalency().using(float, close_within(1e-6)),
)
print("close enough")
```

```text
close enough
```

The same works for `datetime` with a `timedelta` tolerance — two timestamps a
millisecond apart, which is the commonest reason a perfectly correct result fails
an equality test.

## Gotchas

### The kinds have to match

A dataclass is never equivalent to a `dict`, however identical their contents:

```python
from dataclasses import dataclass

from lovely_assertions import expect, AssertionFailure


@dataclass
class Address:
    city: str
    postcode: str


try:
    expect(Address("Lyon", "69001")).is_equivalent_to({"city": "Lyon", "postcode": "69001"})
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Address("Lyon", "69001") to be equivalent to {'city': 'Lyon', 'postcode': '69001'}.
  the value itself: types differ: Address instead of dict
  (compared with strict ordering, maximum depth 10)
```

A record and a mapping are different kinds of thing, and treating them as
interchangeable would make it impossible to assert that a serialiser actually
serialised. **Records of two unrelated classes** *are* compared member by member,
though — it is the record/mapping boundary that is kept, not the class.

Sequences are more relaxed: a list is equivalent to a tuple, since both are
ordered sequences of the same items.

### Equality settles equivalence

Two values that are `==` hold the same information, so the walk stops there and
reports nothing. That is not only an optimisation — it is what keeps equivalence
from being *stricter* than equality, which would be the one pair of answers
nobody could make sense of: the weaker assertion failing where the stronger one
passes.

The practical consequence: a type with a deliberately lenient `__eq__` passes
`is_equivalent_to` for the same reason it passes `is_equal_to`.

Two options escape that, because they are asked **before** `==` rather than after
it. `using(kind, comparator)` replaces equality for the types you register, so a
comparator narrower than `==` refuses a pair that Python would call equal. So
does `comparing_enums_by_name()`: two `IntEnum` members sharing a value under
different names are equal to Python and are *not* equivalent here.

Every other option only widens what counts as equivalent. These two replace it,
which is why they can be stricter.

### It never raises because of a value

A property that explodes, a `__repr__` that lies, an `__eq__` that throws, a
structure that contains itself: each costs you detail in the report and none
turns your failing test into an error raised inside the assertion library. The
guards are per member, so one hostile field of a twelve-field record costs that
field and not the other eleven.

Three things do raise, and none is a property of one value. A *misconfigured
call* raises at the call, where the mistake is. An **unordered** comparison that
runs out of its pairing allowance gives up with a `ValueError` rather than
answering: an unfinished matching is not a verdict in either direction, and
silently calling it equivalent would be the dangerous way to fail. And a walk
that uses up the interpreter's stack before it finishes raises `ValueError` for
that same reason — lower `with_max_depth()`, compare a smaller part of the
graph, or raise `sys.setrecursionlimit()`.

The pairing allowance runs to a couple of hundred items on each side that nothing
pairs off by equality, or a few thousand unhashable ones in the cheap `==` pass
that runs before it. A `set` is matched without regard to order whatever the
options say, so a set whose items mostly *fail* to pair off is the case to watch:
the cost is in the leftovers, not in the size. Two hundred thousand ints
differing in one place answer at once; two hundred and fifty records that pair
with nothing exhaust it — compare fewer items in one call.

### A name nothing carries selects nothing

`including("totl")` selects no member, and two records with no selected member
between them are equivalent — so the typo passes, silently, having compared
nothing. `excluding` every field gives the same answer. Only `excluding_path("")`
is refused at the call, because that one names the root and can be caught there.
Spell these names against the paths a failure message prints.

### An index path stops working once order is ignored

`excluding_path("tags[1]")` names a position, and `ignoring_order()` removes
positions. Use `excluding` by name, or keep the ordering strict.

---

**See also:** [matchers](matchers.md) for per-field placeholders ·
[any value](any-value.md) · [mappings](mappings.md)
