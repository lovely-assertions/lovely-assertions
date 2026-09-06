# Matchers

A matcher is a placeholder you drop into an expectation where you cannot name the
value but can describe it — a generated id, a timestamp, a token.

```python
from lovely_assertions import expect, any_instance_of, anything

created_row = {"id": 7, "name": "ada", "created_at": "2026-01-04T09:15:00Z"}

expect(created_row).is_equal_to(
    {"id": any_instance_of(int), "name": "ada", "created_at": anything()}
)
print("matched")
```

```text
matched
```

The thing it replaces is three assertions that have lost the shape of the value
under test:

```python
from lovely_assertions import expect

created_row = {"id": 7, "name": "ada", "created_at": "2026-01-04T09:15:00Z"}

expect(created_row["name"]).is_equal_to("ada")
expect(created_row["id"]).is_instance_of(int)
expect(created_row).has_length(3)
print("the same claim, three times, shape gone")
```

```text
the same claim, three times, shape gone
```

One expectation that reads like the record beats three that do not — and it also
catches a *fourth* key appearing, which the three separate assertions only catch
because someone remembered to write `has_length`.

## The catalogue

| Matcher | Matches |
|---|---|
| `anything()` | any value at all |
| `any_instance_of(T)` | any instance of `T` |
| `one_of(a, b, ...)` | any of those values |
| `close_to(x)`, `close_to(x, tol=...)` | a number near `x` |
| `string_matching(pattern)` | a string matching a regular expression |
| `string_containing(text)` | a string containing `text` |
| `containing(items)` | a **mapping** whose entries include those, or a **sequence/set** whose items include those |
| `matching(predicate)` | anything the predicate accepts |

`is_matcher(value)` tells you whether something is one.

## The failure is still specific

A matcher does not cost you the message. It renders as the phrase it stands for:

```python
from lovely_assertions import expect, any_instance_of, anything, AssertionFailure

created_row = {"id": 7, "name": "ada", "created_at": "2026-01-04T09:15:00Z"}
try:
    expect(created_row).is_equal_to(
        {"id": any_instance_of(str), "name": "ada", "created_at": anything()}
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected created_row to equal {'id': <any str>, 'name': 'ada', 'created_at': <anything>}, but was {'id': 7, 'name': 'ada', 'created_at': '2026-01-04T09:15:00Z'}.
  values differ at key 'id': 7 instead of <any str>
```

## Where matchers work

Anywhere a value is **compared**, which is more places than just `is_equal_to`:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, any_instance_of, one_of, AssertionFailure

fetch = Mock()
fetch("/users", retries=3)

try:
    expect(fetch, as_=MockExpect).was_called_with(any_instance_of(str), retries=one_of(0, 1))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have been called with (<any str>, retries=<one of 0, 1>), but was called with ('/users', retries=3).
  keyword arguments:
    values differ at key 'retries': 3 instead of <one of 0, 1>
```

Sequences, mappings' values and recorded call arguments are all scans, and all
work. So does
[`is_equivalent_to`](structural-equivalence.md), where a matcher can stand for a
whole nested record rather than a leaf:

<!-- docs-test: expect-error - the deliberately wrong matcher on the last line is refused by the checker as well as at runtime, which is the second half of the lesson -->

```python
from dataclasses import dataclass

from lovely_assertions import expect, any_instance_of, AssertionFailure


@dataclass
class Author:
    id: int
    name: str


@dataclass
class Post:
    title: str
    author: Author


saved = Post(title="Hello", author=Author(id=7, name="ada"))

expect(saved).is_equivalent_to(Post(title="Hello", author=any_instance_of(Author)))

try:
    expect(saved).is_equivalent_to(Post(title="Hello", author=any_instance_of(str)))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected saved to be equivalent to Post(title='Hello', author=<any str>).
  author: Author(id=7, name='ada') instead of <any str>
  (compared with strict ordering, maximum depth 10)
```

The engine stops at the matcher rather than taking the record apart, which is
what a matcher is for: it says the author is *some* `Author`, and nothing about
the fields inside one.

The second call is there twice over. It shows the message — the matcher renders
as its phrase, not as the private class behind it — and it is *also* a checker
error, because `any_instance_of(str)` is declared `str` and `Post.author` is
declared `Author`. That is the rule below arriving in a real example: a matcher
in a declared slot is checked like anything else, and the wrong one never
reaches a test run.

## The typing argument

The usual objection to this trick comes from Jest, where `expect.any(Number)` is
type-erased: TypeScript sees `any`, so the slot it lands in stops being checked —
`expect.any(String)` drops into a `number` field and nobody complains. Written
inline it costs more than that one slot, since `toEqual` takes `unknown`: a typo
in a *neighbouring* key sails through too. Annotating the expectation checks the
neighbours again, and leaves the matcher's slot exactly as lost.

That is a true account of the trick in JavaScript and a false one here, because a
Python matcher can lie about its type in a way the checker still enforces:

<!-- docs-test: skip - the checker's verdicts are the point, and are pinned in typing_tests/ -->

```python
def any_instance_of[T](kind: type[T]) -> T: ...


