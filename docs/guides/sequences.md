# Sequences

`expect(some_list)` — or a tuple, a `range`, `bytes` — gives you a
`SequenceExpect`. It **inherits the whole of [`CollectionExpect`](collections.md)**
and adds everything that only makes sense when there is an order and an index.

Read [collections](collections.md) first for membership, length and set
relations. This page is the order-aware half.

> Full signatures: [`SequenceExpect[E]` in the reference](../reference/assertions.md#sequenceexpecte).

## Position

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
expect(daily_totals).has_element_at(0, 3)

try:
    expect(daily_totals).has_element_at(0, 99)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to have 99 at index 0, but had 3: [3, 1, 2].
```

Because a sequence has positions, **the inherited assertions report them too**.
The same `does_not_contain` that says only "it was there" on a set tells you
*where* on a list:

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
try:
    expect(daily_totals).does_not_contain(3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals not to contain 3, but found it at index 0: [3, 1, 2].
```

## Sorting

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
try:
    expect(daily_totals).is_sorted()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to be sorted, but 1 at index 1 came after 3: [3, 1, 2].
```

That message is the library's flagship example: it names the offending pair
*and* its index. `assert totals == sorted(totals)` gives you two lists and a
staring contest.

`is_sorted_descending`, `is_not_sorted` and `is_not_sorted_descending` complete
the set.

**`is_not_sorted` is the exact negation of `is_sorted`, and that has a
consequence worth seeing once.** Both are about *non-strict* order, so equal
neighbours count as sorted — and a sequence with fewer than two items cannot hold
a violation, so it is sorted and `is_not_sorted` always fails on it:

```python
from lovely_assertions import expect, AssertionFailure

try:
    expect([1]).is_not_sorted()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected [1] not to be sorted, but it was: [1].
```

## Order of items

Two assertions that differ by one word and by everything else:

| | Requires the items to appear |
|---|---|
| `contains_in_order(a, b, c)` | in that relative order, **anything may come between** |
| `contains_in_consecutive_order(a, b, c)` | in that order and **adjacent** |

```python
from lovely_assertions import expect, AssertionFailure

event_log = ["opened", "validated", "paid", "shipped"]
expect(event_log).contains_in_order("opened", "shipped")

try:
    expect(event_log).contains_in_consecutive_order("opened", "shipped")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected event_log to contain ('opened', 'shipped') in consecutive order, but other items came between them: ['opened', 'validated', 'paid', 'shipped'].
```

The failure says *which* condition was not met — "other items came between them"
rather than a flat refusal — so you can tell immediately whether your expectation
or your code is wrong.

`does_not_contain_in_order` and `does_not_contain_in_consecutive_order` are the
complements.

## Prefix and suffix

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
expect(daily_totals).starts_with_sequence([3, 1])

try:
    expect(daily_totals).ends_with_sequence([9])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to end with [9], but differed at index 2 (2 instead of 9).
```

## Whole-sequence comparison

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
try:
    expect(daily_totals).equals_sequence([3, 1, 9])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to equal [3, 1, 9], but differed at index 2 (2 instead of 9).
```

`equals_sequence` compares **element by element**, so a list can equal a tuple:

```python
from lovely_assertions import expect

daily_totals = [3, 1, 2]
expect(daily_totals).equals_sequence((3, 1, 2))
print("a list equals an equal tuple")
```

```text
a list equals an equal tuple
```

That is the difference from `is_equal_to`, where `[3, 1, 2] == (3, 1, 2)` is
`False`. Use `equals_sequence` when the container type is not what you are
testing, and `is_equal_to` when it is. `does_not_equal_sequence` is the
complement.

### Floats

```python
from lovely_assertions import expect, AssertionFailure

measurements = [1.0, 2.0]
try:
    expect(measurements).equals_approximately([1.0, 2.5], tol=0.1)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected measurements to equal [1.0, 2.5] within 0.1, but differed at index 1 (2.0 instead of 2.5).
```

## Element by element

`satisfies_respectively` pairs each element with an inspector, **in order**:

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [3, 1, 2]
try:
    expect(daily_totals).satisfies_respectively(
        lambda total: expect(total).described_as("first").is_equal_to(3),
        lambda total: expect(total).described_as("second").is_equal_to(9),
        lambda total: expect(total).described_as("third").is_equal_to(2),
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to satisfy its assertions respectively.
  - at index 1: Expected second to equal 9, but was 1
```

It requires the sequence and the inspector list to be the same length, and it
tells you *which index* failed. For an order-independent version, see
[`satisfies_in_any_order`](collections.md#order-independent-comparison).

## Extracting stays a sequence

On a sequence, `extracting` gives you back a **sequence** subject, so the ordered
catalogue is still available:

```python
from lovely_assertions import expect

orders = [{"total": 10}, {"total": 20}]
expect(orders).extracting(lambda order: order["total"]).is_sorted()
print("still ordered")
```

```text
still ordered
```

On an unordered collection it gives back a collection instead, and `is_sorted` is
not offered — because the order of that list would be the *source's* iteration
order, which for a `set` means hash order. That would be an assertion that passes
or fails at random.

## Gotchas

### `satisfies_respectively` takes inspectors, not predicates

```python
from lovely_assertions import expect

daily_totals = [3]
try:
    expect(daily_totals).satisfies_respectively(lambda total: total == 3)
except TypeError as error:
    print(error)
```

```text
the callback returned True instead of asserting anything, so this would have passed whatever the subject was. An inspector asserts; a predicate returns a verdict. use `satisfies_in_any_order` to pass a predicate, or assert instead: `lambda it: expect(it).is_positive()`
```

A callback that returned a boolean would make the assertion pass whatever the
sequence held. It is caught at the call, with both fixes named.

### `bytes` is a sequence of integers

```python
from lovely_assertions import expect, AssertionFailure

payload = b"abc"
try:
    expect(payload).starts_with_sequence(b"x")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected payload to start with [120], but differed at index 0 (97 instead of 120).
```

`b"abc"[0]` is `97` in Python, so the elements really are integers and the
message shows them as such. Nothing is wrong here — but it is worth seeing once
before you meet it in a failing test.

### A `str` is not a sequence subject

`expect("abc")` gives you a [`StringExpect`](strings.md), not a
`SequenceExpect[str]`, even though a `str` *is* a `Sequence[str]`. The dispatch
puts `str` first deliberately — see [Typed dispatch](../concepts/typed-dispatch.md).

Nor does a **generator** get any of this: it is not a `Collection`, has no
length, and asserting on it would consume it.

---

**See also:** [collections](collections.md) · [any value](any-value.md) ·
[matchers](matchers.md)
