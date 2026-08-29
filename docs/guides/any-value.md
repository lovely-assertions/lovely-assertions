# Asserting on any value

These assertions live on `Expect[T]`, the root of every subject. They are
available on **every** value you can pass to `expect()`, whatever its type — a
string subject has them, a mapping subject has them, and so does a subject you
[write yourself](extending.md).

If you learn one page of the catalogue, learn this one.

> Full signatures for everything here: [`Expect[T]` in the reference](../reference/assertions.md#expectt).

## Equality

```python
from lovely_assertions import expect

expect("ord-118").is_equal_to("ord-118")
expect(3).is_not_equal_to(4)
print("ok")
```

```text
ok
```

`is_equal_to` is `==`, with one addition that matters: when both sides are
composite, the failure carries a **difference block** saying where they part
company. Two short strings are not composite, so the failure below is one line —
see [Reading a failure](../getting-started/reading-failures.md#composite-values-get-a-difference)
for what a mapping, a sequence and multi-line text produce instead.

```python
from lovely_assertions import expect, AssertionFailure

order_id = "ord-118"
try:
    expect(order_id).is_equal_to("ord-119")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_id to equal 'ord-119', but was 'ord-118'.
```

When `==` is the wrong question — a `dict` against a dataclass, a field you do
not care about, two timestamps a millisecond apart — reach for
[`is_equivalent_to`](structural-equivalence.md) instead.

## Identity

`is_same_as` is `is`, not `==`. Use it when sharing the *same object* is the
thing under test — a cache returning the instance it stored, a singleton, a
sentinel.

```python
from lovely_assertions import expect, AssertionFailure

cached = [1]
try:
    expect(cached).is_same_as([1])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected cached to be the same object as [1], but was [1].
```

That message reads oddly on purpose: two values that print identically and are
not the same object is exactly the bug `is_same_as` exists to catch, and the
message shows you what the confusion looks like. `is_not_same_as` is the
complement.

## `None`

```python
from lovely_assertions import expect, AssertionFailure

maybe_user = None
try:
    expect(maybe_user).is_not_none()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected maybe_user not to be None, but it was.
```

`is_not_none()` is also the [narrowing](../getting-started/chaining-and-narrowing.md)
workhorse: `expect(raw).is_not_none().subject` is a `str` when `raw` was
`str | None`.

## Truthiness

`is_truthy` and `is_falsy` are `bool(subject)`, and the message tells you what
the value actually was — which is the part `assert not x` never says:

```python
from lovely_assertions import expect, AssertionFailure

retry_budget = 0
try:
    expect(retry_budget).is_truthy()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected retry_budget to be truthy, but it is 0.
```

Prefer the specific assertion where you have one. `is_not_empty()` on a
collection and `is_positive()` on a number both say more than `is_truthy()`, and
`0`, `""`, `[]` and `None` are four different bugs that truthiness flattens into
one.

## Membership

`is_one_of` takes the options as arguments; `is_in` takes a single container.
Use whichever reads better where you are.

```python
from lovely_assertions import expect, AssertionFailure

status = "draft"
try:
    expect(status).is_one_of("open", "closed", "shipped")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected status to be one of ('open', 'closed', 'shipped'), but was 'draft'.
```

```python
from lovely_assertions import expect, AssertionFailure

environment = "staging"
try:
    expect(environment).is_in(("prod", "dev"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected environment to be in ('prod', 'dev'), but was 'staging'.
```

`is_not_in` is the complement. There is no `is_not_one_of`: pass the options as
a container to `is_not_in` instead.

## Types

Three assertions, and the difference between them is the whole point:

| | Asks | A subclass |
|---|---|---|
| `is_instance_of(T)` | `isinstance(subject, T)` | **counts** |
| `is_exactly_instance_of(T)` | `type(subject) is T` | does **not** count |
| `as_type(T)` | `is_instance_of(T)` then continue on the value | counts |

```python
from lovely_assertions import expect, AssertionFailure

payload = 42
try:
    expect(payload).is_instance_of(str)
except AssertionFailure as failure:
    print(failure)

try:
    expect(True).is_exactly_instance_of(int)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected payload to be an instance of str, but was int.
Expected True to be exactly int, but was bool.
```

That second one is the reason `is_exactly_instance_of` exists: `isinstance(True, int)`
is `True` in Python, and sometimes that is precisely what you need to rule out.

`is_not_instance_of` and `is_not_exactly_instance_of` are the complements, and
they differ on exactly the same point: `is_not_instance_of(int)` **fails** for a
`bool`, because a `bool` is an `int`.

All three of the positive forms narrow. See
[Chaining and narrowing](../getting-started/chaining-and-narrowing.md).

## Predicates: `matches`

For a one-off condition with no assertion of its own. Note that on a **string**
subject `matches` takes a regular expression *or* a predicate — the example below
uses the predicate form, and [`matches` on a string](strings.md#patterns) is
usually reached for the other one.

```python
from lovely_assertions import expect, AssertionFailure

order_id = "ord-118"
try:
    expect(order_id).matches(lambda value: value.endswith("999"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_id to match the predicate, but 'ord-118' did not.
```

Note what the message can and cannot say. It has the subject and the value, and
it cannot tell you *what* the predicate wanted — a lambda has no description.
That is the cost of `matches`, and the reason to prefer a real assertion when one
exists. It is a good escape hatch and a poor default.

## Nested assertions: `satisfies`

`satisfies` runs assertions *inside* a value and reports them as one finding:

```python
from lovely_assertions import expect, AssertionFailure

order = {"subtotal": 4000, "shipping": 0, "total": 0}
try:
    expect(order).satisfies(lambda o: expect(o["total"]).described_as("total").is_positive())
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to satisfy the inspection.
  - Expected total to be positive, but was 0
```

**Both names in that message are worth understanding.** The statement contains
two `expect()` calls, so name recovery has no unambiguous answer for either one —
and an ambiguous guess would be a *wrong* name, which is worse than none. So the
outer subject falls back to `the value`, and the inner one reads `total` only
because `described_as` said so.

Name both, and the finding reads properly:

```python
from lovely_assertions import expect, AssertionFailure

order = {"subtotal": 4000, "shipping": 0, "total": 0}
try:
    expect(order, name="order").satisfies(
        lambda o: expect(o["total"]).described_as("its total").is_positive()
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order to satisfy the inspection.
  - Expected its total to be positive, but was 0
```

This is the one place naming is not optional, and it is worth the two calls.

## One of several: `satisfies_any` and `satisfies_none`

`satisfies_any` passes when at least one branch holds, and when none does, it
tells you what *each* branch wanted:

```python
from lovely_assertions import expect, AssertionFailure

status = "draft"
try:
    expect(status).satisfies_any(
        lambda s: s.is_equal_to("open"),
        lambda s: s.is_equal_to("closed"),
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected status to satisfy at least one of 2 alternatives, but none did.
  alternative 1:
    - Expected status to equal 'open', but was 'draft'
  alternative 2:
    - Expected status to equal 'closed', but was 'draft'
```

That is the message a hand-written `assert a or b` cannot give you: it fails with
`assert False` and leaves you to work out which half you expected to hold.

`satisfies_none` is the complement, and names the branch that held:

```python
from lovely_assertions import expect, AssertionFailure

status = "draft"
try:
    expect(status).satisfies_none(lambda s: s.starts_with("dr"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected status to satisfy none of 1 alternatives, but alternative 1 held.
```

Note the branches take the *subject*, not the raw value — `s` there is a
`StringExpect`, which is why `s.starts_with(...)` works. This is the opposite of
`satisfies` above, which hands your callback the plain value and leaves you to
wrap it in `expect()` yourself. The two differ, and it is worth checking which
you are writing.

## Naming and continuing

Three more members that are not assertions at all:

| | Does |
|---|---|
| `described_as("...")` | names the subject for every failure after it |
| `.and_` | hands back the same subject, so a chain reads as a sentence |
| `.subject` | hands back the value, re-typed by what you have proved |

```python
from lovely_assertions import expect, AssertionFailure

for index, row in enumerate([{"ok": True}, {"ok": False}]):
    try:
        expect(row["ok"]).described_as(f"rows[{index}].ok").is_true()
    except AssertionFailure as failure:
        print(failure)
```

```text
Expected rows[1].ok to be True, but was False.
```

`expect(value, name="...")` says the same thing one step earlier.

---

**Next:** the catalogue for whatever you are actually holding —
[strings](strings.md), [numbers](numbers.md), [collections](collections.md),
[sequences](sequences.md), [mappings](mappings.md).
