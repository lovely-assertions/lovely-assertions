# Assertion reference

Every assertion in `lovely-assertions`, grouped by the subject it belongs to,
with the signature and the one-line description taken from the code.

> **This file is generated.** `scripts/generate_reference.py` parses
> `src/lovely_assertions/`, calls `expect()` to fill the dispatch table, and
> *runs* every example below to quote the message it produces. Regenerate it
> rather than editing it: a hand-edit is lost on the next run, and a reference
> that has drifted from the code is worse than no reference at all.

## How to read this

`expect(x)` wraps `x` in the subject that knows how to assert on it, chosen by
the type of `x`. That is the entire entry point.

```python
from datetime import date
from pathlib import Path

from lovely_assertions import expect

expect("hello").starts_with("he").and_.has_length(5)
expect([3, 1, 2]).has_length(3).and_.contains(2)
expect({"host": "db-01"}).contains_key("host").whose_value.is_equal_to("db-01")
expect(7).is_between(1, 10)
expect(date(2024, 3, 16)).is_weekend()
expect(Path("build/report.txt")).has_suffix(".txt")
```

Four things hold everywhere, so they are said once here instead of on every
line below.

**Every assertion takes a keyword-only `because`.** It defaults to `""`, it
reaches the message only on failure, and it attaches at the end of the
sentence. It is an ordinary argument, so whatever you interpolate into it is
computed whether or not the assertion fails — keep it cheap. Write it with or
without the leading word — neither reads "because because".

```python
from lovely_assertions import expect

retries = 5
expect(retries).is_less_than(3, because="the backoff caps at three attempts")
```

```
Expected retries to be less than 3, but was 5 because the backoff caps at three attempts.
```

**A message can run to more than one line.** An equality failure on a composite
value carries a difference block under the sentence — a unified diff for
multi-line text, the first offending index for a sequence, the keys that moved
for a mapping. It stays bounded, whatever the size of the two values.

```python
from lovely_assertions import expect

config = {"host": "db-01", "port": 8080, "tls": True}
expect(config).is_equal_to({"host": "db-01", "port": 9090})
```

```
Expected config to equal {'host': 'db-01', 'port': 9090}, but was {'host': 'db-01', 'port': 8080, 'tls': True}.
  values differ at key 'port': 8080 instead of 9090
  extra keys: ['tls']
```

