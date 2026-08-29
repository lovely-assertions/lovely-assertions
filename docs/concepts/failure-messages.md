# Failure messages

The message is the product. This page is the grammar every message follows, and
the rules behind it — useful when you are predicting what a failure will say, and
required reading when you are [writing your own assertions](../guides/extending.md).

## The grammar

Every message in the library is assembled in exactly one place, from one template:

```
Expected {subject} {expectation}[ because {reason}].
[optional detail block]
```

Four parts, two of them optional — the brackets in the template say which:

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [10, 20, 31]
try:
    expect(daily_totals).is_equal_to([10, 20, 30], because="the ledger is authoritative")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to equal [10, 20, 30], but was [10, 20, 31] because the ledger is authoritative.
  first difference at index 2: 31 instead of 30
```

| Part | Here | Comes from |
|---|---|---|
| **subject** | `daily_totals` | recovered from your source, or `name=` / `described_as` |
| **expectation** | `to equal [10, 20, 30], but was [10, 20, 31]` | the assertion |
| **reason** | `because the ledger is authoritative` | your `because=` |
| **detail block** | `first difference at index 2: …` | the difference engine, when there is more to say |

The reason ends the first sentence; the detail block follows it. That ordering is
deliberate — appending your reason after a multi-line diff would leave it
dangling off the last line of the diff, where nobody reads it.

## Rule 1 — say what was expected *and* what was there

Half a message is one that tells you what you asked for and makes you go and find
out what you got:

```text
Expected server_config to contain key 'hostname'.
```

The whole one does both, and volunteers the near miss:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432}
try:
    expect(server_config).contains_key("hostname")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host', 'port'].
```

The reader should not have to re-run anything to understand a failure.

## Rule 2 — distinguish failures that look alike

This is where the library earns its place over a diff. Two failures that a
`==` comparison renders almost identically are different bugs with different
fixes, so they get different sentences:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"port": 8080}

try:
    expect(server_config).contains_entry("port", 9090)
except AssertionFailure as failure:
    print(failure)

try:
    expect(server_config).contains_entry("timeout", 30)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain entry 'port': 9090, but that key held 8080.
Expected server_config to contain entry 'timeout': 30, but the key was missing; the keys were ['port'].
```

*The key holds a different value* and *the key is missing* are two sentences
because they send you to two different places. When an assertion cannot tell two
causes apart, that is a reason to reconsider the assertion — not to write a
vaguer message.

## Rule 3 — always bounded

A message nobody reads is not a message. Every rendering is capped: a collection
prints its first few items and counts the rest, one value prints about a terminal
line, a diff prints a screenful, a difference descends a couple of levels into
nested structure.

```python
from lovely_assertions import expect, AssertionFailure

audit_rows = list(range(5000))
try:
    expect(audit_rows).is_equal_to(list(range(4999)))
except AssertionFailure as failure:
    print(len(str(failure)) < 500)
```

```text
True
```

Comparing two five-thousand-element lists costs you a few hundred characters
rather than sixty thousand. When you are past skimming and need the
whole thing, [raise the bounds for a block](../guides/controlling-output.md).

## Rule 4 — the expectation is a sentence *fragment*

An assertion never writes a whole sentence. It writes the middle of one:

```
"to be sorted, but 1 at index 1 came after 3: [3, 1, 2]"
```

Lower case, no leading `Expected`, no trailing full stop. The one place that
assembles messages adds the subject in front and the reason and the stop behind.
This is what makes subject naming, `because=` and soft scopes work for every
assertion without any of them wiring it up — including
[yours](../guides/extending.md).

## Rule 5 — values render through the registry

Values inside a message go through the formatter registry rather than a raw
`repr` at the call site. That is what lets you teach every message how your
domain types read, in one place:

```python
from lovely_assertions import expect, register_formatter, AssertionFailure


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyFormatter:
    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Money)

    def format(self, value: object, /) -> str:
        assert isinstance(value, Money)
        return f"GBP {value.cents / 100:.2f}"


register_formatter(MoneyFormatter())

price = Money(1250)
try:
    expect(price).is_equal_to(Money(999))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected price to equal GBP 9.99, but was GBP 12.50.
```

Without the formatter, both sides of that message would have been a memory
address. See [Controlling output](../guides/controlling-output.md).

## Where the subject name comes from

At failure time — and only at failure time — the library walks out to your frame,
parses the statement being executed, and recovers the expression handed to
`expect()`. It is Python's answer to C#'s `[CallerArgumentExpression]`.

It needs the caller's source and an unambiguous answer. Two `expect()` calls in
one statement, or no source file at all (a REPL, `exec`, a `.pyc` without its
`.py`), and it says `the value` instead — because an ambiguous guess would be a
*wrong* name, which is worse than no name.

Nothing about this runs when an assertion passes. `ast` and `linecache` are not
even imported until a failure happens.

Two ways to say the name yourself, for the cases where recovery has nothing
useful to recover — a loop variable, or a helper whose parameter is not the name
the reader knows:

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

`expect(value, name="...")` is the same thing said a step earlier.

## Why not just a diff?

Because a diff is the answer to "what is different", and the question a failing
test asks is "what is wrong". Those coincide when the two values are scalars, and
diverge as soon as they are not. This library is the bet that the second question
is the one worth answering, and every rule above follows from it.

---

See also: [Reading a failure](../getting-started/reading-failures.md) ·
[Controlling output](../guides/controlling-output.md) ·
[Extending](../guides/extending.md)