assert_type(any_instance_of(int), int)  # passes
rows: dict[str, int] = {"a": any_instance_of(int)}  # accepted
bad: list[int] = [any_instance_of(str)]  # rejected, as it must be
```

A function *declared* to return `T` is statically indistinguishable from a `T`,
so every slot the checker was already policing stays policed — while at runtime
the object is a placeholder whose `__eq__` answers loosely.

`dirty-equals`, the closest thing Python has to this today, cannot do it: its
matchers are their own types, so `list[int]` has to be widened to
`list[int | IsInt]` and the element type stops meaning anything.

### Where the checking actually bites

A matcher is refused where the slot it lands in has a **declared type**: an
annotated variable, a container element, an assertion parameter carrying the
element type. So
`expect(names).contains(any_instance_of(int))` on a `list[str]` is an error, and
so is `rows: dict[str, int] = {"a": any_instance_of(str)}`.

It is **not** refused by `is_equal_to`, whose parameter is `object` on purpose so
that any two values can be compared. An unannotated `{"id": any_instance_of(str)}`
written straight into that call has no slot to be checked against.

**So: declare the expectation rather than inlining it, when you want the checking.**

## Composing matchers

Two matchers combine by **nesting** one inside another, not by joining them with
an operator. `one_of` takes matchers as readily as it takes values, which is how
"an integer, or nothing" is spelled:

```python
from lovely_assertions import expect, any_instance_of, one_of, AssertionFailure

a_row = {"id": any_instance_of(int), "parent": one_of(None, any_instance_of(int))}

expect({"id": 7, "parent": None}).is_equal_to(a_row)
expect({"id": 7, "parent": 3}).is_equal_to(a_row)

orphan = {"id": 7, "parent": "x"}
try:
    expect(orphan).is_equal_to(a_row)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected orphan to equal {'id': <any int>, 'parent': <one of None, <any int>>}, but was {'id': 7, 'parent': 'x'}.
  values differ at key 'parent': 'x' instead of <one of None, <any int>>
```

`containing` nests the same way: `containing({"id": matching(a_positive_id)})`
asks for a mapping whose `id` satisfies a predicate of yours, and says nothing
about the keys beside it.

Everything else is one predicate. A conjunction, a length, an attribute, a
prefix — a `def` says all of them in the language you already write tests in,
and the annotated expectation keeps its element type:

```python
from dataclasses import dataclass

from lovely_assertions import expect, matching


@dataclass
class Order:
    reference: str
    state: str
    lines: list[str]


def a_settled_order(order: Order) -> bool:
    return (
        order.state in {"paid", "shipped"}
        and len(order.lines) > 0
        and order.reference.startswith("AB-")
    )


shipments = {"latest": Order(reference="AB-9", state="shipped", lines=["widget"])}
settled: dict[str, Order] = {"latest": matching(a_settled_order)}
expect(shipments).is_equal_to(settled)
print("three conditions, one slot, still a dict[str, Order]")
```

```text
three conditions, one slot, still a dict[str, Order]
```

That is the same shape libraries elsewhere sell as `all_of`, `having`,
`of_length` and `a_string`. Note what it is *not* for: those spellings are about
one value inside an expectation. A claim about the **subject** has its own
vocabulary already — chain the assertions, or reach for `satisfies_any`.

### Name the predicate

A `def` carries its name into the message. A lambda has nothing to carry:

```python
from lovely_assertions import expect, matching, AssertionFailure

anonymous: dict[str, int] = {"eur": 40, "usd": matching(lambda amount: amount >= 100)}
totals = {"eur": 40, "usd": 7}
try:
    expect(totals).is_equal_to(anonymous)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected totals to equal {'eur': 40, 'usd': <matching a predicate>}, but was {'eur': 40, 'usd': 7}.
  values differ at key 'usd': 7 instead of <matching a predicate>
```

`__name__` is writable, so the phrase in the message is yours to choose. No
registration, no wrapper, nothing to import:

```python
def a_three_figure_sum(amount: int) -> bool:
    return amount >= 100


a_three_figure_sum.__name__ = "a three-figure sum"

