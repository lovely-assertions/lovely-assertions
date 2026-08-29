# Collections

`expect(some_collection)` gives you a `CollectionExpect` for a container that is
neither a mapping nor a sequence — a `set`, a `frozenset`, a `dict` view. Lists
and tuples get a [`SequenceExpect`](sequences.md) and a `dict` gets a
[`MappingExpect`](mappings.md); **both inherit everything on this page** and add
their own on top.

So: read this page for any container, then [sequences](sequences.md) if yours has
an order.

> Full signatures: [`CollectionExpect[E, C]` in the reference](../reference/assertions.md#collectionexpecte-c).

## Membership

```python
from lovely_assertions import expect, AssertionFailure

order_ids = ["ord-118", "ord-119", "ord-118"]
expect(order_ids).contains("ord-118")
expect(order_ids).does_not_contain("ord-500")

try:
    expect(order_ids).contains_all("ord-118", "ord-999")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids to contain all of ('ord-118', 'ord-999'), but was missing ['ord-999'].
```

`contains_all` names what was missing rather than telling you the whole thing
failed. The family:

| | Passes when |
|---|---|
| `contains(x)` | `x` is in there |
| `contains_all(a, b, ...)` | every one of them is |
| `contains_any(a, b, ...)` | at least one is |
| `contains_none_of(a, b, ...)` | none of them is |
| `does_not_contain(x)` | `x` is not |
| `does_not_contain_all(a, b, ...)` | they are not *all* there — at least one is missing |
| `contains_single()` | there is exactly one item |

On a **sequence** the negative ones say *where* the offender was — a set has no
positions, so there it says only that the item was found:

```python
from lovely_assertions import expect, AssertionFailure

order_ids = ["ord-118", "ord-119", "ord-118"]
try:
    expect(order_ids).does_not_contain("ord-118")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids not to contain 'ord-118', but found it at index 0: ['ord-118', 'ord-119', 'ord-118'].
```

### Counting

`contains` takes an `occurrences=` constraint:

```python
from lovely_assertions import expect, AssertionFailure, exactly

order_ids = ["ord-118", "ord-119", "ord-118"]
try:
    expect(order_ids).contains("ord-118", occurrences=exactly(1))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids to contain 'ord-118' exactly once, but found 2: ['ord-118', 'ord-119', 'ord-118'].
```

See [Counting occurrences](occurrences.md) for the whole set.

## Length and emptiness

```python
from lovely_assertions import expect, AssertionFailure

order_ids = ["ord-118", "ord-119", "ord-118"]
expect(order_ids).is_not_empty()
expect(order_ids).has_length(3)

try:
    expect(order_ids).has_length_greater_than(5)
except AssertionFailure as failure:
    print(failure)

try:
    expect(order_ids).has_same_length_as([1, 2])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids to have more than 5 items, but had 3: ['ord-118', 'ord-119', 'ord-118'].
Expected order_ids to have the same length as [1, 2], but had 3 items against 2.
```

The whole family: `has_length`, `does_not_have_length`,
`has_length_greater_than`, `has_length_greater_than_or_equal_to`,
`has_length_less_than`, `has_length_less_than_or_equal_to`,
`has_length_matching`, `has_same_length_as`, `does_not_have_same_length_as`,
`is_empty`, `is_not_empty`.

`is_none_or_empty` and `is_not_none_or_empty` accept a container that is `None`
without a separate check first. Note that you reach them through a variable
*typed* as optional — `expect(None)` on its own dispatches to the plain
`Expect`, which has no collection catalogue at all.

## Uniqueness

```python
from lovely_assertions import expect, AssertionFailure

order_ids = ["ord-118", "ord-119", "ord-118"]
try:
    expect(order_ids).contains_no_duplicates()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids to have unique items, but 'ord-118' appeared again at index 2: ['ord-118', 'ord-119', 'ord-118'].
```

It names the repeated value *and* where the repeat was, which is the pair you
need. `has_unique_items` is a synonym, for when it reads better.

Both take a **`key=`** selector, for uniqueness on a field rather than on the
whole item:

```python
from lovely_assertions import expect, AssertionFailure

orders = [{"customer": "ada"}, {"customer": "ada"}]
try:
    expect(orders).contains_no_duplicates(key=lambda order: order["customer"])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected orders to have unique items by the key, but 'ada' appeared again at index 1: [{'customer': 'ada'}, {'customer': 'ada'}].
```

`does_not_contain_none` takes one too, and so do
[`is_sorted` and its family](sequences.md#sorting) — sorting a list of records by
a field is the common case.

## Asserting about every item

Four ways, for four different questions.

**`all_are_instance_of`** — every item is of a type:

```python
from lovely_assertions import expect, AssertionFailure

parsed_row = [1, "x"]
try:
    expect(parsed_row).all_are_instance_of(int)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected parsed_row to contain only instances of int, but 'x' at index 1 was str.
```

**`all_equal_to`** and **`contains_only`** — every item is one value:

```python
from lovely_assertions import expect, AssertionFailure

statuses = ["ok", "ok", "failed"]
try:
    expect(statuses).all_equal_to("ok")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected statuses to contain only 'ok', but 'failed' at index 2 did not match: ['ok', 'ok', 'failed'].
```

**`all_satisfy`** — every item passes nested assertions:

```python
from lovely_assertions import expect, AssertionFailure

line_totals = [10, 20, -3]
try:
    expect(line_totals).all_satisfy(lambda total: expect(total).is_positive())
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to satisfy the inspection for every item.
  - at index 2: Expected the value to be positive, but was -3
```

> **`all_satisfy` takes an inspector, not a predicate.** It asserts; it does not
> return a verdict. Handing it `lambda v: v > 0` is caught at the call rather
> than passing silently — see [the gotcha below](#all_satisfy-asserts-it-does-not-return-a-verdict).

**`contains_items_of_type`** is `all_are_instance_of` under the name that reads
better in a sentence, and `all_are_exactly_type` is the strict version — which is
the pair that matters when `bool` is in play:

```python
from lovely_assertions import expect, AssertionFailure

flags = [1, True]
expect(flags).all_are_instance_of(int)

try:
    expect(flags).all_are_exactly_type(int)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected flags to contain only int exactly, but True at index 1 was bool.
```

`does_not_contain_items_of_type` and `does_not_contain_none` are the negatives,
and the second takes a `key=` selector so you can ask it about a field.

**`only_contains`** is the predicate form, for when a boolean really is what you
have:

```python
from lovely_assertions import expect

line_totals = [10, 20, 30]
expect(line_totals).only_contains(lambda total: total > 0)
print("ok")
```

```text
ok
```

## Finding an item

```python
from lovely_assertions import expect, AssertionFailure

order_ids = ["ord-118", "ord-119"]
try:
    expect(order_ids).contains_matching(lambda value: value.startswith("web"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ids to contain an item matching the predicate, but checked 2 items and none matched: ['ord-118', 'ord-119'].
```

`contains_single_matching` additionally requires that exactly one item matches,
and `does_not_contain_matching` is the complement.

`contains_match` and `does_not_contain_match` are the same idea for a **wildcard**
pattern (`*` and `?`) against string items — the same dialect as
[`matches_wildcard`](strings.md#patterns), not a regular expression. They are
offered only on a collection of strings, and that is enforced by the type
checker rather than at runtime.

## Set relations

```python
from lovely_assertions import expect, AssertionFailure

requested_scopes = ["read", "admin"]
try:
    expect(requested_scopes).is_subset_of(["read", "write"])
except AssertionFailure as failure:
    print(failure)

try:
    expect(requested_scopes).is_disjoint_from(["admin"])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected requested_scopes to be a subset of ['read', 'write'], but also had ['admin'].
Expected requested_scopes not to intersect ['admin'], but shared ['admin'].
```

The full set: `is_subset_of`, `is_not_subset_of`, `is_proper_subset_of`,
`is_superset_of`, `is_not_superset_of`, `is_proper_superset_of`, `intersects`,
`does_not_intersect`, `is_disjoint_from`.

Where there are offending elements to name, the message names them — the items
that put you outside the subset, the ones that were shared when they should not
have been. Where the failure is that the two sides are *identical* (a proper
subset that is not proper) there is nothing to point at, and the message says
that instead.

## Asserting on a field of every item

`extracting` transforms the collection into one of a chosen field, and hands you
a subject over that:

```python
from dataclasses import dataclass

from lovely_assertions import expect, AssertionFailure


@dataclass
class Order:
    id: str
    total: int


orders = [Order("ord-118", 40), Order("ord-119", 0)]
expect(orders).extracting(lambda order: order.id).contains("ord-118")

try:
    expect(orders).extracting(lambda order: order.total).only_contains(lambda total: total > 0)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected orders to contain only items matching the predicate, but [0] did not.
```

**The callable form only.** `extracting("total")` is the spelling `assertpy` is
known for, and it cannot be typed: a checker cannot know the attribute exists,
let alone what type it has, so every assertion downstream would be checked
against `Any` — an empty autocomplete list and a type error that never fires. The
callable survives a rename, and the element type is inferred from it.

`extracting` is a transformation, not an assertion. It makes no claim, so it
cannot fail and takes no `because`.

## Order-independent comparison

`satisfies_in_any_order` pairs each item with a predicate, in whatever order
matches:

```python
from lovely_assertions import expect

scopes = ["write", "read"]
expect(scopes).satisfies_in_any_order(
    lambda scope: scope == "read",
    lambda scope: scope == "write",
)
print("matched in any order")
```

```text
matched in any order
```

It takes **predicates**, not inspectors, and the pairing is one-to-one: each
predicate must claim a *distinct* item. That matters — with items `[1, 2]` and
predicates `is_one_or_two, is_one`, matching each predicate independently would
pass, and it would be wrong, because `is_one_or_two` has taken the only item
`is_one` can use. The assignment is solved as a matching instead.

```python
from lovely_assertions import expect, AssertionFailure

scopes = ["write", "read"]
try:
    expect(scopes).satisfies_in_any_order(
        lambda scope: scope == "read",
        lambda scope: scope == "admin",
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected scopes to satisfy every predicate in any order, but no unclaimed item matched the predicate (predicate 2): ['write', 'read'].
```

For a sequence where order *is* the point, see
[`satisfies_respectively`](sequences.md#element-by-element).

## Gotchas

### `all_satisfy` asserts; it does not return a verdict

```python
from lovely_assertions import expect

line_totals = [10, 20, 30]
try:
    expect(line_totals).all_satisfy(lambda total: total > 0)
except TypeError as error:
    print(error)
```

```text
the callback returned True instead of asserting anything, so this would have passed whatever the subject was. An inspector asserts; a predicate returns a verdict. use `only_contains` to pass a predicate, or assert instead: `lambda it: expect(it).is_positive()`
```

An inspector that quietly returned a boolean would make the assertion pass
whatever the collection held — a test that can never fail and never says so. It
is caught at the call, and the message tells you both fixes.

### `contains_only` is not `only_contains`

Two similar names, two different questions:

- **`contains_only(a, b)`** — the collection holds exactly those values, in
  either direction: nothing else is present, and nothing named is absent. About
  *values*.
- **`only_contains(predicate)`** — every item satisfies the predicate. About a
  *condition*.

```python
from lovely_assertions import expect, AssertionFailure

statuses = ["ok", "failed"]
try:
    expect(statuses).contains_only("ok")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected statuses to contain only ('ok',), but also had ['failed'].
```

### A `set` is not a `Sequence`

`expect({1, 2})` gives you a `CollectionExpect`, not a `SequenceExpect`: there is
no indexing and no order to assert about, so `is_sorted` and `has_element_at` are
not offered. That is the dispatch being honest rather than restrictive — see
[Typed dispatch](../concepts/typed-dispatch.md).

---

**See also:** [sequences](sequences.md) · [mappings](mappings.md) ·
[occurrences](occurrences.md) · [matchers](matchers.md)
