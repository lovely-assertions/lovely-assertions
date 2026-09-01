# Reading a failure

This is the half of the library you actually bought. A passing assertion is a
comparison; a failing one has to end an investigation.

## The shape of a message

Most failures are one sentence, assembled from one template:

```
Expected {subject} {expectation}[ because {reason}].
[optional detail block]
```

Two parts are always there: the **subject** names the value, and the
**expectation** says what was required of it and what was there instead. Two are
optional: the reason you passed as `because=`, and a detail block under the
sentence when there is more to say than the two values. The rest of this page is
those four in use;
[Failure messages](../concepts/failure-messages.md#the-grammar) is the grammar
behind them.

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

`user_age` is the subject, `to be greater than 18, but was 15` the expectation.
Three facts, none of which you have to go and look up: *which* value, what was
required of it, and what it actually held.

pytest's `assert` rewriting shows you the same three — it prints your source line
above `assert 15 > 18`. What it does not do is put them in the *message*:
`str(exc)` is `assert 15 > 18`, with `user_age` gone. So the name survives in the
report and nowhere else — not in the summary line, not in a log, not in a file
pytest never rewrote.

Not every failure is that sentence. The `but` half is absent where there is
nothing to contrast — an inspection reports the failures nested inside it
instead — and a [soft scope](../guides/soft-assertions.md) prints a numbered list
rather than a sentence.

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

They are one mechanism: `expect(value, name=...)` calls `described_as` for you.
Either string lands in the sentence as written, so make it a noun phrase that
fits after "Expected". At your own `expect()` the choice between them is style —
`name=` keeps the name beside the value, `described_as` reads better for a
phrase.

`described_as` reaches two places `name=` cannot. It names a subject you did not
construct: the handle `expect_raises` hands back reports as `the value` until you
describe it. And it renames from the point it appears, where `name=` covers the
whole chain. Reach for either wherever recovery works but is useless — in a loop
recovery names `row["n"]` identically on every iteration, and `f"rows[{index}]"`
says which row it was.

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

When there is more to say than the two values themselves, the sentence is
followed by an indented detail block pinning the difference down. How far it can
pin it depends on what the values are.

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

**A set** has neither a key nor an index, so it names what is missing and what
is extra:

```python
from lovely_assertions import expect, AssertionFailure

allowed_ports = {80, 443, 8080}
try:
    expect(allowed_ports).is_equal_to({80, 443, 9090})
except AssertionFailure as failure:
    print(failure)
```

```text
Expected allowed_ports to equal {80, 9090, 443}, but was {80, 443, 8080}.
  missing items: [9090]
  extra items: [8080]
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

**A long single line** has no lines to diff, so it gets the column it parts at
and the run-up to it:

```python
from lovely_assertions import expect, AssertionFailure

connection_url = "postgresql://user@db-01.internal:5432/analytics_prod"
try:
    expect(connection_url).is_equal_to("postgresql://user@db-01.internal:5433/analytics_prod")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected connection_url to equal 'postgresql://user@db-01.internal:5433/analytics_prod', but was 'postgresql://user@db-01.internal:5432/analytics_prod'.
  first difference at index 36: '2' instead of '3', after ...'r@db-01.internal:543'
```

Two short values get no block at all: both reprs are already in the sentence,
side by side, and a second line would only repeat them.

## Messages stay a readable size

Every rendering is bounded, so even a huge value leaves you a message you can
skim — which is what you need when you are working out *which* assertion broke.
[Controlling output](../guides/controlling-output.md) has what the bounds are,
how to raise them for a block when you are past skimming, and how to teach a
message to render your own domain types instead of falling back to `repr`.

## Failures are ordinary `AssertionError`s

`AssertionFailure` derives from `AssertionError`, so pytest and `unittest` count
it as a failed test rather than an erroring one, and `pytest.raises(AssertionError)`
catches it.

Under pytest the library's own frames are folded out of the traceback, so you
see the line in *your* test rather than machinery inside `_core`, while a genuine
bug inside the library keeps its full traceback. The hook is pytest's own, so
other runners — `unittest`, a bare `python` — show the library's frames under
your line.

---

Next: [Chaining and narrowing](chaining-and-narrowing.md).