**Every assertion returns something chainable.** Most return the subject itself,
so assertions stack directly. The ones that *find* a value return a
[`Found`](#continuations), and the ones that narrow return a re-typed subject.
Which it is, is in the signature.

**A failure raises `AssertionFailure`**, a subclass of `AssertionError`, so
pytest and unittest treat it as an ordinary test failure. Inside a
`soft_assertions()` block nothing is raised until the block ends.

Signatures are quoted as the source declares them: `/` closes the
positional-only parameters, `*` opens the keyword-only ones, and `self` appears
only where its annotation is load-bearing — which is how `is_not_none` says it
wants an optional subject, and how `contains_match` says it wants a sequence of
strings.

## Contents

- [Which subject you get](#which-subject-you-get)
- [Continuations](#continuations)
- [`Expect[T]`](#expectt)
- [`BoolExpect`](#boolexpect)
- [`StringExpect`](#stringexpect)
- [`OrderedExpect[T]`](#orderedexpectt)
- [`NumericExpect`](#numericexpect)
- [`CollectionExpect[E, C]`](#collectionexpecte-c)
- [`SequenceExpect[E]`](#sequenceexpecte)
- [`MappingExpect[K, V]`](#mappingexpectk-v)
- [`DateExpect[T]`](#dateexpectt)
- [`DateTimeExpect`](#datetimeexpect)
- [`TimeExpect`](#timeexpect)
- [`TimeDeltaExpect`](#timedeltaexpect)
- [`PurePathExpect[T]`](#purepathexpectt)
- [`PathExpect`](#pathexpect)
- [`EnumExpect[T]`](#enumexpectt)
- [`CallableExpect`](#callableexpect)
- [`RaisedExpect[E]`](#raisedexpecte)
- [`WarnedExpect[W]`](#warnedexpectw)
- [`TypeExpect`](#typeexpect)
- [`MockExpect`](#mockexpect)
- [Elsewhere in the public API](#elsewhere-in-the-public-api)

## Which subject you get

`expect()` is overloaded, and the overloads are **ordered**: the first one that
matches wins. The runtime dispatch walks the same order, so what a type checker
offers and what you actually get are the same thing.

| # | Matches | For example | Subject |
| --- | --- | --- | --- |
| 1 | any value, with `as_=SomeExpect` | `expect(order, as_=OrderExpect)` | whatever `as_=` names |
| 2 | `type[Any]` | `int`, a class of your own, an `Enum` class | `TypeExpect` |
| 3 | an `Enum` member | `Colour.RED`, and `IntEnum`/`StrEnum` members | `EnumExpect[T]` |
| 4 | `datetime` | `datetime(2024, 3, 16, 14, 30)` | `DateTimeExpect` |
| 5 | `date` | `date(2024, 3, 16)` | `DateExpect[T]` |
| 6 | `time` | `time(14, 30)` | `TimeExpect` |
| 7 | `timedelta` | `timedelta(minutes=90)` | `TimeDeltaExpect` |
| 8 | `Path` | `PosixPath`, `WindowsPath` | `PathExpect` |
| 9 | `PurePath` | `PurePosixPath`, `PureWindowsPath` | `PurePathExpect[T]` |
| 10 | `Decimal` | `Decimal("1.5")` | `OrderedExpect[T]` |
| 11 | `Fraction` | `Fraction(1, 3)` | `OrderedExpect[T]` |
| 12 | `bool` | `True`, `False` | `BoolExpect` |
| 13 | `str` | `"hello"`, and any `str` subclass | `StringExpect` |
| 14 | `int \| float` | `3`, `3.5`, and their subclasses | `NumericExpect` |
| 15 | `Mapping[K, V]` | `dict`, `OrderedDict`, `ChainMap`, `MappingProxyType` | `MappingExpect[K, V]` |
| 16 | `Sequence[E]` | `list`, `tuple`, `range`, `bytes`, `bytearray` | `SequenceExpect[E]` |
| 17 | `Collection[E]` | `set`, `frozenset`, and the three `dict` views | `CollectionExpect[E, C]` |
| 18 | `Callable[..., object]` | a function, a lambda, a bound method | `CallableExpect` |
| 19 | anything else | `None`, a generator, a plain object | `Expect[T]` |

The order is the mechanism, not an accident, and it reads from the narrow to
the broad. A class comes first because an `Enum` class is iterable through its
metaclass, and a class whose metaclass implements the mapping protocol is a
`Mapping`, so anything further down would claim one or the other. The enum, date
and path rows come next because an `IntEnum` member is an `int` and a `StrEnum`
member is a `str`. `bool` is a subclass of `int` and a `str` is a
`Sequence[str]`, so without the order `expect(True)` would be a `NumericExpect`
and `expect("x")` a `SequenceExpect[str]`. `Mapping` precedes `Sequence` and
`Sequence` precedes `Collection` on the same argument: each of them is one, with
more to say about itself. The bare `T` fallback is last.

One subject is missing from the table because it is missing from the overloads.
A mock is dispatched to [`MockExpect`](#mockexpect) before anything else is
looked at, and no overload can say so: typeshed puts an `Any` in
`NonCallableMock`'s MRO, which makes a mock statically assignable to every
parameter type, so the first concrete overload would always win whatever order
they were written in. The runtime is left to be right on its own, and
`expect(m, as_=MockExpect)` is the typed route.

A few results that surprise people. The subject column is the class `expect()`
actually returned when this table was generated.

| Call | Subject | Why |
| --- | --- | --- |
| `expect(b"abc")` | `SequenceExpect` | `bytes` is a `Sequence[int]`, so the elements are integers. |
| `expect(range(3))` | `SequenceExpect` | a `range` is a sequence, and is not materialised. |
| `expect({1, 2})` | `CollectionExpect` | a `set` is a `Collection` but not a `Sequence` — no indexing, no order. |
| `expect(int)` | `TypeExpect` | a class is a class before it is anything else, callable though it is. |
| `expect(Colour)` | `TypeExpect` | an `Enum` class is iterable through its metaclass, and is a class all the same. |
| `expect(Colour.RED)` | `EnumExpect` | a member is not a class, and is not a collection. |
| `expect(Decimal("1.5"))` | `OrderedExpect` | ordered, but neither an `int` nor a `float`, so it gets the ordering half. |
| `expect(Mock())` | `MockExpect` | a mock is a mock first; see the note above the table. |
| `expect(None)` | `Expect` | nothing narrower claims it. |

`register(SomeType, SomeExpect)` inserts your own subject just after the exact
built-in table, so it is consulted before the `Mapping`/`Sequence`/callable
chain. Registering *over* a built-in is refused, because it would put the
runtime out of step with the overloads above — and no checker can see a runtime
registration in any case. `expect(x, as_=SomeExpect)` is the typed route. See
[the extension guide](../guides/extending.md).

## Continuations

Four properties carry a chain from one assertion to the next. Which of them
you have depends on what the last assertion returned.

| Continuation | Appears on | Gives you |
| --- | --- | --- |
| `.and_` | every subject, and `Found` | the subject the assertion was made on, so the next one reads as a continuation of the same sentence |
| `.which` | `Found`, and `RaisedExpect` | a subject over the value the assertion *found* — the single item, the element at an index, the value under a key, the exception |
| `.whose_value` | `Found` | the same as `.which`, spelled for a key lookup |
| `.subject` | every subject, and `Found` | the raw value, re-typed |

`Found[P, V, A]` is what an assertion returns when it found something: `P` is
the subject it was made on, `V` the value it found, and `A` the subject
`.which` hands back. `A` defaults to `Expect[V]`, which is what nearly every
producer leaves it at; one that knows better says so, and
`is_instance_of(str)` returns `Found[Self, str, StringExpect]` because that is
the object `expect()` builds for a string. Its four members are the four
continuations:

- `.and_ -> P` — Continue asserting on the original subject.
- `.which -> A` — Continue asserting on the value that was found.
- `.whose_value -> A` — The mapping-flavoured spelling of `which`; the same object.
- `.subject -> V` — The value that was found, re-typed.

```python
from lovely_assertions import expect

response = {"status": "ok"}

expect(response).contains_key("status").whose_value.is_equal_to("ok")
expect(["only"]).contains_single().which.is_equal_to("only")
expect([1, 2, 3]).has_element_at(0, 1).and_.has_length(3)
expect(3).is_instance_of(int).and_.is_positive()
```

Left at that default — everywhere but `is_instance_of` and
`is_exactly_instance_of` — `.which` is declared `Expect[V]`, the generic
subject. At runtime it routes through `expect()`, so for a string the object
really is a `StringExpect`, but a checker reads the declared type and the string
catalogue is not offered. Re-bind through `.subject` and call `expect()` again
where you want it:

```python
from lovely_assertions import expect

response = {"content-type": "application/json"}

content_type = expect(response).contains_key("content-type").subject
expect(content_type).contains("json").and_.starts_with("application/")
```

The same trade is why `is_not_none()` returns `Expect[S]` rather than a
re-specialised subject; [the divergence ledger](../concepts/typing-divergences.md)
records the reasoning.

## `Expect[T]`

```python
class Expect[T]:
```

The generic subject, and the base class of every other one. `expect(x)` returns
it directly when nothing narrower claims `x` — `None`, a generator, an object of
your own — and it is what you subclass to add assertions of your own
([the extension guide](../guides/extending.md)).

The 23 assertions and two continuations below are inherited by
every other subject on this page. They are listed here once, and referred to
as *inherited* from there on.

**Continuations**

- `.subject -> T` — The value under test, re-typed by whatever narrowing has happened.
- `.and_ -> Self` — Re-chain another assertion on the same subject. A typed no-op.

**The primitive**

- `described_as(name: str, /) -> Self` — Name this subject explicitly, instead of recovering it from the source.

**Truthiness**

- `is_truthy(*, because: str = "") -> Self` — Assert `bool(subject)` is true.
- `is_falsy(*, because: str = "") -> Self` — Assert `bool(subject)` is false.

**Composition (chaining is an AND; these are the other two)**

- `satisfies_any(*branches: Callable[[Self], object], because: str = "") -> Self` — Assert at least one branch holds.
- `satisfies_none(*branches: Callable[[Self], object], because: str = "") -> Self` — Assert no branch holds — the complement of `satisfies_any`.

**Equality**

- `is_equal_to(expected: object, /, *, because: str = "") -> Self` — Assert `subject == expected`.
- `is_not_equal_to(unexpected: object, /, *, because: str = "") -> Self` — Assert `subject != unexpected`.

**Structural equivalence**

- `is_equivalent_to(expected: object, /, *, options: Equivalency | None = None, because: str = "") -> Self` — Assert the subject matches `expected` member by member, recursively.
- `is_not_equivalent_to(expected: object, /, *, options: Equivalency | None = None, because: str = "") -> Self` — Assert the subject differs from `expected` somewhere.

**Identity**

- `is_same_as(expected: object, /, *, because: str = "") -> Self` — Assert `subject is expected` — the same object, not merely an equal one.
- `is_not_same_as(unexpected: object, /, *, because: str = "") -> Self` — Assert `subject is not unexpected`.

**None (and the narrowing primitive)**

- `is_none(*, because: str = "") -> Self` — Assert the subject is `None`.
- `is_not_none[S](self: Expect[S | None], *, because: str = "") -> Expect[S]` — Assert the subject is not `None`, and hand back a subject typed without it.

**Membership**

- `is_one_of(*options: object, because: str = "") -> Self` — Assert the subject equals one of `options`.
- `is_in(container: Container[object], /, *, because: str = "") -> Self` — Assert the subject is contained in `container`.
- `is_not_in(container: Container[object], /, *, because: str = "") -> Self` — Assert the subject is not contained in `container`.

**Predicates**

- `matches(predicate: Callable[[T], bool], /, *, because: str = "") -> Self` — Assert `predicate(subject)` is true.
- `satisfies(inspector: Callable[[T], object], /, *, because: str = "") -> Self` — Assert the subject satisfies the nested assertions in `inspector`.

**Type**

- `is_instance_of[S: Enum](expected_type: type[S], /, *, because: str = ...) -> Found[Self, S, EnumExpect[S]]` or `is_instance_of(expected_type: type[bool], /, *, because: str = ...) -> Found[Self, bool, BoolExpect]` or `is_instance_of(expected_type: type[str], /, *, because: str = ...) -> Found[Self, str, StringExpect]` or `is_instance_of[S](expected_type: type[S], /, *, because: str = ...) -> Found[Self, S]` — Assert `isinstance(subject, expected_type)`; continue with `.which`.
- `is_not_instance_of(unexpected_type: type[object], /, *, because: str = "") -> Self` — Assert the subject is not an instance of `unexpected_type`.
- `is_exactly_instance_of[S: Enum](expected_type: type[S], /, *, because: str = ...) -> Found[Self, S, EnumExpect[S]]` or `is_exactly_instance_of(expected_type: type[bool], /, *, because: str = ...) -> Found[Self, bool, BoolExpect]` or `is_exactly_instance_of(expected_type: type[str], /, *, because: str = ...) -> Found[Self, str, StringExpect]` or `is_exactly_instance_of[S](expected_type: type[S], /, *, because: str = ...) -> Found[Self, S]` — Assert `type(subject) is expected_type` — a subclass does not count.
- `is_not_exactly_instance_of(unexpected_type: type[object], /, *, because: str = "") -> Self` — Assert `type(subject) is not unexpected_type`.
- `as_type[S: Enum](expected_type: type[S], /, *, because: str = ...) -> EnumExpect[S]` or `as_type(expected_type: type[bool], /, *, because: str = ...) -> BoolExpect` or `as_type(expected_type: type[str], /, *, because: str = ...) -> StringExpect` or `as_type[S](expected_type: type[S], /, *, because: str = ...) -> Expect[S]` — Assert the subject's type and continue on the narrowed value.

**What a failure looks like**

```python
from dataclasses import dataclass

from lovely_assertions import expect


@dataclass(frozen=True, slots=True)
class Money:
    cents: int
    currency: str


price = Money(1999, "EUR")
expect(price).is_equal_to(Money(2499, "EUR"))
```

```
Expected price to equal Money(cents=2499, currency='EUR'), but was Money(cents=1999, currency='EUR').
  field cents: 1999 instead of 2499
```

## `BoolExpect`

```python
class BoolExpect(Expect[bool]):
```

Returned for an exact `bool`: `True` and `False`, and nothing else.

**The two values**

- `is_true(*, because: str = "") -> Self` — Assert the subject is `True`.
- `is_false(*, because: str = "") -> Self` — Assert the subject is `False`.
- `is_not_true(*, because: str = "") -> Self` — Assert the subject is not `True`.
- `is_not_false(*, because: str = "") -> Self` — Assert the subject is not `False`.

**Logic**

- `implies(consequent: bool, /, *, because: str = "") -> Self` — Assert the material implication `subject -> consequent`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect

feature_enabled = False
expect(feature_enabled).is_true()
```

```
Expected feature_enabled to be True, but was False.
```

## `StringExpect`

```python
class StringExpect(Expect[str]):
```

Returned for a `str` and for any subclass of one. Note which `matches` this is:
on a string it takes a **regular expression**, because that is what the name
means in Python. The wildcard form is `matches_wildcard`, and the inherited
predicate form still works.

**Emptiness**

- `is_empty(*, because: str = "") -> Self` — Assert the string has no characters at all.
- `is_not_empty(*, because: str = "") -> Self` — Assert the string has at least one character.
- `is_blank(*, because: str = "") -> Self` — Assert the string is empty or contains nothing but whitespace.
- `is_not_blank(*, because: str = "") -> Self` — Assert the string holds something other than whitespace.

**Length**

- `has_length(expected: int, /, *, because: str = "") -> Self` — Assert the string is `expected` characters long.

**Caseless equality**

- `is_equal_ignoring_case(expected: str, /, *, ignoring_whitespace: bool = False, ignoring_newline_style: bool = False, because: str = "") -> Self` — Assert the string equals `expected` once case is set aside.
- `is_not_equal_ignoring_case(unexpected: str, /, *, ignoring_whitespace: bool = False, ignoring_newline_style: bool = False, because: str = "") -> Self` — Assert the string differs from `unexpected` by more than case.

**Containment**

- `contains(value: str, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert `value` appears somewhere in the string.
- `does_not_contain(unexpected: str, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert `unexpected` appears nowhere in the string.
- `contains_all(*values: str, because: str = "") -> Self` — Assert every one of `values` appears in the string.
- `does_not_contain_all(*values: str, because: str = "") -> Self` — Assert at least one of `values` is absent from the string.
- `contains_any(*values: str, because: str = "") -> Self` — Assert at least one of `values` appears in the string.
- `does_not_contain_any(*values: str, because: str = "") -> Self` — Assert none of `values` appears in the string.
- `contains_ignoring_case(value: str, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert `value` appears in the string, whatever the case of either.
- `does_not_contain_ignoring_case(unexpected: str, /, *, because: str = "") -> Self` — Assert `unexpected` appears nowhere in the string, in any case.

**Edges**

- `starts_with(prefix: str, /, *, because: str = "") -> Self` — Assert the string begins with `prefix`.
- `does_not_start_with(prefix: str, /, *, because: str = "") -> Self` — Assert the string does not begin with `prefix`.
- `starts_with_ignoring_case(prefix: str, /, *, because: str = "") -> Self` — Assert the string begins with `prefix`, whatever the case of either.
- `does_not_start_with_ignoring_case(prefix: str, /, *, because: str = "") -> Self` — Assert the string does not begin with `prefix` in any case.
- `ends_with(suffix: str, /, *, because: str = "") -> Self` — Assert the string ends with `suffix`.
- `does_not_end_with(suffix: str, /, *, because: str = "") -> Self` — Assert the string does not end with `suffix`.
- `ends_with_ignoring_case(suffix: str, /, *, because: str = "") -> Self` — Assert the string ends with `suffix`, whatever the case of either.
- `does_not_end_with_ignoring_case(suffix: str, /, *, because: str = "") -> Self` — Assert the string does not end with `suffix` in any case.

**Regular expressions**

- `matches(pattern: str | re.Pattern[str], /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` or `matches(predicate: Callable[[str], bool], /, *, because: str = "") -> Self` — Assert the string matches a regular expression, or satisfies a predicate.
- `does_not_match(pattern: str | re.Pattern[str], /, *, because: str = "") -> Self` — Assert no part of the string matches the regular expression `pattern`.

**Wildcards**

- `matches_wildcard(pattern: str, /, *, because: str = "") -> Self` — Assert the whole string matches the wildcard `pattern`.
- `does_not_match_wildcard(pattern: str, /, *, because: str = "") -> Self` — Assert the string does not match the wildcard `pattern` in full.
- `matches_wildcard_ignoring_case(pattern: str, /, *, because: str = "") -> Self` — Assert the whole string matches the wildcard `pattern`, ignoring case.
- `does_not_match_wildcard_ignoring_case(pattern: str, /, *, because: str = "") -> Self` — Assert the string does not match the wildcard `pattern`, in any case.

**Case**

- `is_upper(*, because: str = "") -> Self` — Assert every cased character in the string is upper case.
- `is_not_upper(*, because: str = "") -> Self` — Assert the string is not entirely upper case.
- `is_lower(*, because: str = "") -> Self` — Assert every cased character in the string is lower case.
- `is_not_lower(*, because: str = "") -> Self` — Assert the string is not entirely lower case.
- `is_title(*, because: str = "") -> Self` — Assert the string is title case (`str.istitle`).
- `is_not_title(*, because: str = "") -> Self` — Assert the string is not title case.

**Character classes**

- `is_alpha(*, because: str = "") -> Self` — Assert every character is a letter (`str.isalpha`).
- `is_not_alpha(*, because: str = "") -> Self` — Assert the string is not made entirely of letters.
- `is_digit(*, because: str = "") -> Self` — Assert every character is a digit (`str.isdigit`).
- `is_not_digit(*, because: str = "") -> Self` — Assert the string is not made entirely of digits.
- `is_numeric(*, because: str = "") -> Self` — Assert every character is numeric (`str.isnumeric`).
- `is_not_numeric(*, because: str = "") -> Self` — Assert the string is not made entirely of numeric characters.
- `is_alnum(*, because: str = "") -> Self` — Assert every character is a letter or a number (`str.isalnum`).
- `is_not_alnum(*, because: str = "") -> Self` — Assert the string is not made entirely of letters and numbers.
- `is_ascii(*, because: str = "") -> Self` — Assert every character is ASCII (`str.isascii`).
- `is_not_ascii(*, because: str = "") -> Self` — Assert the string holds at least one character outside ASCII.
- `is_printable(*, because: str = "") -> Self` — Assert every character is printable (`str.isprintable`).
- `is_not_printable(*, because: str = "") -> Self` — Assert the string holds at least one unprintable character.
- `is_space(*, because: str = "") -> Self` — Assert the string is non-empty and made only of whitespace (`str.isspace`).
- `is_not_space(*, because: str = "") -> Self` — Assert the string is not made entirely of whitespace.

**Identifiers**

- `is_identifier(*, because: str = "") -> Self` — Assert the string is a valid Python identifier (`str.isidentifier`).
- `is_not_identifier(*, because: str = "") -> Self` — Assert the string is not a valid Python identifier.

**UUIDs**

- `is_uuid(*, version: int | None = None, because: str = "") -> Found[Self, UUID]` — Assert the string spells a UUID; continue on the parsed one with `.which`.

**Inherited from [`Expect[T]`](#expectt)** (24 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`. `matches` is
redeclared above, and the declaration there is the one this subject offers.

**What a failure looks like**

```python
from lovely_assertions import expect

hostname = "db-01.internal"
expect(hostname).ends_with(".example.com")
```

```
Expected hostname to end with '.example.com', but was 'db-01.internal'.
```

## `OrderedExpect[T]`

```python
class OrderedExpect[T: Ordered](Expect[T]):
```

Returned for a `Decimal` and for a `Fraction`, and inherited by `NumericExpect`.
It holds the assertions that ask nothing of a value except that `<` accepts it —
comparisons, sign, ranges — which is what lets a `Decimal` have them without
being flattened into `int | float`: `.subject` keeps the type it was handed.

**Ordering**

- `is_greater_than(other: T, /, *, because: str = "") -> Self` — Assert `subject > other`. A NaN on either side fails: NaN is unordered.
- `is_greater_than_or_equal_to(other: T, /, *, because: str = "") -> Self` — Assert `subject >= other`.
- `is_less_than(other: T, /, *, because: str = "") -> Self` — Assert `subject < other`. A NaN on either side fails: NaN is unordered.
- `is_less_than_or_equal_to(other: T, /, *, because: str = "") -> Self` — Assert `subject <= other`.

**Sign and zero**

- `is_positive(*, because: str = "") -> Self` — Assert `subject > 0`. Zero is not positive, `-0.0` included.
- `is_negative(*, because: str = "") -> Self` — Assert `subject < 0`. `-0.0` is zero with a sign bit, not a negative number.
- `is_zero(*, because: str = "") -> Self` — Assert the subject is zero — `0`, `0.0` and `-0.0` all are.
- `is_not_zero(*, because: str = "") -> Self` — Assert the subject is not zero. A NaN passes: it equals nothing, zero included.

**Ranges (`is_between` includes its bounds)**

- `is_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low <= subject <= high`, both bounds included.
- `is_not_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert the subject is outside `low..high`, bounds included.
- `is_strictly_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low < subject < high`, both bounds excluded.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from decimal import Decimal

from lovely_assertions import expect

balance = Decimal("-12.50")
expect(balance).is_positive()
```

```
Expected balance to be positive, but was Decimal('-12.50').
```

`Ordered` in the signatures is the module's protocol for "anything `<` accepts".
It is not part of the public API and there is nothing to import: any type that
answers the four comparison operators satisfies it.

## `NumericExpect`

```python
class NumericExpect(OrderedExpect[int | float]):
```

Returned for an `int`, a `float` and their subclasses, and an `OrderedExpect` as
well, so the comparisons and ranges above all apply. What it adds is what only a
machine number needs: tolerance, and the two values that are not quite numbers.
The subject is the union `int | float` rather than a type parameter, so a
predicate handed to the inherited `matches` has to accept both.

**Approximation**

- `is_close_to(value: int | float, /, *, tol: int | float | None = None, rel: int | float | None = None, because: str = "") -> Self` — Assert the subject is close to `value`, absolutely or relatively.
- `is_not_close_to(value: int | float, /, *, tol: int | float | None = None, rel: int | float | None = None, because: str = "") -> Self` — Assert the subject is further from `value` than the tolerance allows.

**Special values**

- `is_nan(*, because: str = "") -> Self` — Assert the subject is a NaN.
- `is_not_nan(*, because: str = "") -> Self` — Assert the subject is not a NaN. Both infinities pass: neither of them is one.
- `is_infinite(*, because: str = "") -> Self` — Assert the subject is `inf` or `-inf`.
- `is_not_infinite(*, because: str = "") -> Self` — Assert the subject is finite. A NaN passes: it is not an infinity either.

**Inherited from [`OrderedExpect[T]`](#orderedexpectt)** (11 more):
`is_greater_than`, `is_greater_than_or_equal_to`, `is_less_than`,
`is_less_than_or_equal_to`, `is_positive`, `is_negative`, `is_zero`,
`is_not_zero`, `is_between`, `is_not_between`, `is_strictly_between`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect

measured = 9.9
expect(measured).is_close_to(10.0, tol=0.05)
```

```
Expected measured to be within 0.05 of 10.0, but 9.9 was 0.09999999999999964 away.
```

Two families of argument are rejected outright with a `ValueError`, before the
subject is looked at: an unusable range — inverted, `NaN`-bounded, or an empty
exclusive one — and an unusable tolerance, negative or `NaN`. Neither describes
a claim about the value, so neither is reported as a failure of it.

## `CollectionExpect[E, C]`

```python
class CollectionExpect[E, C: Collection[Any] = Collection[E]](Expect[C]):
```

Returned for anything with a length, an iterator and a membership test but no
order: a `set`, a `frozenset`, and the three `dict` views. It is also the base of
[`SequenceExpect[E]`](#sequenceexpecte), which is why the catalogue here is the
longest on the page — none of it depends on order, so a sequence inherits the
whole of it and adds the assertions that need one.

**Emptiness**

- `is_empty(*, because: str = "") -> Self` — Assert the collection has no items.
- `is_not_empty(*, because: str = "") -> Self` — Assert the collection has at least one item.
- `is_none_or_empty(*, because: str = "") -> Self` — Assert the collection is `None` or has no items.
- `is_not_none_or_empty(*, because: str = "") -> Self` — Assert the collection is neither `None` nor empty.

**Length**

- `has_length(expected: int, /, *, because: str = "") -> Self` — Assert the collection has exactly `expected` items.
- `does_not_have_length(unexpected: int, /, *, because: str = "") -> Self` — Assert the collection has any length but `unexpected`.
- `has_length_matching(predicate: Callable[[int], bool], /, *, because: str = "") -> Self` — Assert the collection's length satisfies `predicate`.
- `has_length_greater_than(other: int, /, *, because: str = "") -> Self` — Assert the collection has more than `other` items.
- `has_length_greater_than_or_equal_to(other: int, /, *, because: str = "") -> Self` — Assert the collection has at least `other` items.
- `has_length_less_than(other: int, /, *, because: str = "") -> Self` — Assert the collection has fewer than `other` items.
- `has_length_less_than_or_equal_to(other: int, /, *, because: str = "") -> Self` — Assert the collection has at most `other` items.
- `has_same_length_as(other: Collection[object], /, *, because: str = "") -> Self` — Assert the collection is as long as `other`.
- `does_not_have_same_length_as(other: Collection[object], /, *, because: str = "") -> Self` — Assert the collection is not as long as `other`.

**Containment**

- `contains(item: E, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert the collection holds `item`, and — with `occurrences` — how often.
- `does_not_contain(item: E, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert the collection does not hold `item`, or not that many times.
- `contains_single(*, because: str = "") -> Found[Self, E]` — Assert the collection holds exactly one item; continue with `.which`.
- `contains_matching(predicate: Callable[[E], bool], /, *, because: str = "") -> Found[Self, E]` — Assert some item satisfies `predicate`; continue on it with `.which`.
- `does_not_contain_matching(predicate: Callable[[E], bool], /, *, because: str = "") -> Self` — Assert no item satisfies `predicate`.
- `contains_single_matching(predicate: Callable[[E], bool], /, *, because: str = "") -> Found[Self, E]` — Assert exactly one item satisfies `predicate`; continue on it with `.which`.
- `only_contains(predicate: Callable[[E], bool], /, *, because: str = "") -> Self` — Assert every item satisfies `predicate`.
- `contains_items_of_type(expected_type: type[object], /, *, because: str = "") -> Self` — Assert every item is an instance of `expected_type` — the FluentAssertions spelling.
- `does_not_contain_items_of_type(unexpected_type: type[object], /, *, because: str = "") -> Self` — Assert no item is an instance of `unexpected_type`, subclasses included.
- `does_not_contain_none(*, key: Callable[[E], object] | None = None, because: str = "") -> Self` — Assert no item is `None`, or — with `key` — that no item *yields* one.
- `has_unique_items(*, key: Callable[[E], object] | None = None, because: str = "") -> Self` — Assert no item appears twice, or — with `key` — no *key* does.
- `contains_no_duplicates(*, key: Callable[[E], object] | None = None, because: str = "") -> Self` — Assert no item appears twice — the FluentAssertions spelling.

**Set-like relations**

- `is_subset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert every item also appears in `other`.
- `is_not_subset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert at least one item is missing from `other`.
- `is_superset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert every item of `other` also appears here.
- `is_not_superset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert at least one item of `other` is missing here.
- `is_proper_subset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert every item is in `other`, and `other` holds something more.
- `is_proper_superset_of(other: Collection[E], /, *, because: str = "") -> Self` — Assert every item of `other` is here, and something else besides.
- `intersects(other: Collection[E], /, *, because: str = "") -> Self` — Assert the collection shares at least one item with `other`.
- `does_not_intersect(other: Collection[E], /, *, because: str = "") -> Self` — Assert the collection shares no item with `other`.
- `is_disjoint_from(other: Collection[E], /, *, because: str = "") -> Self` — Assert the collection shares no item with `other` — the set-theory spelling.
- `contains_only(*items: E, because: str = "") -> Self` — Assert the collection holds exactly `items` — order and repeats ignored.
- `contains_none_of(*items: E, because: str = "") -> Self` — Assert not one of `items` appears in the collection.

**Multi-item membership**

- `contains_all(*items: E, because: str = "") -> Self` — Assert every one of `items` appears in the collection.
- `does_not_contain_all(*items: E, because: str = "") -> Self` — Assert at least one of `items` is absent.
- `contains_any(*items: E, because: str = "") -> Self` — Assert at least one of `items` appears in the collection.

**Element types**

- `all_are_instance_of(expected_type: type[object], /, *, because: str = "") -> Self` — Assert every item is an instance of `expected_type`, subclasses included.
- `all_are_exactly_type(expected_type: type[object], /, *, because: str = "") -> Self` — Assert every item is exactly `expected_type` — a subclass does not count.
- `all_equal_to(value: E, /, *, because: str = "") -> Self` — Assert every item equals `value`.

**Nested assertions**

- `all_satisfy(action: Callable[[E], object], /, *, because: str = "") -> Self` — Assert every item satisfies the nested assertions in `action`.
- `satisfies_in_any_order(*predicates: Callable[[E], bool], because: str = "") -> Self` — Assert each predicate holds for a *distinct* item, in any order.

**Wildcard matching (string collections)**

- `contains_match[S: CollectionExpect[str]](self: S, pattern: str, /, *, because: str = "") -> S` — Assert some item matches the wildcard `pattern` (`*` and `?`).
- `does_not_contain_match[S: CollectionExpect[str]](self: S, pattern: str, /, *, because: str = "") -> S` — Assert no item matches the wildcard `pattern` (`*` and `?`).

**Projection**

- `extracting[R](selector: Callable[[E], R], /) -> CollectionExpect[R]` — Assert about one field of every item instead of about the items.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect

response_headers = {"content-type": "application/json", "content-length": "27"}
expect(response_headers.keys()).contains("authorization")
```

```
Expected response_headers.keys() to contain 'authorization', but was ['content-type', 'content-length'].
```

`occurrences=` takes an occurrence constraint — `exactly(3)`, `at_least(1)`,
`once`; they are listed under
[Elsewhere in the public API](#elsewhere-in-the-public-api). On a negative
assertion it is the constraint that is negated and not the containment, so
`does_not_contain(x, occurrences=exactly(3))` passes when `x` appears twice,
four times, or not at all, and fails only on exactly three.

Every rendering of a collection in a message is bounded, whatever the size of
the collection; `formatting(max_items=...)` raises the bound for a block where
the whole list is what the reader needs.

## `SequenceExpect[E]`

```python
class SequenceExpect[E](CollectionExpect[E, Sequence[E]]):
```

Returned for a `Sequence` — `list`, `tuple`, `range`, `bytes` — parameterised by
the element type, so `expect(names).contains(3)` is a type error when `names` is
a `Sequence[str]`. Everything here is an assertion that needs an order to mean
anything; the rest of the catalogue is inherited from the collection subject.

**Ordered equality**

- `equals_sequence(other: Sequence[E], /, *, because: str = "") -> Self` — Assert the sequence holds the same items as `other`, in the same order.
- `does_not_equal_sequence(other: Sequence[E], /, *, because: str = "") -> Self` — Assert the sequence differs from `other` in length or in some item.
- `equals_approximately(other: Sequence[float], /, *, tol: float, because: str = "") -> Self` — Assert the sequence matches `other` item by item, each within `tol`.
- `starts_with_sequence(prefix: Sequence[E], /, *, because: str = "") -> Self` — Assert the sequence opens with `prefix`, item for item.
- `ends_with_sequence(suffix: Sequence[E], /, *, because: str = "") -> Self` — Assert the sequence closes with `suffix`, item for item.

**Element access**

- `has_element_at(index: int, value: E, /, *, because: str = "") -> Found[Self, E]` — Assert the item at `index` equals `value`; continue with `.which`.

**Containment**

- `does_not_contain(item: E, /, *, occurrences: Occurrence | None = None, because: str = "") -> Self` — Assert the sequence does not hold `item`, or not that many times.
- `contains_in_order(*items: E, because: str = "") -> Self` — Assert `items` all appear, in this order, not necessarily adjacent.
- `does_not_contain_in_order(*items: E, because: str = "") -> Self` — Assert `items` do not all appear in this order.
- `contains_in_consecutive_order(*items: E, because: str = "") -> Self` — Assert `items` appear as an unbroken run, in this order.
- `does_not_contain_in_consecutive_order(*items: E, because: str = "") -> Self` — Assert `items` never appear as an unbroken run in this order.

**Ordering**

- `is_sorted(*, key: Callable[[E], Sortable] | None = None, because: str = "") -> Self` — Assert the items are in non-decreasing order.
- `is_not_sorted(*, key: Callable[[E], Sortable] | None = None, because: str = "") -> Self` — Assert some item comes before one it should follow.
- `is_sorted_descending(*, key: Callable[[E], Sortable] | None = None, because: str = "") -> Self` — Assert the items are in non-increasing order.
- `is_not_sorted_descending(*, key: Callable[[E], Sortable] | None = None, because: str = "") -> Self` — Assert the items are not in non-increasing order.

**Projection**

- `extracting[R](selector: Callable[[E], R], /) -> SequenceExpect[R]` — Assert about one field of every item, keeping the order they were in.

**Nested assertions**

- `satisfies_respectively(*assertions: Callable[[E], object], because: str = "") -> Self` — Assert each item satisfies its own inspection, paired by position.

**Inherited from [`CollectionExpect[E, C]`](#collectionexpecte-c)** (45 more):
`is_empty`, `is_not_empty`, `is_none_or_empty`, `is_not_none_or_empty`,
`has_length`, `does_not_have_length`, `has_length_matching`,
`has_length_greater_than`, `has_length_greater_than_or_equal_to`,
`has_length_less_than`, `has_length_less_than_or_equal_to`,
`has_same_length_as`, `does_not_have_same_length_as`, `contains`,
`contains_single`, `contains_matching`, `does_not_contain_matching`,
`contains_single_matching`, `only_contains`, `contains_items_of_type`,
`does_not_contain_items_of_type`, `does_not_contain_none`, `has_unique_items`,
`contains_no_duplicates`, `is_subset_of`, `is_not_subset_of`, `is_superset_of`,
`is_not_superset_of`, `is_proper_subset_of`, `is_proper_superset_of`,
`intersects`, `does_not_intersect`, `is_disjoint_from`, `contains_only`,
`contains_none_of`, `contains_all`, `does_not_contain_all`, `contains_any`,
`all_are_instance_of`, `all_are_exactly_type`, `all_equal_to`, `all_satisfy`,
`satisfies_in_any_order`, `contains_match`, `does_not_contain_match`.
`does_not_contain` and `extracting` are redeclared above, and the declaration
there is the one this subject offers.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect

order_totals = [3, 1, 2]
expect(order_totals).is_sorted()
```

```
Expected order_totals to be sorted, but 1 at index 1 came after 3: [3, 1, 2].
```

`_Ordered` in the `key=` signatures is the module's internal protocol for
"anything `<` accepts". It is not exported and there is nothing to import: any
key function returning an orderable value satisfies it.

`contains_match` and `does_not_contain_match` carry an annotated `self`, which is
how they are offered on a sequence of strings and nowhere else.

`does_not_contain` and `extracting` are redeclared rather than inherited, and
order is the reason for both: a sequence can say *where* it found the item, and
an `extracting` over a sequence has to stay a `SequenceExpect` so that the
ordering assertions still follow it.

## `MappingExpect[K, V]`

```python
class MappingExpect[K, V](Expect[Mapping[K, V]]):
```

Returned for a `Mapping` — `dict`, `OrderedDict`, `ChainMap`, `MappingProxyType`
— parameterised by key and value type. It is not a `CollectionExpect`: a mapping
is a collection of its *keys*, and `contains` meaning "has this key" on one line
and "has this element" on the next is exactly the ambiguity this subject exists
to remove.

**Size**

- `is_empty(*, because: str = "") -> Self` — Assert the mapping has no entries.
- `is_not_empty(*, because: str = "") -> Self` — Assert the mapping has at least one entry.
- `is_none_or_empty(*, because: str = "") -> Self` — Assert the mapping is `None` or has no entries.
- `is_not_none_or_empty(*, because: str = "") -> Self` — Assert the mapping is neither `None` nor empty.
- `has_length(expected: int, /, *, because: str = "") -> Self` — Assert the mapping has exactly `expected` entries.
- `does_not_have_length(unexpected: int, /, *, because: str = "") -> Self` — Assert the mapping has any number of entries other than `unexpected`.
- `has_length_matching(predicate: Callable[[int], bool], /, *, because: str = "") -> Self` — Assert the number of entries satisfies `predicate`.
- `has_length_greater_than(other: int, /, *, because: str = "") -> Self` — Assert the mapping has more than `other` entries.
- `has_length_greater_than_or_equal_to(other: int, /, *, because: str = "") -> Self` — Assert the mapping has at least `other` entries.
- `has_length_less_than(other: int, /, *, because: str = "") -> Self` — Assert the mapping has fewer than `other` entries.
- `has_length_less_than_or_equal_to(other: int, /, *, because: str = "") -> Self` — Assert the mapping has at most `other` entries.
- `has_same_length_as(other: Sized, /, *, because: str = "") -> Self` — Assert the mapping has as many entries as `other` has items.
- `does_not_have_same_length_as(other: Sized, /, *, because: str = "") -> Self` — Assert the mapping and `other` differ in size.

**Views**

- `.keys -> CollectionExpect[K]` — Continue on the keys, as a collection.
- `.values -> CollectionExpect[V]` — Continue on the values, as a collection.

**Keys**

- `contains_key(key: K, /, *, because: str = "") -> Found[Self, V]` — Assert the mapping has `key`; continue on its value with `.whose_value`.
- `does_not_contain_key(key: K, /, *, because: str = "") -> Self` — Assert the mapping has no such key.
- `contains_keys(*keys: K, because: str = "") -> Self` — Assert every one of `keys` is present.
- `does_not_contain_keys(*keys: K, because: str = "") -> Self` — Assert none of `keys` is present.
- `contains_only_keys(*keys: K, because: str = "") -> Self` — Assert the keys are exactly `keys` — no more, no fewer, order ignored.
- `contains_key_matching(predicate: Callable[[K], bool], /, *, because: str = "") -> Found[Self, K]` — Assert some key satisfies `predicate`; continue on that key with `.which`.

**Values**

- `contains_value(value: V, /, *, occurrences: Occurrence | None = None, because: str = "") -> Found[Self, V]` — Assert some key holds `value`; continue on it with `.which`.
- `does_not_contain_value(value: V, /, *, because: str = "") -> Self` — Assert no key holds `value`.
- `contains_values(*values: V, because: str = "") -> Self` — Assert every one of `values` is held by some key.
- `does_not_contain_values(*values: V, because: str = "") -> Self` — Assert none of `values` is held by any key.
- `contains_value_matching(predicate: Callable[[V], bool], /, *, because: str = "") -> Found[Self, V]` — Assert some key holds a value satisfying `predicate`; continue with `.which`.

**Entries**

- `contains_entry(key: K, value: V, /, *, because: str = "") -> Self` — Assert the mapping maps `key` to `value`.
- `does_not_contain_entry(key: K, value: V, /, *, because: str = "") -> Self` — Assert the mapping does not map `key` to `value`.
- `contains_entries(entries: Mapping[K, V], /, *, because: str = "") -> Self` — Assert every entry of `entries` is present with that exact value.
- `contains_entry_matching(predicate: Callable[[K, V], bool], /, *, because: str = "") -> Found[Self, tuple[K, V]]` — Assert some entry satisfies `predicate(key, value)`; continue with `.which`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect

server_config = {"host": "db-01", "port": 5432}
expect(server_config).contains_key("hostname")
```

```
Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host', 'port'].
```

## `DateExpect[T]`

```python
class DateExpect[T: date](TemporalExpect[T]):
```

Returned for a `date`. The ordering assertions come from a base shared with the
time subject, written once because a `date` and a `time` answer the comparison
operators identically; what a date adds is the calendar — the components, the
day of the week, and where today falls.

**Ordering and ranges**

- `is_before(other: T, /, *, because: str = "") -> Self` — Assert the subject falls strictly before `other`.
- `is_after(other: T, /, *, because: str = "") -> Self` — Assert the subject falls strictly after `other`.
- `is_on_or_before(other: T, /, *, because: str = "") -> Self` — Assert the subject falls at or before `other`.
- `is_on_or_after(other: T, /, *, because: str = "") -> Self` — Assert the subject falls at or after `other`.
- `is_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low <= subject <= high`, both bounds included.
- `is_not_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert the subject falls outside `low..high`, bounds included.
- `is_strictly_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low < subject < high`, both bounds excluded.

**The calendar**

- `has_year(expected: int, /, *, because: str = "") -> Self` — Assert the subject falls in year `expected`.
- `has_month(expected: int, /, *, because: str = "") -> Self` — Assert the subject falls in month `expected`, January being 1.
- `has_day(expected: int, /, *, because: str = "") -> Self` — Assert the subject falls on day `expected` of its month.
- `is_weekday(*, because: str = "") -> Self` — Assert the subject falls Monday through Friday.
- `is_weekend(*, because: str = "") -> Self` — Assert the subject falls on a Saturday or a Sunday.
- `is_today(*, because: str = "") -> Self` — Assert the subject falls on today's calendar date.
- `is_in_the_past(*, because: str = "") -> Self` — Assert the subject is earlier than the moment the assertion runs.
- `is_in_the_future(*, because: str = "") -> Self` — Assert the subject is later than the moment the assertion runs.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from datetime import date

from lovely_assertions import expect

invoice_date = date(2024, 3, 16)
expect(invoice_date).is_weekday()
```

```
Expected invoice_date to fall on a weekday, but 2024-03-16 is a Saturday.
```

## `DateTimeExpect`

```python
class DateTimeExpect(DateExpect[datetime], ClockExpect[datetime]):
```

Returned for a `datetime` — which *is* a `date`, so this subject is a
[`DateExpect`](#dateexpectt) too and the whole calendar catalogue applies to it.
What it adds is the half a bare date has not got: the clock, which is the second
base class and is shared with [`TimeExpect`](#timeexpect), and then the timezone
and closeness measured as a `timedelta` rather than as a number.

**The clock**

- `has_hour(expected: int, /, *, because: str = "") -> Self` — Assert the subject's hour is `expected`, on a 24-hour clock.
- `has_minute(expected: int, /, *, because: str = "") -> Self` — Assert the subject's minute is `expected`.
- `has_second(expected: int, /, *, because: str = "") -> Self` — Assert the subject's second is `expected`. `datetime` has no leap seconds.
- `has_microsecond(expected: int, /, *, because: str = "") -> Self` — Assert the subject's microsecond is `expected`.
- `is_aware(*, because: str = "") -> Self` — Assert the subject carries a usable timezone.
- `is_naive(*, because: str = "") -> Self` — Assert the subject carries no usable timezone — `is_aware`'s complement.

**Instants and timezones**

- `is_same_date_as(other: datetime, /, *, because: str = "") -> Self` — Assert the subject falls on the same calendar day as `other`.
- `is_close_to(other: datetime, /, *, within: timedelta, because: str = "") -> Self` — Assert the subject is no more than `within` away from `other`.
- `is_not_close_to(other: datetime, /, *, within: timedelta, because: str = "") -> Self` — Assert the subject is more than `within` away from `other`.
- `is_utc(*, because: str = "") -> Self` — Assert the subject is anchored to UTC.
- `has_timezone(zone: tzinfo, /, *, because: str = "") -> Self` — Assert the subject carries exactly the timezone `zone`.
- `is_within(delta: timedelta, /) -> WithinDelta[Self]` — Open a difference chain: `is_within(delta).before(other)` or `.after(other)`.

**Inherited from [`DateExpect[T]`](#dateexpectt)** (15 more): `is_before`,
`is_after`, `is_on_or_before`, `is_on_or_after`, `is_between`, `is_not_between`,
`is_strictly_between`, `has_year`, `has_month`, `has_day`, `is_weekday`,
`is_weekend`, `is_today`, `is_in_the_past`, `is_in_the_future`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from datetime import datetime

from lovely_assertions import expect

recorded_at = datetime(2024, 3, 16, 14, 30)
expect(recorded_at).is_utc()
```

```
Expected recorded_at to be UTC, but 2024-03-16T14:30:00 is naive.
```

## `TimeExpect`

```python
class TimeExpect(ClockExpect[time]):
```

Returned for a `time`: a clock reading with no date behind it. It shares the
ordering assertions with the date subject and the clock assertions with the
datetime one, and adds the single thing only a time can be. Both shared groups
come from private base classes, which is why `T` appears in the signatures
below: here it is always `time`.

**Ordering and ranges**

- `is_before(other: T, /, *, because: str = "") -> Self` — Assert the subject falls strictly before `other`.
- `is_after(other: T, /, *, because: str = "") -> Self` — Assert the subject falls strictly after `other`.
- `is_on_or_before(other: T, /, *, because: str = "") -> Self` — Assert the subject falls at or before `other`.
- `is_on_or_after(other: T, /, *, because: str = "") -> Self` — Assert the subject falls at or after `other`.
- `is_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low <= subject <= high`, both bounds included.
- `is_not_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert the subject falls outside `low..high`, bounds included.
- `is_strictly_between(low: T, high: T, /, *, because: str = "") -> Self` — Assert `low < subject < high`, both bounds excluded.

**The clock**

- `has_hour(expected: int, /, *, because: str = "") -> Self` — Assert the subject's hour is `expected`, on a 24-hour clock.
- `has_minute(expected: int, /, *, because: str = "") -> Self` — Assert the subject's minute is `expected`.
- `has_second(expected: int, /, *, because: str = "") -> Self` — Assert the subject's second is `expected`. `datetime` has no leap seconds.
- `has_microsecond(expected: int, /, *, because: str = "") -> Self` — Assert the subject's microsecond is `expected`.
- `is_aware(*, because: str = "") -> Self` — Assert the subject carries a usable timezone.
- `is_naive(*, because: str = "") -> Self` — Assert the subject carries no usable timezone — `is_aware`'s complement.

**Midnight**

- `is_midnight(*, because: str = "") -> Self` — Assert the subject is exactly 00:00:00.000000.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from datetime import time

from lovely_assertions import expect

cutoff = time(17, 30)
expect(cutoff).is_midnight()
```

```
Expected cutoff to be midnight, but was 17:30:00.
```

## `TimeDeltaExpect`

```python
class TimeDeltaExpect(Expect[timedelta]):
```

Returned for a `timedelta`. A duration is not a moment, so this one deliberately
does not inherit the temporal base: `is_before` would have nothing to mean on it.
It carries its own comparisons instead, spelled as lengths — `is_longer_than`,
`is_at_most` — and they read as durations rather than as positions.

**Durations**

- `is_longer_than(other: timedelta, /, *, because: str = "") -> Self` — Assert the subject is a longer duration than `other`.
- `is_shorter_than(other: timedelta, /, *, because: str = "") -> Self` — Assert the subject is a shorter duration than `other`.
- `is_at_least(other: timedelta, /, *, because: str = "") -> Self` — Assert the subject is `other` or longer.
- `is_at_most(other: timedelta, /, *, because: str = "") -> Self` — Assert the subject is `other` or shorter.
- `is_between(low: timedelta, high: timedelta, /, *, because: str = "") -> Self` — Assert `low <= subject <= high`, both bounds included.
- `is_not_between(low: timedelta, high: timedelta, /, *, because: str = "") -> Self` — Assert the subject falls outside `low..high`, bounds included.
- `is_positive(*, because: str = "") -> Self` — Assert the duration runs forwards. Zero is not positive.
- `is_negative(*, because: str = "") -> Self` — Assert the duration runs backwards. Zero is not negative.
- `is_zero(*, because: str = "") -> Self` — Assert the duration is exactly zero.
- `is_not_zero(*, because: str = "") -> Self` — Assert the duration is not zero — `is_zero`'s complement.
- `is_close_to(other: timedelta, /, *, within: timedelta, because: str = "") -> Self` — Assert the subject is no more than `within` away from `other`.
- `is_not_close_to(other: timedelta, /, *, within: timedelta, because: str = "") -> Self` — Assert the subject is more than `within` away from `other`.
- `has_total_seconds(expected: float, /, *, because: str = "") -> Self` — Assert `subject.total_seconds()` equals `expected`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from datetime import timedelta

from lovely_assertions import expect

elapsed = timedelta(seconds=95)
expect(elapsed).is_shorter_than(timedelta(seconds=60))
```

```
Expected elapsed to be shorter than 0:01:00, but was 0:01:35.
```

## `PurePathExpect[T]`

```python
class PurePathExpect[T: PurePath](Expect[T]):
```

Returned for a `PurePath`: a path as a *name*, with no filesystem behind it.
Every assertion here is string and structure work and none of them touches the
disk, which is what makes them safe on a `PureWindowsPath` under Linux and on a
path that was never going to exist.

**The pieces of a name**

- `has_name(expected: str, /, *, because: str = "") -> Self` — Assert the last component of the path is `expected`.
- `has_stem(expected: str, /, *, because: str = "") -> Self` — Assert the name without its final suffix is `expected`.
- `has_suffix(expected: str, /, *, because: str = "") -> Self` — Assert the final suffix is `expected`, leading dot included.
- `has_suffixes(expected: list[str] | tuple[str, ...], /, *, because: str = "") -> Self` — Assert the full run of suffixes is `expected`, in order.
- `has_no_suffix(*, because: str = "") -> Self` — Assert the path's name carries no suffix at all.

**Absoluteness**

- `is_absolute(*, because: str = "") -> Self` — Assert the path is absolute.
- `is_relative(*, because: str = "") -> Self` — Assert the path is relative — the exact complement of `is_absolute`.

**One path against another**

- `is_relative_to(other: PurePath, /, *, because: str = "") -> Self` — Assert the path sits under `other`, or is `other`.
- `is_not_relative_to(other: PurePath, /, *, because: str = "") -> Self` — Assert the path does not sit under `other`.
- `has_parent(other: PurePath, /, *, because: str = "") -> Self` — Assert the path's immediate parent is `other`.
- `matches_pattern(pattern: str, /, *, case_sensitive: bool | None = None, because: str = "") -> Self` — Assert the path matches a glob `pattern` — `PurePath.match`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from pathlib import PurePosixPath

from lovely_assertions import expect

artefact = PurePosixPath("build/report.txt")
expect(artefact).has_suffix(".pdf")
```

```
Expected artefact to have the suffix '.pdf', but 'build/report.txt' has the suffix '.txt'.
```

## `PathExpect`

```python
class PathExpect(PurePathExpect[Path]):
```

Returned for a `Path`, and a `PurePathExpect` as well, so every name assertion
above applies to it. What it adds is everything that has to look: presence, kind,
size, contents, directory entries. Each of those can fail for a reason that is
not the claim being made — the path is a directory, the parent is missing, the
file is not readable — and the message says which, rather than reporting the
assertion false.

**Presence**

- `exists(*, because: str = "") -> Self` — Assert something usable exists at the path, following symbolic links.
- `does_not_exist(*, because: str = "") -> Self` — Assert the path is free — nothing there, not even a dangling link.

**What kind of thing is there**

- `is_file(*, because: str = "") -> Self` — Assert a regular file is at the path, following symbolic links.
- `is_not_file(*, because: str = "") -> Self` — Assert something is at the path and it is not a regular file.
- `is_directory(*, because: str = "") -> Self` — Assert a directory is at the path, following symbolic links.
- `is_not_directory(*, because: str = "") -> Self` — Assert something is at the path and it is not a directory.
- `is_symlink(*, because: str = "") -> Self` — Assert the path itself is a symbolic link, wherever it points.
- `is_not_symlink(*, because: str = "") -> Self` — Assert something is at the path and it is not a symbolic link.

**Emptiness**

- `is_empty(*, because: str = "") -> Self` — Assert the path holds nothing: zero bytes for a file, no entries for a directory.
- `is_not_empty(*, because: str = "") -> Self` — Assert the path holds something: at least one byte, or at least one entry.

**Size**

- `has_size(expected: int, /, *, because: str = "") -> Self` — Assert the file holds exactly `expected` bytes.
- `has_size_greater_than(limit: int, /, *, because: str = "") -> Self` — Assert the file holds strictly more than `limit` bytes.
- `has_size_less_than(limit: int, /, *, because: str = "") -> Self` — Assert the file holds strictly fewer than `limit` bytes.

**Contents**

- `has_text(expected: str, /, *, encoding: str = "utf-8", because: str = "") -> Self` — Assert the file's contents are exactly `expected`.
- `contains_text(expected: str, /, *, encoding: str = "utf-8", because: str = "") -> Self` — Assert `expected` appears somewhere in the file's contents.
- `does_not_contain_text(unexpected: str, /, *, encoding: str = "utf-8", because: str = "") -> Self` — Assert `unexpected` appears nowhere in the file's contents.

**Directory entries**

- `has_child(name: str, /, *, because: str = "") -> Self` — Assert the directory holds an entry called `name`.
- `does_not_have_child(name: str, /, *, because: str = "") -> Self` — Assert the directory holds no entry called `name`.

**Identity on disk**

- `is_same_file_as(other: Path, /, *, because: str = "") -> Self` — Assert the subject and `other` are the same file on disk.

**Inherited from [`PurePathExpect[T]`](#purepathexpectt)** (11 more):
`has_name`, `has_stem`, `has_suffix`, `has_suffixes`, `has_no_suffix`,
`is_absolute`, `is_relative`, `is_relative_to`, `is_not_relative_to`,
`has_parent`, `matches_pattern`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from pathlib import Path

from lovely_assertions import expect

config_file = Path("settings.toml")
expect(config_file).exists()
```

```
Expected config_file to exist, but nothing is there at 'settings.toml'.
```

Nothing here caches. Each assertion asks the filesystem at the moment it is
made, which is the only answer worth reporting about a thing another process can
change between two lines of a test.

## `EnumExpect[T]`

```python
class EnumExpect[T: Enum](Expect[T]):
```

Returned for an enum *member*, and ahead of `str` and `int` because a `StrEnum`
member is a `str` and an `IntEnum` member is an `int`: being an enum is the more
useful of the two things to know. The flag assertions are for `enum.Flag` and
`enum.IntFlag`; asked of a plain `Enum` they raise a `TypeError` rather than
report a failure that would mean nothing. An enum *class* is a class, and gets
[`TypeExpect`](#typeexpect).

**Names**

- `has_name(name: str, /, *, because: str = "") -> Self` — Assert the member is the one called `name`.
- `does_not_have_name(name: str, /, *, because: str = "") -> Self` — Assert the member is not the one called `name`.
- `has_same_name_as(other: Enum, /, *, because: str = "") -> Self` — Assert the member's name equals `other`'s.

**Values**

- `has_value(value: object, /, *, because: str = "") -> Self` — Assert the member's `value` equals `value`.
- `does_not_have_value(value: object, /, *, because: str = "") -> Self` — Assert the member's `value` differs from `value`.
- `has_same_value_as(other: Enum, /, *, because: str = "") -> Self` — Assert the member's `value` equals `other`'s.

**Flags (enum.Flag and enum.IntFlag only)**

- `has_flag(other: T, /, *, because: str = "") -> Self` — Assert `other`'s bits are all set in the subject.
- `does_not_have_flag(other: T, /, *, because: str = "") -> Self` — Assert at least one of `other`'s bits is not set in the subject.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from enum import Enum

from lovely_assertions import expect


class Status(Enum):
    PENDING = "pending"
    SHIPPED = "shipped"


order_status = Status.PENDING
expect(order_status).has_name("SHIPPED")
```

```
Expected order_status to be named 'SHIPPED', but Status.PENDING is named 'PENDING'.
```

## `CallableExpect`

```python
class CallableExpect(Expect[Callable[..., object]]):
```

Returned for anything callable that is not a class. The subject is normally a
zero-argument thunk, because the assertion has to do the calling itself:
`expect(lambda: parse("x")).raises(ValueError)`. A generator function needs
draining as well, and `expect(lambda: list(rows()))` is how — calling a
generator function only builds a generator, so nothing it would raise has
happened yet.

The context-manager form is the other spelling and the primary one, because it
leaves the code under test a statement instead of folding it into a lambda:

```python
from lovely_assertions import expect_raises


def parse(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse("nope")

caught.with_message_containing("invalid literal")
```

Both hand back a [`RaisedExpect[E]`](#raisedexpecte). Inside the block there is
no exception yet, and `caught.subject` says so with a `RuntimeError` rather than
reporting on a value that does not exist.

The warning assertions below come in the same two forms — `warns` here and
`expect_warns` as the block — and both hand back a
[`WarnedExpect[W]`](#warnedexpectw).

**Raising**

- `raises[E: BaseException](exception_type: type[E], /, *, because: str = "") -> RaisedExpect[E]` — Assert the call raises `exception_type` or a subclass; continue on the exception.
- `raises_exactly[E: BaseException](exception_type: type[E], /, *, because: str = "") -> RaisedExpect[E]` — Assert the call raises `exception_type` itself — a subclass does not count.
- `does_not_raise(exception_type: type[BaseException] | None = None, /, *, because: str = "") -> Self` — Assert the call raises nothing, or nothing of type `exception_type`.

**Warning**

- `warns[W: Warning](category: type[W], /, *, occurrences: Occurrence | None = None, because: str = "") -> WarnedExpect[W]` — Assert the call issues a warning of `category`; continue on the warnings.
- `does_not_warn(category: type[Warning] | None = None, /, *, because: str = "") -> Self` — Assert the call issues no warning, or none of type `category`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect


def parse(text: str) -> int:
    return int(text)


expect(lambda: parse("nope")).raises(KeyError)
```

```
Expected lambda: parse("nope") to raise KeyError, but raised ValueError("invalid literal for int() with base 10: 'nope'").
```

## `RaisedExpect[E]`

```python
class RaisedExpect[E: BaseException](Expect[E]):
```

The exception itself, as a subject. `raises`, `raises_exactly`, `with_cause`,
`with_cause_exactly` and `expect_raises` all hand one back, so the whole generic
catalogue applies to the exception too. `.which` is here a spelling rather than
a step — the exception is already the subject — so that
`raises(ValueError).which.with_message("x")` reads the way it is meant.

**Continuations**

- `.which -> Self` — The exception itself: here a spelling, not a step.

**Message**

- `with_message(pattern: str | re.Pattern[str], /, *, because: str = "") -> Self` — Assert the exception's message matches the regular expression `pattern`.
- `with_message_containing(text: str, /, *, because: str = "") -> Self` — Assert the exception's message contains `text` — a plain substring, no regex.

**Notes (PEP 678)**

- `with_note(text: str, /, *, because: str = "") -> Self` — Assert the exception carries `text` as one of its notes, exactly.
- `with_note_matching(pattern: str | re.Pattern[str], /, *, because: str = "") -> Self` — Assert some note matches the regular expression `pattern`.
- `has_no_notes(*, because: str = "") -> Self` — Assert nothing has been attached to the exception with `add_note`.

**Cause**

- `with_cause[C: BaseException](exception_type: type[C], /, *, because: str = "") -> RaisedExpect[C]` — Assert the exception has a cause of type `exception_type`; continue on the cause.
- `with_cause_exactly[C: BaseException](exception_type: type[C], /, *, because: str = "") -> RaisedExpect[C]` — Assert the cause is `exception_type` itself — a subclass does not count.

**Predicate**

- `where(predicate: Callable[[E], bool], /, *, because: str = "") -> Self` — Assert the exception satisfies `predicate`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect_raises


def parse(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse("nope")

caught.with_message_containing("not a number")
```

```
Expected the value to have a message containing 'not a number', but the message was "invalid literal for int() with base 10: 'nope'".
```

The message names `the value` rather than a variable, and that is worth knowing:
subject naming reads the statement that failed, and
`caught.with_message_containing(...)` holds no `expect(...)` call to read a name
out of. The fluent form keeps it —
`expect(lambda: parse("nope")).raises(ValueError).with_message_containing(...)`
reports `Expected lambda: parse("nope") to have a message containing ...`.

## `WarnedExpect[W]`

```python
class WarnedExpect[W: Warning](Expect[tuple[W, ...]]):
```

The warnings a call issued, as a subject. A call raises at most one exception
and may issue any number of them, so this subject carries every warning of the
category asked for, in the order they were issued, and its own assertions ask
whether *some* one of them satisfies the claim — never all of them, because a
call that deprecates two arguments issues two warnings and the test is about
one.

Two forms produce it, as the exception family has two. `expect_warns(...)` is
the primary one and sits where `pytest.warns` sits, leaving the code under test
a statement; `warns(...)` on [`CallableExpect`](#callableexpect) is the
thunk-wrapping twin. Both take an `occurrences=` constraint counted over the
warnings of that category alone, and mean "at least one" without it. Inside the
block there are no warnings yet, and `warned.subject` raises a `RuntimeError`
saying so.

The negative is `does_not_warn()`, and it sits on the callable subject rather
than here: nothing was captured for it to be a subject of.

**Continuations**

- `.which -> Self` — The warnings themselves: here a spelling, not a step.

**Message**

- `with_message(pattern: str | re.Pattern[str], /, *, because: str = "") -> Self` — Assert some captured warning's message matches the regular expression `pattern`.
- `with_message_containing(text: str, /, *, because: str = "") -> Self` — Assert some captured warning's message contains `text` — a substring, no regex.

**Predicate**

- `where(predicate: Callable[[W], bool], /, *, because: str = "") -> Self` — Assert some captured warning satisfies `predicate`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
import warnings

from lovely_assertions import expect_warns


def parse_date(text: str) -> str:
    warnings.warn("parse_date() is deprecated since 2.0", DeprecationWarning, stacklevel=2)
    return text


with expect_warns(DeprecationWarning) as warned:
    parse_date("2024-03-16")

warned.with_message_containing("use parse_iso instead")
```

```
Expected DeprecationWarning to have a message containing 'use parse_iso instead', but the message was 'parse_date() is deprecated since 2.0'.
```

The message names the *category*, where the exception subject above names `the
value`, and the difference is deliberate: the block form holds no `expect(...)`
call to read a name out of, and `DeprecationWarning` is worth more in that
sentence than `the value` would be. It reads the same when the category arrived
in a variable, because it is taken from the class rather than from the source.

**Where `pytest.warns` is the better answer.** It is one line, it is already in
the file, and for "did this warn at all" there is nothing here it does not
already do. Three things it cannot do are why this exists beside it. A failure
here says what *was* there rather than only what was not — the messages above,
and, where the capture itself came up empty, every warning that was issued with
the file and line `stacklevel` pointed at. It reports through the same path as
every other assertion, so a `soft_assertions()` block collects it and runs to
the end instead of stopping at the first finding. And `occurrences=` counts,
which `pytest.warns` has no spelling for. `does_not_warn` is a fourth:
`pytest.warns` can only say that something *did* warn.

Capture is process-wide and not thread-safe, because `warnings.catch_warnings`
swaps a global filter list — the same caveat `pytest.warns` carries, for the
same reason. Warnings *outside* the category under test are re-issued to the
project's own filters on the way out rather than swallowed, so a block watching
for one category does not quietly disarm the project's handling of the rest.

## `TypeExpect`

```python
class TypeExpect(CallableExpect):
```

Returned for a class — any class, an `Enum` class and an ABC included. It is a
`CallableExpect`, because a class is callable, so `expect(Widget).raises(...)`
still asks about the constructor. What it adds is what a class can say about
itself: what it inherits, what it declares, whether it can be instantiated at
all, and whether it satisfies a protocol.

Where an answer cannot honestly be computed — a protocol that is not
`runtime_checkable`, a subject that is not a class — the assertion raises rather
than reporting a failure it did not establish.

**Inheritance**

- `is_subclass_of(other: type[object], /, *, because: str = "") -> Self` — Assert the subject is a subclass of `other`.
- `is_not_subclass_of(other: type[object], /, *, because: str = "") -> Self` — Assert the subject is not a subclass of `other`.

**Attributes and methods**

- `has_attribute(name: str, /, *, because: str = "") -> Found[Self, Any]` — Assert the class defines `name`; continue on its value with `.which`.
- `does_not_have_attribute(name: str, /, *, because: str = "") -> Self` — Assert the class does not define `name`.
- `has_method(name: str, /, *, because: str = "") -> Found[Self, Any]` — Assert the class defines `name` as a method; continue on it with `.which`.

**Abstractness**

- `is_abstract(*, because: str = "") -> Self` — Assert the class leaves at least one abstract method unimplemented.
- `is_not_abstract(*, because: str = "") -> Self` — Assert the class leaves no abstract method unimplemented.

**Protocols**

- `implements(protocol: type[object], /, *, because: str = "") -> Self` — Assert the class satisfies `protocol`.
- `does_not_implement(protocol: type[object], /, *, because: str = "") -> Self` — Assert the class does not satisfy `protocol`.

**Inherited from [`CallableExpect`](#callableexpect)** (five more): `raises`,
`raises_exactly`, `does_not_raise`, `warns`, `does_not_warn`.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from lovely_assertions import expect


class Repository:
    pass


expect(Repository).is_subclass_of(dict)
```

```
Expected Repository to be a subclass of dict, but it inherits from object.
```

## `MockExpect`

```python
class MockExpect(Expect[Any]):
```

Returned for a `unittest.mock` mock, ahead of everything else: a `MagicMock`
defines `__len__`, `__iter__` and `__contains__`, so the collection subject would
otherwise claim it, and a mock is not a collection in any sense the collection
catalogue could act on.

It is also the one subject with no overload behind it, for the reason given
under [Which subject you get](#which-subject-you-get): a mock is statically
assignable to everything, so no position in the overload list could reach it.
`expect(m, as_=MockExpect)` is the typed route, and
[the divergence ledger](../concepts/typing-divergences.md) records the trade.

**How often**

- `was_called(*, because: str = "") -> Self` — Assert the mock was called at least once.
- `was_not_called(*, because: str = "") -> Self` — Assert the mock was never called.
- `was_called_once(*, because: str = "") -> Self` — Assert the mock was called exactly once, whatever the arguments.
- `has_call_count(expected: int | Occurrence, /, *, because: str = "") -> Self` — Assert how many times the mock was called.

**With what**

- `was_called_with(*args: object, because: str = "", **kwargs: object) -> Self` — Assert the **most recent** call was made with these arguments.
- `was_called_once_with(*args: object, because: str = "", **kwargs: object) -> Self` — Assert the mock was called exactly once, and with these arguments.
- `was_ever_called_with(*args: object, because: str = "", **kwargs: object) -> Self` — Assert some call — any of them — was made with these arguments.
- `was_never_called_with(*args: object, because: str = "", **kwargs: object) -> Self` — Assert no call was made with these arguments.

**Continuations**

- `.calls -> SequenceExpect[Any]` — The recorded calls, as a sequence subject.
- `last_call(*, because: str = "") -> Found[Self, Any]` — Assert the mock was called, and continue on its most recent call.

**Inherited from [`Expect[T]`](#expectt)** (25 more): `subject`, `and_`,
`described_as`, `is_truthy`, `is_falsy`, `satisfies_any`, `satisfies_none`,
`is_equal_to`, `is_not_equal_to`, `is_equivalent_to`, `is_not_equivalent_to`,
`is_same_as`, `is_not_same_as`, `is_none`, `is_not_none`, `is_one_of`, `is_in`,
`is_not_in`, `matches`, `satisfies`, `is_instance_of`, `is_not_instance_of`,
`is_exactly_instance_of`, `is_not_exactly_instance_of`, `as_type`.

**What a failure looks like**

```python
from unittest.mock import Mock

from lovely_assertions import expect

send = Mock()
send("welcome", to="ada@example.com")

expect(send).was_called_with("welcome", to="grace@example.com")
```

```
Expected send to have been called with ('welcome', to='grace@example.com'), but was called with ('welcome', to='ada@example.com').
  keyword arguments:
    values differ at key 'to': 'ada@example.com' instead of 'grace@example.com'
```

## Elsewhere in the public API

Not assertions, but exported from `lovely_assertions` and worth knowing exist;
names and descriptions come from the same source as everything above.
[the extension guide](../guides/extending.md) is where the extension half
of the list belongs.

**Failures and scopes**

| Name | What it is |
| --- | --- |
| `AssertionFailure` | Raised when an assertion fails. |
| `expect_raises[E: BaseException](exception_type: type[E], /, *, because: str = "") -> AbstractContextManager[RaisedExpect[E]]` | Assert that the block raises `exception_type`; continue on the exception. |
| `expect_warns[W: Warning](category: type[W], /, *, occurrences: Occurrence \| None = None, because: str = "") -> AbstractContextManager[WarnedExpect[W]]` | Assert that the block issues a warning of `category`; continue on the warnings. |
| `soft_assertions(name: str \| None = None, /, *, formatters: tuple[ValueFormatter, ...] = ()) -> SoftScope` | Open a soft-assertion scope; failures inside it aggregate instead of raising. |
| `SoftScope` | Collects assertion failures instead of raising them, one scope at a time. |
| `Found` | The result of an assertion that *found* a value inside the subject. |
| `WithinDelta` | The middle of `is_within(delta).before(other)`. |

**How many times**

| Name | What it is |
| --- | --- |
| `Occurrence` | How many times something has to appear for an assertion to hold. |
| `exactly(count: int, /) -> Occurrence` | Require exactly `count` occurrences. |
| `at_least(count: int, /) -> Occurrence` | Require `count` occurrences or more. |
| `at_most(count: int, /) -> Occurrence` | Require `count` occurrences or fewer. |
| `more_than(count: int, /) -> Occurrence` | Require strictly more than `count` occurrences. |
| `less_than(count: int, /) -> Occurrence` | Require strictly fewer than `count` occurrences. |
| `once` | `exactly(1)`, for the reading. |
| `twice` | `exactly(2)`, likewise. |

**Structural comparison**

| Name | What it is |
| --- | --- |
| `Equivalency` | How two graphs are to be compared. Immutable; every method returns a new one. |
| `equivalency() -> Equivalency` | Return the default configuration: strict ordering, ten levels, nothing excluded. |
| `close_within(tolerance: float \| timedelta) -> Callable[[Any, Any], bool]` | Build a comparator for `Equivalency.using` that allows `tolerance`. |

**Matchers**

| Name | What it is |
| --- | --- |
| `any_instance_of[T](kind: type[T], /) -> T` | A placeholder for any instance of `kind`. |
| `anything() -> Any` | A placeholder for any value at all, `None` included. |
| `string_matching(pattern: str \| re.Pattern[str], /) -> str` | A placeholder for any string a regular expression finds a match in. |
| `string_containing(fragment: str, /) -> str` | A placeholder for any string holding `fragment`. |
| `close_to(value: int \| float, /, *, tol: int \| float \| None = None, rel: int \| float \| None = None) -> float` | A placeholder for any number within a tolerance of `value`. |
| `one_of[T](*values: T) -> T` | A placeholder for any one of `values`. |
| `containing[T](spec: T, /) -> T` | A placeholder for a container holding at least what `spec` holds. |
| `matching[T](predicate: Callable[[T], bool], /) -> T` | A placeholder for any value a predicate says yes to. |
| `is_matcher(value: object, /) -> bool` | Whether `value` is one of this library's matchers. |

**How values are rendered**

| Name | What it is |
| --- | --- |
| `FormattingOptions` | The bounds a failure message renders within. |
| `formatting(*, max_items: int \| None = None, max_chars: int \| None = None, max_diff_lines: int \| None = None, max_depth: int \| None = None) -> AbstractContextManager[FormattingOptions]` | Scope different rendering bounds to a block. |
| `current_formatting() -> FormattingOptions` | Return the bounds a failure message currently renders within. |
| `register_formatter(formatter: ValueFormatter, /) -> None` | Register `formatter` for every failure message from here on. |
| `ValueFormatter` | Renders a value into the text of a failure message. |
| `ObjectFormatter` | Renders an object through chosen attributes: `Order(id=7, total=42)`. |
| `IterableFormatter` | Renders an iterable as `Type[item, item, ... (3 more)]`. |
| `format_value(value: object, /) -> str` | Render `value` for a failure message. |

**Dispatch and extension**

| Name | What it is |
| --- | --- |
| `register[T](subject_type: type[T], factory: Callable[[T], Expect[T]], /) -> None` | Teach `expect()` to return a custom subject for `subject_type`. |
| `custom_assertion[F: Callable[..., Any]](func: F, /) -> F` | Mark a user-defined assertion function so its frame is skipped when naming the subject. |
| `is_mock(value: object, /) -> bool` | Whether `value` behaves like a `unittest.mock` mock. The dispatch predicate. |

A soft scope changes the shape of a message rather than its content: failures
are collected instead of raised, the scope's name is prefixed to every subject
name, and the block reports all of them on the way out. Scopes nest, and the
names compose into a `/`-joined path, so a failure two levels down reads
`checkout/totals/total`.

```python
from lovely_assertions import expect, soft_assertions

total = -3
items: list[str] = []

with soft_assertions("checkout"):
    expect(total).is_positive()
    expect(items).is_not_empty()
```

```
2 assertions failed:
  (1) Expected checkout/total to be positive, but was -3.
  (2) Expected checkout/items not to be empty, but it was.
```

A matcher is a placeholder that goes in an *expectation* and never in a
subject. `{"id": any_instance_of(int)}` is an ordinary dict holding an ordinary
object, and the object answers `==` loosely. Nothing in this library walks them:
a matcher is reached by Python's own comparison protocol, which is why one works
at any depth inside `is_equal_to`, `is_equivalent_to`, `contains` and
`was_called_with` with not a line of support written for any of them.

```python
from lovely_assertions import any_instance_of, close_to, containing, expect, string_matching

response = {
    "id": 4171,
    "token": "eyJhbGciOiJIUzI1NiJ9",
    "ttl": 59.7,
    "tags": ["beta", "eu-west"],
}

expect(response).is_equal_to(
    {
        "id": any_instance_of(int),
        "token": string_matching(r"^ey"),
        "ttl": close_to(60, tol=1),
        "tags": containing(["eu-west"]),
    }
)
```

The unusual part is the declaration. Each factory is *declared* to return the
type it stands in for, so a matcher drops into an invariant slot —
`dict[str, int]`, `list[int]` — that no honestly typed placeholder could reach,
and the slot goes on being checked:

```python
from lovely_assertions import any_instance_of, expect, one_of

counts = {"hits": 12, "misses": 3, "retries": 1}
expected: dict[str, int] = {"hits": any_instance_of(int), "misses": 3, "retries": one_of(0, 1)}

expect(counts).is_equal_to(expected)
```

`dict[str, int]` is what that annotation says and what both checkers enforce:
`any_instance_of(str)` in the same slot is an error, and so is
`expect(names).contains(any_instance_of(int))` on a `list[str]`. It is the
caller's own annotations that switch the protection on, which is the argument
for declaring the expectation rather than inlining it — `is_equal_to` takes an
`object`, so that any two values can be compared, and a matcher written straight
into the call has no slot to be checked against.

The declaration is also a fiction, and the cost is worth stating rather than
discovering: `any_instance_of(str)` is annotated `str` and has no `.upper()`. So
a matcher belongs in an expectation and nowhere else — never the subject, never
stored, never operated on — and `expect()` refuses one outright rather than
reporting on a placeholder:

```python
from lovely_assertions import any_instance_of, expect, expect_raises

with expect_raises(TypeError) as refused:
    expect(any_instance_of(int))

refused.with_message_containing("<any int> is a matcher, so it belongs in an expectation")
```

`<any int>` there is the matcher's `repr`, which is the phrase it stands for,
because that is the text a reader meets in the message it turns up in. One place
a matcher does not reach: `in` against a `set`, a `frozenset` or a mapping's
keys is a hash lookup rather than a scan, so nothing is ever compared against it
and `expect({1, 2}).contains(any_instance_of(int))` finds nothing. Sequences,
mappings' values and recorded call arguments are all scans, and work.

---

This document describes the code it was generated from: Python 3.13+,
zero runtime dependencies. Assertions that are planned but not yet written are
deliberately absent — see [CHANGELOG.md](../../CHANGELOG.md) for what has shipped.
