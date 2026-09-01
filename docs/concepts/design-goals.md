# Design goals

What this library claims, what it does not, and what it gives up to keep the
claims true.

## The competition is not another library

`assertpy` and `PyHamcrest` are not what this has to beat. **pytest's own
`assert` rewriting** is. pytest rewrites your `assert a == b` into something that
introspects both sides and prints a readable diff, for free, with no import and
no API to learn. Any assertion library that only offers "a nicer way to write
`==`" is worse than the thing already in the room.

So the value has to be somewhere else. It is in three places, and if any of them
stops being true the package has no reason to exist.

## Claim 1 — typed discoverability

`expect(x).` offers only the assertions that are valid for the type of `x`. A
`str` subject has no `is_positive`. A `dict` subject has `contains_key` and a
`list` subject does not.

This is not documentation, it is your editor's completion list, and it is checked
before you run anything:

```python
from lovely_assertions import expect

expect("hello").starts_with("he")
expect([1, 2, 3]).contains_no_duplicates()
expect({"a": 1}).contains_key("a")
expect(3).is_positive()
print("four subjects, four catalogues")
```

```text
four subjects, four catalogues
```

`expect("hello").is_positive()` is a type error your checker reports, not an
`AttributeError` you find at runtime. No library that dispatches dynamically can
do this, which is most of them.

What it costs: the dispatch has to be [one table written twice](typed-dispatch.md)
— an `@overload` chain the checker reads and a branch order the runtime walks —
and the two must never drift.

## Claim 2 — real narrowing

`expect(raw).is_not_none().subject` is a `str` to both pyright and mypy. Not an
`object`, not `Any`, and no `cast` anywhere.

```python
from lovely_assertions import expect

raw: str | None = "db-01"
hostname = expect(raw).is_not_none().subject
print(hostname.upper())
```

```text
DB-01
```

Stated up front rather than discovered: **the original variable is not narrowed.**
`raw` stays `str | None`. `TypeGuard` and `TypeIs` narrow only a function's first
positional argument, and `expect()` captures the value inside a wrapper. Narrowing
flows through the returned subject — rebind it and the type is guaranteed.

And the subject it hands back is a plain `Expect[str]`, not a `StringExpect`, so
Claim 1's catalogue is not on it: `expect(raw).is_not_none().starts_with("db")`
is a type error. Re-specialising would catch a user's own `class Mine(Expect[str])`
as well and hand it back mislabelled, so the
[sound widening was kept](typing-divergences.md#is_not_none-returns-expects-not-a-re-specialised-subject)
and you rebind: `expect(hostname).starts_with("db")`.

No Python assertion library does better on either count; this one says so instead
of implying otherwise.

## Claim 3 — failure messages that explain

The competition prints a diff and stops. This leads with a sentence naming the
subject, what was expected and what was there, then adds a detail block
underneath when there is more to say — where two structures part company, or a
unified diff when the values are multi-line text.

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01"}
try:
    expect(server_config).contains_key("hostname")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host'].
```

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"port": 8080}
try:
    expect(server_config).contains_entry("port", 9090)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain entry 'port': 9090, but that key held 8080.
```

That pair is the argument, though not because pytest confuses the two bugs. It
prints `assert 'hostname' in {'host': 'db-01'}` and `assert 8080 == 9090`, which
already say which one you have. Missing is the near-miss suggestion, which pytest
has no way to reach, and the name of the value under test — in the second case
the key `'port'` as well — which it puts on the source line above the failure
rather than in the message. Under `--tb=line`, in a log, or outside pytest, that
source line is gone and `assert 8080 == 9090` is all that is left. A rejected
expression needs its surroundings; a diagnosis carries them.

An assertion whose message says less than the comparison it replaces is worse
than no assertion at all. That is the bar every assertion here is held to.

## What is given up to keep those true

**Zero runtime dependencies, permanently.** This package is installed into test
suites that already carry their own dependency trees. Adding to somebody else's
tree is a cost they did not choose. Internally this means several things are
built by hand that a dependency would have supplied, and that `re`, `difflib`,
`ast` and friends are imported *inside* the function that needs them rather than
at module level — importing this package imports almost nothing.

**A passing assertion is a comparison and a `return self`.** No frame inspection,
no context lookups, no message built, and your `because=` string never rendered.
Everything expensive — recovering the subject's name, formatting values,
computing a diff — happens only once a failure is certain. See
[Performance](performance.md).

**Both checkers, both strict.** pyright is the reference and mypy is matrixed
alongside it, both at their strictest, both required green. Where the two
genuinely disagree, the disagreement is [written down](typing-divergences.md) and
lived with. **The API is never shaved down to make a checker happy** — that would
trade the product's actual value for a green tick.

## What this does not claim

- **It is not a test framework.** It is a function you import. There is no
  plugin, no fixture, no base class, and no reason to use it for every assertion
  in a file.
- **It does not replace `assert`.** `assert result == 4` says everything already.
  Use this where the value is composite, the failure needs explaining, or the
  narrowing is worth having.
- **It is not faster than `assert`.** Nothing is. It is fast enough that you will
  not measure it in a test suite, which is a different and achievable claim.
- **It does not narrow your variables**, for the reason given above.

## Where to go next

- [Typed dispatch](typed-dispatch.md) — how a value becomes a subject.
- [Failure messages](failure-messages.md) — the grammar, and the rules behind it.
- [Performance](performance.md) — what each path is allowed to cost.
- [Migrating](../guides/migrating.md) — how this maps onto what you write today.
