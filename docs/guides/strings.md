# Strings

`expect(some_str)` gives you a `StringExpect` — a large catalogue, because
strings are what tests assert on most. (The largest is
[`SequenceExpect`](sequences.md), which inherits the whole collection catalogue on
top of its own.)

> Full signatures: [`StringExpect` in the reference](../reference/assertions.md#stringexpect).

## Containment

```python
from lovely_assertions import expect

hostname = "db-01.internal"
expect(hostname).contains("db-01")
expect(hostname).does_not_contain("web")
expect(hostname).contains_any("db", "api")
expect(hostname).contains_all("db", ".internal")
print("ok")
```

```text
ok
```

The `any`/`all` variants exist because the message is the point. Compare what
each tells you when it fails:

```python
from lovely_assertions import expect, AssertionFailure

hostname = "db-01.internal"
try:
    expect(hostname).contains_any("web", "api")
except AssertionFailure as failure:
    print(failure)

try:
    expect(hostname).contains_all("db", "api")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected hostname to contain at least one of ['web', 'api'], but 'db-01.internal' contains none of them.
Expected hostname to contain all of ['db', 'api'], but 'db-01.internal' is missing ['api'].
```

`contains_all` names *which* substring was missing. Writing that by hand as
`assert "db" in h and "api" in h` fails with `assert False` and no such detail.

Every one of them has a `does_not_*` complement. Case-insensitive variants exist
for the single-needle forms only — `contains_ignoring_case` and
`does_not_contain_ignoring_case` — not for `contains_all` or `contains_any`. For
those, lower-case both sides yourself.

## Prefixes and suffixes

```python
from lovely_assertions import expect, AssertionFailure

hostname = "db-01.internal"
try:
    expect(hostname).starts_with("web-")
except AssertionFailure as failure:
    print(failure)

try:
    expect(hostname).ends_with_ignoring_case(".LOCAL")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected hostname to start with 'web-', but was 'db-01.internal'.
Expected hostname to end with '.LOCAL' ignoring case, but was 'db-01.internal'.
```

Also: `does_not_start_with`, `does_not_end_with`, `starts_with_ignoring_case`,
`does_not_start_with_ignoring_case`, and the matching suffix set.

## Patterns

Two flavours, for two audiences.

**Regular expressions**, when you need the power:

```python
from lovely_assertions import expect, AssertionFailure

hostname = "db-01.internal"
try:
    expect(hostname).matches(r"^web-\d+")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected hostname to match the regular expression '^web-\\d+', but was 'db-01.internal'.
```

**Wildcards**, when `*` and `?` say it more clearly than a regex would:

```python
from lovely_assertions import expect, AssertionFailure

hostname = "db-01.internal"
expect(hostname).matches_wildcard("db-*.internal")

try:
    expect(hostname).matches_wildcard("web-*")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected hostname to match the wildcard pattern 'web-*', but was 'db-01.internal'.
```

`matches_wildcard_ignoring_case`, `does_not_match`, `does_not_match_wildcard`
and `does_not_match_wildcard_ignoring_case` complete the set. Reach for a wildcard when the pattern
is about shape rather than structure — it is the version a reader who does not
write regexes daily can still check at a glance.

`re` is imported only when one of these actually runs, so a suite that never
matches a pattern never pays for it.

## Counting occurrences

`contains` takes an `occurrences=` constraint, which turns "is it there" into "is
it there the right number of times":

```python
from lovely_assertions import expect, AssertionFailure, exactly, at_least

log = "retry\nretry\nok\n"
expect(log).contains("retry", occurrences=at_least(1))

try:
    expect(log).contains("retry", occurrences=exactly(3))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log to contain 'retry' exactly 3 times, but found 2.
```

The alternative — `expect(log.count("retry")).is_equal_to(3)` — asserts the same
fact and reports almost none of it: its subject is an integer, so the failure
names `log.count('retry')` and the haystack is gone. See
[Counting occurrences](occurrences.md) for the full set of constraints.

## Length and emptiness

```python
from lovely_assertions import expect, AssertionFailure

hostname = "db-01.internal"
expect(hostname).is_not_empty()
expect("   ").is_blank()

try:
    expect(hostname).has_length(3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected hostname to have length 3, but 'db-01.internal' has length 14.
```

`is_empty` is `== ""`. `is_blank` is "empty or only whitespace", and
`is_not_blank` is its complement — the assertion you want for a field a user was
supposed to fill in.

## Character classes

The `str` predicates, each wrapped so its failure explains itself:

| | True when the string |
|---|---|
| `is_alpha` / `is_not_alpha` | is all letters |
| `is_digit` / `is_not_digit` | is all digits |
| `is_numeric` / `is_not_numeric` | is all numeric characters |
| `is_alnum` / `is_not_alnum` | is all letters or digits |
| `is_ascii` / `is_not_ascii` | is all ASCII |
| `is_lower` / `is_upper` (and complements) | is all lower / upper case |
| `is_title` / `is_not_title` | is title case |
| `is_space` / `is_not_space` | is all whitespace |
| `is_printable` / `is_not_printable` | is all printable |
| `is_identifier` / `is_not_identifier` | is a valid Python identifier |

The reason to use these rather than `assert value.isdigit()` is the same as
everywhere else — the message points at the offending character:

```python
from lovely_assertions import expect, AssertionFailure

order_ref = "ORD-118"
try:
    expect(order_ref).is_digit()
except AssertionFailure as failure:
    print(failure)

try:
    expect(order_ref).is_identifier()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected order_ref to contain only digits, but 'ORD-118' has 'O' at index 0.
Expected order_ref to be a valid Python identifier, but 'ORD-118' has '-' at index 3.
```

`'-' at index 3` is the whole investigation, done. `assert order_ref.isidentifier()`
tells you it failed and nothing else.

## UUIDs

```python
from lovely_assertions import expect, AssertionFailure

request_id = "5f1e3a4c-2b7d-4e91-a8c3-9d2f6b1a7e04"
expect(request_id).is_uuid()

try:
    expect("db-01.internal").is_uuid()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected "db-01.internal" to be a UUID, but 'db-01.internal' has a body of 13 characters, not 32 hexadecimal digits.
```

The message says *why* it is not a UUID rather than only that it is not — the
count that was wrong. `is_uuid` also returns a continuation, so `.which` hands
you the parsed `UUID` object. `uuid` is imported inside the assertion rather than
at module level, so a suite that never asserts on one never pays for it.

## Case-insensitive equality

```python
from lovely_assertions import expect, AssertionFailure

header_name = "Content-Type"
expect(header_name).is_equal_ignoring_case("content-type")

try:
    expect(header_name).is_equal_ignoring_case("content-length")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected header_name to equal 'content-length' ignoring case, but was 'Content-Type'.
```

## Multi-line strings get a diff

Plain `is_equal_to` on a multi-line string produces a unified diff rather than
two reprs you have to compare by eye — see
[Reading a failure](../getting-started/reading-failures.md#composite-values-get-a-difference).

---

**See also:** [any value](any-value.md) · [occurrences](occurrences.md) ·
[matchers](matchers.md) for `string_matching` and `string_containing`.
