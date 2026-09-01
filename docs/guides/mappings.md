# Mappings

`expect(some_dict)` gives you a `MappingExpect` — and so does any other `Mapping`:
`OrderedDict`, `ChainMap`, `MappingProxyType`, or your own.

The organising idea of this page is that **a key, a value and an entry are three
different questions**, and the failure message is different for each. That is
most of what this subject buys you over `assert d == expected`.

> Full signatures: [`MappingExpect[K, V]` in the reference](../reference/assertions.md#mappingexpectk-v).

## Keys, values, entries

```python
from lovely_assertions import expect

server_config = {"host": "db-01", "port": 5432, "tls": True}

expect(server_config).contains_key("host")  # is the key there?
expect(server_config).contains_value("db-01")  # is the value there, under any key?
expect(server_config).contains_entry("port", 5432)  # is that key holding that value?
print("three different questions")
```

```text
three different questions
```

Now watch what each one says when it fails.

### A missing key volunteers the near miss

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).contains_key("hostname")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host', 'port', 'tls'].
```

`(did you mean 'host'?)` is the whole investigation for the commonest mapping
bug there is — a typo or a renamed field. It appears when the key you looked up
is a string and some string key present is close enough to it. The condition is
on the key you asked for rather than on the mapping: mixed key types are fine, a
non-string lookup never gets a suggestion. `contains_entry` carries the same
clause on a missing key; the plural forms below carry none.

### A wrong entry and a missing entry are different sentences

This is the pair the library was built around:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
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
Expected server_config to contain entry 'port': 9090, but that key held 5432.
Expected server_config to contain entry 'timeout': 30, but the key was missing; the keys were ['host', 'port', 'tls'].
```

*The key holds the wrong value* is a bug in the code under test. *The key is
missing* is usually a bug in the contract, or in the test. They send you to
different places. pytest's own diff does separate them — `Differing items:`
against `Right contains 1 more item:` — but only if you build a whole expected
mapping to ask about one field, and it omits the entries that agreed until you
pass `-vv`. `contains_entry` asks about the one entry, and answers in a sentence.

## The plural forms

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).contains_keys("host", "timeout")
except AssertionFailure as failure:
    print(failure)

try:
    expect(server_config).contains_entries({"port": 9090, "tls": False})
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain keys ['host', 'timeout'], but was missing ['timeout']; the keys were ['host', 'port', 'tls'].
Expected server_config to contain entries {'port': 9090, 'tls': False}, but 'port' held 5432 instead of 9090, 'tls' held True instead of False.
```

`contains_entries` reports every entry that disagreed, not just the first — up to
the preview cap, after which the message says how many more there were, and the
echo of what you asked for is capped the same way. Widen both with a
[`formatting` block](controlling-output.md#bounds-formatting).

`contains_values(a, b)` is the same shape for values, and asks only that each
appears *somewhere*, not that it appears under a particular key or that there are
as many entries as values. Counting is a different question:
`contains_value(v, occurrences=at_least(2))` asks how many keys hold it — see
[counting occurrences](occurrences.md).

`contains_only_keys` is the exhaustive version, for asserting a shape:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).contains_only_keys("host", "port")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain only the keys ['host', 'port'], but also had ['tls'].
```

The negatives name what they found: `does_not_contain_key` reports the value that
key held, `does_not_contain_value` the key that held it, and the plural
`does_not_contain_keys` and `does_not_contain_values` list which of the ones you
passed were present. `does_not_contain_entry` can only say the entry was there —
you named both halves yourself, so there is nothing left to report.

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).does_not_contain_key("host")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config not to contain key 'host', but it held 'db-01'.
```

## Descending into a value

`contains_key(...)` returns a
[continuation](../getting-started/chaining-and-narrowing.md), so you can assert on
what the key holds without a second lookup:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
expect(server_config).contains_key("host").whose_value.is_equal_to("db-01")
expect(server_config).contains_key("host").whose_value.as_type(str).starts_with("db-")

try:
    expect(server_config).contains_key("host").whose_value.is_equal_to("db-99")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to equal 'db-99', but was 'db-01'.
```

