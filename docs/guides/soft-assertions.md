# Soft assertions

By default an assertion raises, so a test stops at the first thing wrong. That is
the right default — but it means a run tells you about one problem, you fix it,
you run again, and it tells you about the next.

`soft_assertions()` collects every failure in a block and reports them together:

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure

server_config = {"host": "db-01", "port": 8080}
try:
    with soft_assertions():
        expect(server_config).contains_key("hostname")
        expect(server_config).contains_entry("port", 5432)
        expect(server_config).has_length(5)
except AssertionFailure as failure:
    print(failure)
```

```text
3 assertions failed:
  (1) Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host', 'port'].
  (2) Expected server_config to contain entry 'port': 5432, but that key held 8080.
  (3) Expected server_config to have 5 entries, but had 2 entries with keys ['host', 'port'].
```

One run, the whole picture. The block runs to the end; the failure is raised when
it exits.

## When to reach for it

**Good uses**

- Validating several independent fields of one response, record or config.
- A parametrised check where the failures are more informative together — three
  rows wrong tells you something one row wrong does not.
- Any assertion sequence where the later ones do not depend on the earlier ones
  being true.

**Bad uses**

- When a later assertion would *crash* if an earlier one failed. Collecting
  `expect(user).is_not_none()` and then reading `user.name` gets you an
  `AttributeError`, not a report.
- As a default wrapper around every test. A test that fails softly everywhere
  usually wants splitting into several tests.

## Chains keep going

This is the part that surprises people, and it is deliberate:

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure

hostname = "db-01"
try:
    with soft_assertions():
        expect(hostname).starts_with("web-").and_.ends_with(".local").and_.has_length(99)
except AssertionFailure as failure:
    print(failure)
```

```text
3 assertions failed:
  (1) Expected hostname to start with 'web-', but was 'db-01'.
  (2) Expected hostname to end with '.local', but was 'db-01'.
  (3) Expected hostname to have length 99, but 'db-01' has length 5.
```

Outside a soft scope that chain stops at the first failure and reports one thing.
Inside one, a failed assertion still returns its subject, so the chain continues
and all three are collected.

## Everything reports through it

Soft scopes are not a feature of a few assertions. Every failure in the library
goes through one place, which is what makes them work everywhere without any
assertion wiring it up — including
[exception assertions](exceptions.md), [warning assertions](warnings.md), nested
[`satisfies`](any-value.md#nested-assertions-satisfies) inspections, and
[assertions you wrote yourself](extending.md).

## A real error still wins

If your code raises inside the block, that exception propagates — it is not
collected and not swallowed. The failures gathered so far are attached to it as
notes, so you do not lose them:

```python
from lovely_assertions import expect, soft_assertions

try:
    with soft_assertions():
        expect(1).is_equal_to(2)
        raise RuntimeError("the fixture blew up")
except RuntimeError as error:
    print(type(error).__name__)
    for note in error.__notes__:
        print(note)
```

```text
RuntimeError
1 assertion had already failed in this scope:
  (1) Expected 1 to equal 2, but was 1.
```

This is the right way round. A `RuntimeError` from your own code means the test
did not get to run properly, and reporting three assertion failures as though it
had would be misleading. The notes keep the context without pretending.

## Naming a scope

A scope takes a name, and it **prefixes every subject the block reports on**:

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure

try:
    with soft_assertions("payload"):
        expect(1).is_equal_to(2)
        with soft_assertions("headers"):
            expect(3).is_equal_to(4)
        expect(5).is_equal_to(6)
except AssertionFailure as failure:
    print(failure)
```

```text
3 assertions failed:
  (1) Expected payload/1 to equal 2, but was 1.
  (2) Expected payload/headers/3 to equal 4, but was 3.
  (3) Expected payload/5 to equal 6, but was 5.
```

Nested scopes compose their names with `/`, so a long report says which part of
the value each finding came from. An inner scope hands its failures **up** to the
scope containing it, so only the outermost one raises — which means a helper that
opens its own scope composes whether or not its caller has one.

Nesting without names is safe and buys you nothing: the inner findings arrive in
the outer report indistinguishable from the rest. Name them, or do not nest.

## Scoping formatters to a block

`soft_assertions` is also the sanctioned way to change *rendering* for one block,
overriding the globally registered formatters for as long as it runs:

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure


class Terse:
    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, list)

    def format(self, value: object, /) -> str:
        assert isinstance(value, list)
        return f"<{len(value)} rows>"


audit_rows = [1, 2, 3]
try:
    with soft_assertions(formatters=(Terse(),)):
        expect(audit_rows).is_equal_to([1, 2])
except AssertionFailure as failure:
    print(failure)
```

```text
1 assertion failed:
  (1) Expected audit_rows to equal <2 rows>, but was <3 rows>.
        lengths differ: 3 items, expected 2
        extra items: [3]
```

Global registration is write-once at import, because assertion state a test can
mutate stops being safe the moment the runner goes parallel. This is the per-test
escape hatch. See [Controlling output](controlling-output.md).

## Taking the failures instead of raising

`scope.discard()` hands you the collected messages and leaves the scope with
nothing to raise:

```python
from lovely_assertions import expect, soft_assertions

with soft_assertions() as scope:
    expect(1).is_equal_to(2)
    collected = scope.discard()

print(collected)
```

```text
['Expected 1 to equal 2, but was 1.']
```

Useful when you are testing assertion behaviour itself, or aggregating findings
into a report of your own rather than a test failure.

## The scope object

`soft_assertions()` returns a `SoftScope`. You can hold on to it:

```python
from lovely_assertions import expect, soft_assertions, AssertionFailure

scope = soft_assertions()
try:
    with scope:
        expect(1).is_equal_to(2)
except AssertionFailure as failure:
    print(failure)
```

```text
1 assertion failed:
  (1) Expected 1 to equal 2, but was 1.
```

Note the singular — "1 assertion failed", not "1 assertions failed". The count
reads as English, because the message is meant to be read.

A scope is **not reentrant** — you cannot enter the same one twice at once — but
it is reusable once it has closed.

## Thread and task safety

The active scope lives in a `ContextVar`, not a global. One thread's or one
asyncio task's collected failures never reach another's, so a suite that runs in
parallel does not turn a fixed message into a flaky one.

Nothing about a soft scope costs a passing assertion anything: the `ContextVar`
is read on the failure path only.

---

**See also:** [reading a failure](../getting-started/reading-failures.md) ·
[any value](any-value.md) · [extending](extending.md)