totals = {"eur": 40, "usd": 7}
in_the_hundreds: dict[str, int] = {"eur": 40, "usd": matching(a_three_figure_sum)}
try:
    expect(totals).is_equal_to(in_the_hundreds)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected totals to equal {'eur': 40, 'usd': <matching a three-figure sum>}, but was {'eur': 40, 'usd': 7}.
  values differ at key 'usd': 7 instead of <matching a three-figure sum>
```

Bind the expectation to an annotated name, as both blocks above do. An inline
`matching(lambda ...)` written straight into `is_equal_to` has no slot to take
its parameter type from, and neither checker can type it.

**What composition costs.** The message names the predicate and stops there — it
says the value did not match *a three-figure sum*, never which of three
conditions failed. A predicate that bundles unrelated checks buys brevity and
sells the diagnosis; that is the trade, and it is why one well-named predicate
beats one that means four things.

### Why there is no `&`, `|` or `~`

Other libraries offer operators for this. They cannot be typed honestly here,
because a matcher's declared type is the type it stands in for — so what the
operators mean depends entirely on what is being matched:

<!-- docs-test: expect-error - the point of the section: the checker refuses these for a str, and the block prints what happens for an int -->

```python
from lovely_assertions import any_instance_of

try:
    both = any_instance_of(str) & any_instance_of(str)
except TypeError as error:
    print("str &:", error)

try:
    either = any_instance_of(int) | any_instance_of(int)
except TypeError as error:
    print("int |:", error)
```

```text
str &: unsupported operand type(s) for &: 'AnyInstance' and 'AnyInstance'
int |: unsupported operand type(s) for |: 'AnyInstance' and 'AnyInstance'
```

The `str` line is a checker error — `str` has no `&`. The `int` line is not:
`int | int` is perfectly good arithmetic, so the checker accepts it and says the
result is an `int`. Neither one works at runtime.

That asymmetry is the whole argument. An operator set that the checker refuses
for a `str` matcher and blesses for an `int` one is not a feature, it is a
coin-toss — and the `int` half is the bad half, because it is the one that gets
past review. Nesting and a named predicate say the same things and say them the
same way for every type.

## Gotchas

### A matcher belongs in an expectation and nowhere else

```python
from lovely_assertions import expect, anything

try:
    expect(anything())
except TypeError as error:
    print(error)
```

```text
<anything> is a matcher, so it belongs in an expectation rather than under expect(). Its declared type is a deliberate fiction -- the object is a placeholder, not a value of the type it claims -- so an assertion about it would be an assertion about the placeholder. Put it in the expected value instead: expect(row).is_equal_to({'id': any_instance_of(int)}).
```

The declaration is a fiction: `any_instance_of(str)` is annotated `str` and has
no `.upper()`. Never make one the subject and never operate on one. Storing one
as an expectation is fine — an annotated constant is the form the section above
recommends.

### A matcher cannot be found inside a `set`

```python
from lovely_assertions import expect, any_instance_of, AssertionFailure

port_numbers = {80, 443}
try:
    expect(port_numbers).contains(any_instance_of(int))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected port_numbers to contain <any int>, but was {80, 443}.
```

`in` against a `set`, a `frozenset` or a mapping's keys is a **hash lookup**, not
a scan, so nothing is ever compared against the matcher. The same call on a list
works, because a list is scanned:

```python
from lovely_assertions import expect, any_instance_of

port_numbers = [80, 443]
expect(port_numbers).contains(any_instance_of(int))
print("a list is scanned, so the matcher is consulted")
```

```text
a list is scanned, so the matcher is consulted
```

The failing direction at least tells you. The other one does not:
`expect({80, 443}).does_not_contain(any_instance_of(int))` passes, always, and
that test can never fail.

The exclusion is about the *lookup*, not about sets in general: give either call
an `occurrences=` constraint and it counts by scanning, so the matcher is
consulted after all.

```python
from lovely_assertions import expect, any_instance_of, exactly

port_numbers = {80, 443}
expect(port_numbers).contains(any_instance_of(int), occurrences=exactly(2))
print("counted by scanning, so the matcher is consulted")
```

```text
counted by scanning, so the matcher is consulted
```

### `containing` reads a mapping and a sequence differently

`containing({"id": 3})` means "a mapping with at least this entry"; `containing(["a"])`
means "a sequence or set with at least these items". The two are disjoint, not one
rule — a list spec never matches a mapping.

### `matching(predicate)` swallows a raising predicate

A predicate that throws is treated as "did not match". That is the safe direction
for a positive assertion and a trap for a negative one: an assertion that the
value does *not* match can never fail if the predicate always raises. Keep
predicates total.

---

**See also:** [structural equivalence](structural-equivalence.md) for comparing
whole graphs · [mocks](mocks.md) · [any value](any-value.md)
