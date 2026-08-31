# Reading a failure

This is the half of the library you actually bought. A passing assertion is a
comparison; a failing one has to end an investigation.

## The shape of every message

Every failure is one sentence with three parts:

```
Expected <the value> to <what should have been true>, but <what was there instead>.
```

```python
from lovely_assertions import expect, AssertionFailure

user_age = 15
try:
    expect(user_age).is_greater_than(18)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected user_age to be greater than 18, but was 15.
```

Three facts, none of which you have to go and look up: *which* value, what was
required of it, and what it actually held. Compare that with what a bare
`assert user_age > 18` gives you, which is the first two thirds of it at best.

## Where the name comes from

`user_age` in that message was never typed twice. At failure time — and only at
failure time — the library walks out to your frame, parses the statement being
executed, and recovers the expression you handed to `expect()`. It is Python's
answer to C#'s `[CallerArgumentExpression]`.

It recovers expressions, not just names:

```python
from lovely_assertions import expect, AssertionFailure

row = {"a": 1}
try:
    expect(row["a"] + 1).is_equal_to(3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected row["a"] + 1 to equal 3, but was 2.
```

**This is why naming your variables well is the cheapest improvement available to
your failure messages.** `expect(t)` and `expect(order_total)` cost the same to
write and produce very different failures.

### When it cannot tell

Recovery needs the caller's source and an unambiguous answer. If the statement
holds several `expect()` calls the library cannot tell which one failed, or if
the code has no source file at all — a REPL, `exec`, a `.pyc` without its
`.py` — an ambiguous answer would be a *wrong* name in a message, which is worse
than no name. So it says `the value` instead, and the rest of the sentence still
carries the assertion and the actual value.

You are never at its mercy. Two ways to say the name yourself, and both also read
better than a recovered expression when the expression is long:

```python
from lovely_assertions import expect, AssertionFailure

try:
    expect(15, name="user_age").is_greater_than(18)
except AssertionFailure as failure:
    print(failure)

try:
    expect(15).described_as("the applicant's age").is_greater_than(18)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected user_age to be greater than 18, but was 15.
Expected the applicant's age to be greater than 18, but was 15.
```

`name=` is for when you have a value and not an expression — a loop variable, a
parsed row. `described_as` is for when the *English* is what the reader needs:
it goes in the sentence as written, so write it as a noun phrase that fits after
"Expected".

## Adding your reason

`because=` appends the fact a reader would otherwise have to go and find:

```python
from lovely_assertions import expect, AssertionFailure

retry_budget = 0
try:
    expect(retry_budget).is_positive(because="the outbound queue retries on 429")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected retry_budget to be positive, but was 0 because the outbound queue retries on 429.
```

It is appended, never interpolated, so it cannot break the sentence, and a
passing assertion never renders it.

**A string literal there is free; an expression is not.** `because=` is an
ordinary argument, so Python evaluates whatever you write before the call —
`because=f"tenant {load_tenant()}"` runs `load_tenant()` on every passing
assertion. Keep it a literal, and if the reason needs computing, compute it in
the failure path of your own code.

## Composite values get a difference

When the two sides of an equality are structures rather than scalars, the
sentence is followed by an indented block saying *where* they part company. The
block is chosen by what the values are.

**A mapping** names the key:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 8080, "tls": True}
try:
    expect(server_config).is_equal_to({"host": "db-01", "port": 5432, "tls": True})
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to equal {'host': 'db-01', 'port': 5432, 'tls': True}, but was {'host': 'db-01', 'port': 8080, 'tls': True}.
  values differ at key 'port': 8080 instead of 5432
```

**A sequence** names the index:

```python
from lovely_assertions import expect, AssertionFailure

daily_totals = [10, 20, 31, 40]
try:
    expect(daily_totals).is_equal_to([10, 20, 30, 40])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected daily_totals to equal [10, 20, 30, 40], but was [10, 20, 31, 40].
  first difference at index 2: 31 instead of 30
```

**Multi-line text** gets a unified diff:

```python
from lovely_assertions import expect, AssertionFailure

rendered = "line one\nline TWO\nline three\n"
try:
    expect(rendered).is_equal_to("line one\nline two\nline three\n")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected rendered to equal 'line one\nline two\nline three\n', but was 'line one\nline TWO\nline three\n'.
  the strings differ (- expected, + actual):
    @@ -1,3 +1,3 @@
     line one
    -line two
    +line TWO
     line three
```

## Messages stay a readable size

Every rendering is bounded. A collection prints its first few items and counts
the rest; one value prints about a terminal line; a diff prints a screenful. So
comparing two five-thousand-element lists gives you a few hundred characters, not
sixty thousand — the message stays skimmable, which is what you need when you are
working out *which* assertion broke.

The default shows ten items. When you are past skimming and debugging the value
itself, that is exactly wrong, so you raise it for a block:

```python
from lovely_assertions import expect, formatting, AssertionFailure

rows = list(range(60))
try:
    with formatting(max_items=25):
        expect(rows).contains(999)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected rows to contain 999, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, ... (35 more)].
```

[Controlling output](../guides/controlling-output.md) covers the full set of
bounds, and how to teach a message to render your own domain types instead of
falling back to `repr`.

## Failures are ordinary `AssertionError`s

`AssertionFailure` derives from `AssertionError`, so pytest and `unittest` count
it as a failed test rather than an erroring one, and `pytest.raises(AssertionError)`
catches it.

The library's own frames are hidden from the traceback — pytest reports the line
in *your* test, not machinery inside `_core` — while a genuine bug inside the
library keeps its full traceback.

---

Next: [Chaining and narrowing](chaining-and-narrowing.md).