`.whose_value` is typed as [the universal catalogue](any-value.md) over the value
type, not as a string or a number subject — the value type of a mapping is not
something a checker can turn into one. `is_equal_to` and its neighbours are there
already; the typed catalogue is one step further in, which is why the second line
names the type. `as_type(str)` is `is_instance_of(str).which` in one call.

`.and_` goes back to the mapping instead, so you can keep asserting about the
whole thing:

```python
from lovely_assertions import expect

server_config = {"host": "db-01", "port": 5432, "tls": True}
expect(server_config).contains_key("host").and_.contains_key("port")
print("back up to the mapping")
```

```text
back up to the mapping
```

## The keys and values views

`.keys` and `.values` hand you a **collection subject** over the view, so the
whole of [the collection catalogue](collections.md) applies:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
expect(server_config).keys.contains_all("host", "port")
expect(server_config).values.contains_no_duplicates()

try:
    expect(server_config).keys.contains("nope")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain 'nope', but was ['host', 'port', 'tls'].
```

Note that the message still names `server_config` — the name follows you into the
view, which is what you want in a failure.

A view is a subject in its own right, not a continuation that remembers the
mapping: `.and_` on it re-chains on the view. To ask another question about the
mapping, start a new `expect(...)`.

**They are properties, not methods.** Write `.keys`, not `.keys()`. And there is
no `.items` view: an entry is what `contains_entry` and `contains_entries` are
for.

## Matching

When you cannot name the key or the value exactly:

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).contains_key_matching(lambda key: key.startswith("z"))
except AssertionFailure as failure:
    print(failure)

try:
    expect(server_config).contains_entry_matching(lambda key, value: key == "z")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to contain a key matching the predicate, but the keys were ['host', 'port', 'tls'].
Expected server_config to contain an entry matching the predicate, but the entries were {'host': 'db-01', 'port': 5432, 'tls': True}.
```

`contains_entry_matching` takes a predicate of **two arguments** — `(key, value)`
— not one pair. `contains_value_matching` completes the set.

All three hand back what they found, and `.which` continues on it: the matching
key, the `(key, value)` pair, the stored value. So does `contains_value`.

## Length and emptiness

```python
from lovely_assertions import expect, AssertionFailure

server_config = {"host": "db-01", "port": 5432, "tls": True}
try:
    expect(server_config).has_length(5)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_config to have 5 entries, but had 3 entries with keys ['host', 'port', 'tls'].
```

It counts *entries* and shows you the keys — not "expected 5, was 3", which
would leave you to go and look. The rest of the family matches
[collections](collections.md#length-and-emptiness): `has_length_greater_than`,
`has_same_length_as`, `is_empty`, `is_not_empty`, `is_none_or_empty`, and so on.

## Gotchas

### Containment uses `==`, so `True` is `1`

```python
from lovely_assertions import expect

server_config = {"host": "db-01", "port": 5432, "tls": True}
expect(server_config).contains_value(1)
print("True == 1, so this passes")
```

```text
True == 1, so this passes
```

Membership is Python's own `x is y or x == y`, and `True == 1` is true. If the
distinction matters, assert the entry and the type:
`expect(server_config).contains_key("tls").whose_value.is_exactly_instance_of(bool)`.

### Comparing whole mappings

`is_equal_to` is inherited from [the universal catalogue](any-value.md) and gives
you a difference block naming the keys that moved. Reach for it when the whole
shape is under test; reach for `contains_entry` when one fact is.

When `==` is the wrong question — a `dict` against a dataclass, or a field you do
not care about — use [`is_equivalent_to`](structural-equivalence.md).

---

**See also:** [collections](collections.md) · [any value](any-value.md) ·
[structural equivalence](structural-equivalence.md) · [matchers](matchers.md)
