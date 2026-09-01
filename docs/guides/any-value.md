# Asserting on any value

The assertions every value has, whatever its type: equality, identity, `None`,
truthiness, membership, types and predicates.

They live on `Expect[T]`, the root of every subject — a string subject has them,
a mapping subject has them, and so does a subject you
[write yourself](extending.md). If you learn one page of the catalogue, learn
this one.

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

`is_equal_to` is `==`, with one addition that matters: where the two reprs alone
do not show what went wrong, the failure carries an indented **difference
block** — the key that differs for a mapping, the index for a sequence, a
unified diff for multi-line text, the column for a long single line, and, for
two values whose reprs print the same, the fact that they are unequal at all,
with the cause where there is one to name. Short strings are read faster side by
side than as a diff, so the failure below is one line — see
[Reading a failure](../getting-started/reading-failures.md#composite-values-get-a-difference)
for the other forms.

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

`is_none()` is identity against `None`, never `== None`, so a type with a
permissive `__eq__` cannot talk its way past. `is_not_none()` is the complement:

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

`is_truthy` and `is_falsy` are `bool(subject)`. When `is_truthy` fails, the
message names which *kind* of falsy applied — a zero, an empty container,
`None`, or a `__bool__` that said no:

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

For a zero a bare `assert retry_budget` says as much — pytest rewrites it to
`assert 0`. The last kind is the one it cannot help with: a rewritten assert on
a domain object prints its repr, which is an address.

```python
from lovely_assertions import expect, AssertionFailure


class Cart:
    def __init__(self) -> None:
        self.items: list[str] = []

    def __bool__(self) -> bool:
        return bool(self.items)


cart = Cart()
try:
    expect(cart).is_truthy()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected cart to be truthy, but Cart.__bool__ returned False.
```

Prefer the specific assertion where you have one. `is_not_empty()` on a
collection and `is_positive()` on a number both say more than `is_truthy()`, and
`0`, `""`, `[]` and `None` are four different bugs that truthiness flattens into
one.

## Membership

`is_one_of` compares the subject to each option with `==`. `is_in` asks the
container's own `__contains__`, which is not the same question:
`expect("draft").is_in("drafts")` passes on the substring, and a `range` answers
arithmetically without materialising anything. Write the alternatives out with
`is_one_of`; reach for `is_in` when you already hold the container and mean its
own idea of membership.

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
a container to `is_not_in` instead. `is_one_of` with no options at all raises
`ValueError`, since a call with nothing to look for could never pass.

## Types

Three assertions, and the difference between them is the whole point:

| | Asks | A subclass |
|---|---|---|
| `is_instance_of(T)` | `isinstance(subject, T)` | **counts** |
| `is_exactly_instance_of(T)` | `type(subject) is T` | does **not** count |
| `as_type(T)` | `is_instance_of(T).which`, in one step | counts |

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

`is_instance_of` and `is_exactly_instance_of` hand back a `Found`, not the
subject. `.which` continues on the value re-typed — and re-dispatched, so
`.which` after `is_instance_of(str)` carries the string catalogue — while
`.and_` goes back to the original subject.

```python
from lovely_assertions import expect

incoming: object = "ord-118"
expect(incoming).is_instance_of(str).which.starts_with("ord-")
print("ok")
```

```text
ok
```

`as_type(T)` is those two steps spelled as one, which is why it drops the
original subject. See
[Chaining and narrowing](../getting-started/chaining-and-narrowing.md).

Every assertion here asks about the type *of a value*. To assert about a class
itself — `is_subclass_of`, `implements`, `is_abstract` — pass the class to
`expect()` and see [types and enums](types-and-enums.md).

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

The message has the subject and the value, and nothing about what the predicate
wanted — a lambda has no name to print. Give the predicate one and the message
uses it, which is usually the cheaper fix:

```python
from lovely_assertions import expect, AssertionFailure


def ends_with_999(value: str) -> bool:
    return value.endswith("999")


try:
    expect(order_id).matches(ends_with_999)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_id to match ends_with_999, but 'ord-118' did not.
```

Where the *reason* matters and not just the name, use `satisfies` instead: its
nested assertions each explain themselves.

## Nested assertions: `satisfies`

`satisfies` runs assertions *inside* a value and collects them: one failure
listing everything that was wrong, rather than stopping at the first.

The callback it takes is an **inspector** — a callable that *asserts*. A
callable that *returns a verdict* is a **predicate**, which is what `matches`
above takes. The library refuses to confuse the two: `lambda o: o["total"] > 0`
returns a verdict, which would have passed whatever the subject was, so it
raises `TypeError` at the call and points you at `matches`. Neither checker
catches that one.

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

Naming is needed there because the lambda puts both `expect()` calls in one
statement. Lift the inspector into a function and they are in separate
statements again, so recovery answers for each of them. The inner names are read
from the *helper's* source, so what they show is its parameter — name it after
what it holds:

```python
from collections.abc import Mapping

from lovely_assertions import expect, AssertionFailure


def is_a_paid_order(order: Mapping[str, int]) -> None:
    expect(order["total"]).is_positive()
    expect(order["shipping"]).is_positive()


order = {"subtotal": 4000, "shipping": 0, "total": 0}
try:
    expect(order).satisfies(is_a_paid_order)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order to satisfy the inspection.
  - Expected order["total"] to be positive, but was 0
  - Expected order["shipping"] to be positive, but was 0
```

Two findings from one call: the second assertion ran even though the first had
already failed.

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

A hand-written `assert a or b` can only re-print the expression it was given —
pytest interleaves both comparisons and their diffs into one blob. Here each
branch is a whole assertion chain, so every alternative explains itself in the
words of the assertion that failed.

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
wrap it in `expect()` yourself.

## Naming and continuing

Three more members that are not assertions at all:

| | Does |
|---|---|
| `described_as("...")` | names the subject for every failure on that chain — a new subject from `.which` does not inherit it |
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
