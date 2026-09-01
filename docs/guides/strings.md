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
`assert "db" in h and "api" in h` gets you pytest's rewriting of the whole
expression — both needles, both haystacks — and leaves you to work out which
half was false.

Every one of them has a `does_not_*` complement. Case-insensitive variants exist
for the single-needle forms only — `contains_ignoring_case` and
`does_not_contain_ignoring_case` — not for `contains_all` or `contains_any`. For
those, `casefold()` both sides yourself: it is the fold the caseless assertions
use, and the one that matches `"straße"` against `"STRASSE"` where `lower()`
does not.

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
and `does_not_match_wildcard_ignoring_case` complete the set.

The two are not interchangeable. `matches` **searches**: `matches("db")` passes
for `"db-01.internal"`, which is why the regex example above anchors with `^`.
Anchor it yourself with `^` and `$`, or reach for `matches_wildcard`, when you
mean the whole string — a wildcard pattern always matches in full, and inside one
a `.` is a full stop rather than a metacharacter.

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

`does_not_contain`, `contains_ignoring_case` and the regex form of `matches`
take the same argument, and all four count non-overlapping matches — `"aaa"`
contains `"aa"` once. Counting it yourself — `expect(log.count("retry")).is_equal_to(3)`
— makes the subject an integer and loses the haystack; see
[Counting occurrences](occurrences.md) for that comparison and the whole set of
constraints.

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
| `is_digit` / `is_not_digit` | is all digits, `"²"` included |
| `is_numeric` / `is_not_numeric` | is all numeric characters, `"½"` and `"Ⅷ"` too |
| `is_alnum` / `is_not_alnum` | is all letters or digits |
| `is_ascii` / `is_not_ascii` | is all ASCII |
| `is_lower` / `is_upper` (and complements) | is all lower / upper case |
| `is_title` / `is_not_title` | is title case |
| `is_space` / `is_not_space` | is all whitespace |
| `is_printable` / `is_not_printable` | is all printable |
| `is_identifier` / `is_not_identifier` | is a valid Python identifier |

An empty string fails every positive form here except `is_ascii` and
`is_printable` — that is `str`'s rule rather than this library's, and the failure
message says so. And if what you mean by `is_digit` is *this parses as an
integer*, it is not that assertion: `"²"` passes it where `int("²")` raises. Use
`matches(r"\A\d+\Z")` for that, or assert on the parsed value.

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

`assert order_ref.isidentifier()` shows you the string it was called on; it does
not show you which character disqualified it.

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
count that was wrong. `is_uuid` returns a continuation: `.and_` carries on with
the string, `.which` carries on with the parsed `UUID`, and `.subject` hands that
`UUID` over unwrapped.

```python
from uuid import UUID

found = expect(request_id).is_uuid()
found.which.is_instance_of(UUID)
print(found.subject.version)
```

```text
4
```

`uuid` is imported inside the assertion rather than at module level, so a suite
that never asserts on one never pays for it.

Pass `version=` when the version is part of what you are asserting — a v4 token
is random, a v1 one carries a timestamp and a MAC address, and accepting either
where you meant one is a real bug:

```python
token = "5b8f0c7e-2a4d-41f9-9c3e-7d1b6a0e2f84"
expect(token).is_uuid(version=4)

try:
    expect(token).is_uuid(version=1)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected token to be a version 1 UUID, but '5b8f0c7e-2a4d-41f9-9c3e-7d1b6a0e2f84' is version 4.
```

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

Case is not the only difference worth forgiving, and the other two are opt-in for
the same reason case is: silently ignoring whitespace would hide a real bug in
code that builds a string by concatenation. `ignoring_whitespace=True` forgives
leading, trailing and internal runs of it; `ignoring_newline_style=True` treats
`\r\n` and `\n` as the same line ending, which is what you want when a fixture
file was written on one platform and read on another. Both are available on
`is_not_equal_ignoring_case` too, and the failure message names whichever ones
were in force.

```python
expect(" Content-Type ").is_equal_ignoring_case("content-type", ignoring_whitespace=True)
expect("first\r\nsecond").is_equal_ignoring_case("FIRST\nSECOND", ignoring_newline_style=True)
```

## Multi-line strings get a diff

Plain `is_equal_to` on a multi-line string produces a unified diff rather than
two reprs you have to compare by eye — see
[Reading a failure](../getting-started/reading-failures.md#composite-values-get-a-difference).
Two short strings are left as the pair of reprs: below a combined repr length
they still fit on one line, and reading them side by side beats diffing them.

---

**See also:** [any value](any-value.md) · [occurrences](occurrences.md) ·
[matchers](matchers.md) for `string_matching` and `string_containing`.
