# Chaining and narrowing

Every assertion returns something you can keep asserting on. That gives you two
different things: a way to write several checks about one value without repeating
its name, and a way to move *down* into a value while the type checker follows
you.

## Chaining: staying on the same value

Assertions return their own subject, so they compose directly. `and_` is a no-op
property whose only job is to make the chain read as a sentence.

```python
from lovely_assertions import expect

release_tag = "v2.14.0-rc1"
expect(release_tag).starts_with("v").and_.contains("-rc").and_.has_length(11)
print("chained")
```

```text
chained
```

The chain short-circuits: the first failure raises, and nothing after it runs.
That is the same behaviour as separate statements, and it is usually what you
want. When it is not — when you would rather learn about all three problems at
once — reach for [soft assertions](../guides/soft-assertions.md).

Chaining is a readability tool, not a requirement. Three separate `expect()`
lines are just as correct and often clearer when the assertions are unrelated.

## Narrowing: `.subject`

`.subject` hands back the value the chain is holding, re-typed by whatever you
have proved about it. This is the feature that a plain `assert` cannot give you.

```python
from lovely_assertions import expect

raw: str | None = "db-01"
hostname = expect(raw).is_not_none().subject
print(hostname.upper())
```

```text
DB-01
```

To both pyright and mypy, `hostname` there is a `str` — not `str | None`, not
`object`, and no `cast` was written. The same works for a type check:

```python
from lovely_assertions import expect


def read_port(payload: object) -> int:
    port = expect(payload).is_instance_of(int).subject
    return port + 0


print(read_port(8080))
```

```text
8080
```

### The honest limitation

The *original variable* is not narrowed. After

```python
from lovely_assertions import expect

raw: str | None = "db-01"
expect(raw).is_not_none()
print(type(raw).__name__)
```

```text
str
```

`raw` is still `str | None` as far as a checker is concerned, even though it is
plainly a `str` at runtime. Python's `TypeGuard` and `TypeIs` can only narrow a
function's *first positional argument*, and `expect()` captures the value inside
a wrapper, putting the caller's variable out of reach.

So narrowing flows through the value the chain returns, not backwards into the
variable you started from. **Rebind, and you have a statically guaranteed type:**

```python
from lovely_assertions import expect

raw: str | None = "db-01"
hostname = expect(raw).is_not_none().subject  # str, from here on
expect(hostname).starts_with("db-")
print("rebound and re-entered")
```

```text
rebound and re-entered
```

No Python assertion library does better than this. This one says so rather than
implying otherwise.

## Descending: `.which`, `.and_` and `.whose_value`

Some assertions do not just pass or fail — they *find* something. Those return a
continuation offering three ways forward:

| | Continues on | Use when |
|---|---|---|
| `.and_` | the original subject | you have more to say about the whole thing |
| `.which` | the value that was found, as a **subject** | you want to keep asserting on the part |
| `.subject` | the value that was found, as a **plain value** | you want to leave the library |

```python
from lovely_assertions import expect

server_config = {"host": "db-01.internal", "port": 5432}
expect(server_config).contains_key("host").whose_value.is_equal_to("db-01.internal")
expect(server_config).contains_key("port").and_.contains_key("host")
print("descended, then came back up")
```

```text
descended, then came back up
```

`whose_value` is a mapping's spelling of `.which` — the same continuation, named
for what it holds. Reading `contains_key("host").whose_value.is_equal_to(...)`
aloud is the point.

### The found value keeps its own catalogue

When you name a type, the continuation gives you that type's subject, with its
assertions:

```python
from lovely_assertions import expect


def check(payload: object) -> None:
    expect(payload).is_instance_of(str).which.starts_with("db-")


check("db-01")
print("string assertions, on a value that was an object a line ago")
```

```text
string assertions, on a value that was an object a line ago
```

`is_instance_of(str).which` is a `StringExpect`, statically. `as_type(str)` is
the same move in one step, for when the type check is a step on the way rather
than the point:

```python
from lovely_assertions import expect


def check(payload: object) -> None:
    expect(payload).as_type(str).starts_with("db-")


check("db-01")
print("same thing, said shorter")
```

```text
same thing, said shorter
```

Use `is_instance_of(...)` with `.and_` when you still have something to say about
the original subject; use `as_type(...)` when you do not.

**Not every type gets a specialised subject here.** `as_type(str)` gives you a
`StringExpect` and `as_type(bool)` a `BoolExpect`, but `as_type(int)` gives you a
plain `Expect[int]` rather than a `NumericExpect`. The continuation is overloaded
on the type you *named*, and that list is deliberately short. Where you want the
numeric catalogue, take the value out and re-enter:

```python
from lovely_assertions import expect


def check(payload: object) -> None:
    port = expect(payload).is_instance_of(int).subject
    expect(port).is_between(1, 65535)


check(5432)
print("re-entered for the numeric catalogue")
```

```text
re-entered for the numeric catalogue
```

Re-entering with `expect()` is always available and always gives you the full
catalogue for the value's type. It is the answer whenever a continuation hands
back something more general than you wanted.

## One more rough edge, stated plainly

`expect(rows).subject` on a `list[str]` gives you a `Sequence[str]`, not a
`list[str]`. One subject class covers lists, tuples and every other sequence,
which is what makes the catalogue work at all; the cost is that `.subject` hands
back the abstract type. The element type — the part carrying the information —
survives intact.

The full list of these trade-offs, and what was decided for each, is in
[Type-checker divergences](../concepts/typing-divergences.md).

---

That is the whole of the core model. From here, go by what you are asserting on:
[the guides](../README.md#guides), or straight to
[the reference](../reference/assertions.md).
