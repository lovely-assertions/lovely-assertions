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

`<any str>` is the matcher's own `repr`, chosen to read as the phrase in a
sentence — because that is the text you meet in a failing test.

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
work.

## The typing argument

The usual objection to this trick comes from Jest, where `expect.any(Number)` is
type-erased: TypeScript sees `any`, the slot it lands in stops being checked, and
a typo in the *neighbouring* key sails through.

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

Stated before anybody is disappointed by it. A matcher is refused where the slot
it lands in has a **declared type**: an annotated variable, a container element,
an assertion parameter carrying the element type. So
`expect(names).contains(any_instance_of(int))` on a `list[str]` is an error, and
so is `rows: dict[str, int] = {"a": any_instance_of(str)}`.

It is **not** refused by `is_equal_to`, whose parameter is `object` on purpose so
that any two values can be compared. An unannotated `{"id": any_instance_of(str)}`
written straight into that call has no slot to be checked against.

**So: declare the expectation rather than inlining it, when you want the checking.**

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

The declaration is a fiction, and the cost is worth stating rather than
discovering: `any_instance_of(str)` is annotated `str` and has no `.upper()`.
Never make one the subject, never store one, never operate on one.

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

The exclusion is about the *lookup*, not about sets in general: give the same
call an `occurrences=` constraint and it counts by scanning, so the matcher is
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
