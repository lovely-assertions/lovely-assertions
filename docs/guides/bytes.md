# Bytes

`expect(payload)` on a byte string gives you a `BytesExpect` — a
[`SequenceExpect[int]`](sequences.md) with two more readings on it.

```python
from lovely_assertions import expect

payload = b"GET /orders HTTP/1.1"

expect(payload).contains(b"HTTP/1.1").and_.has_length(20)
print("both readings, one subject")
```

```text
both readings, one subject
```

> Full signatures: [`BytesExpect`](../reference/assertions.md#bytesexpect).

## It is still a sequence of integers

`b"abc"[0]` is `97`, so the elements really are integers and every sequence
assertion applies to them, unchanged:

```python
expect(b"abc").contains(97).and_.contains_in_order(97, 99).and_.is_sorted()
print("the integer reading, untouched")
```

```text
the integer reading, untouched
```

`bytearray` and `memoryview` are not `bytes` and keep the plain
`SequenceExpect[int]`.

## Membership asks either question

`bytes` answers `in` for a single byte **and** for a run of them — `b"bc" in
b"abc"` is true — and that second reading is what its own subject adds:

```python
from lovely_assertions import expect, AssertionFailure

payload = b"GET /orders HTTP/1.1"
try:
    expect(payload).contains(b"POST")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected payload to contain b'POST', but was b'GET /orders HTTP/1.1'.
```

The complement names where the run begins, since "it is in there somewhere" is
the half you already knew:

```python
try:
    expect(payload).does_not_contain(b"orders")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected payload not to contain b'orders', but it begins at byte 5 of b'GET /orders HTTP/1.1'.
```

`occurrences=` counts **non-overlapping** runs, the rule the
[string subject](strings.md) already applies:

```python
from lovely_assertions import exactly

expect(b"aXbXc").contains(b"X", occurrences=exactly(2))
expect(b"aaaa").contains(b"aa", occurrences=exactly(2))
print("two, not three")
```

```text
two, not three
```

## A byte reads in hexadecimal

`has_byte_at` is thin, and it earns its place on the message alone: a byte is
written in hex in every specification you check a test against, and `repr` shows
it as a decimal.

```python
header = b"\x1f\x8b\x08"
try:
    expect(header).has_byte_at(1, 0x1F)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected header to have 0x1f at byte 1, but had 0x8b: b'\x1f\x8b\x08'.
```

A `value` outside `0..255` raises `ValueError`: no byte could equal it, so it is
a mistake in the test rather than a finding about the subject.

## Reading it as text

`is_valid_utf8` asks the question you ask before decoding, and answers it with
the offset — which is the useful half of the `UnicodeDecodeError` it replaces:

```python
broken = b"a\xffb"
try:
    expect(broken).is_valid_utf8()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected broken to be valid UTF-8, but byte 1 (0xff) is not: b'a\xffb'.
```

`decoded_as` does the decode and hands the text on. The found value really is a
`str`, so the whole string catalogue follows it:

```python
expect(b"<!DOCTYPE html>").decoded_as("utf-8").which.starts_with("<!DOCTYPE")
print("bytes in, string assertions out")
```

```text
bytes in, string assertions out
```

`.and_` goes back to the bytes, `.which` descends into the text, `.subject` hands
the text over raw. An encoding Python does not know is a `LookupError` from the
standard library, raised where you wrote it.

## Gotchas

### Equality on two long payloads is still hard to read

A failed `is_equal_to` clips both sides at the same width and gives no
difference block, so a byte that differs deep in a payload has to be found by
eye. That is a gap in the difference engine rather than in this subject, and it
is not closed yet — for now, compare a slice or a `hex()` of the region you care
about.

### `contains` uses `find`, not `in`

An implementation detail with a visible cost behind it: `b"x" in payload`
allocates a couple of hundred bytes on **every** call through the buffer
protocol, where `payload.find(b"x")` allocates nothing and asks the same C
routine. Worth knowing if you are writing your own byte assertions.

---

**See also:** [sequences](sequences.md) · [strings](strings.md) ·
[typed dispatch](../concepts/typed-dispatch.md)
