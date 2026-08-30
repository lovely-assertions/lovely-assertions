# Migrating

How what you write today maps onto what you would write here — and, just as
importantly, where you should not bother.

## Where a plain `assert` is still the right call

Start here, because adopting this library everywhere is the wrong move.

```python
from lovely_assertions import expect

result = 2 + 2

assert result == 4  # already says everything
expect(result).is_equal_to(4)  # says the same thing, longer
print("both fine; the first is fine too")
```

```text
both fine; the first is fine too
```

pytest rewrites `assert` and prints a decent diff for free. Use `expect()` where
it buys you something specific:

- the value is **composite**, and you want to know *which* part disagreed;
- the failure needs **explaining** — a near-miss key, an offending index, a
  count;
- you want the **narrowing**, so the value comes out typed;
- you want the **catalogue** — the assertion already exists and you would
  otherwise write it by hand.

Mixing the two in one file is normal and expected.

## From plain `assert`

| You write | Consider |
|---|---|
| `assert x == y` | `expect(x).is_equal_to(y)` — for a difference block |
| `assert x is None` | `expect(x).is_none()` |
| `assert x is not None` | `expect(x).is_not_none()` — and take `.subject` for the narrowed value |
| `assert isinstance(x, T)` | `expect(x).is_instance_of(T)` — same, plus narrowing |
| `assert x in c` | `expect(x).is_in(c)` |
| `assert item in collection` | `expect(collection).contains(item)` — names what was there |
| `assert len(c) == 3` | `expect(c).has_length(3)` — shows the contents |
| `assert not c` | `expect(c).is_empty()` — says more than falsiness |
| `assert c == sorted(c)` | `expect(c).is_sorted()` — names the offending pair |
| `assert s.startswith(p)` | `expect(s).starts_with(p)` |
| `assert s.isdigit()` | `expect(s).is_digit()` — names the offending character |
| `assert d["k"] == v` | `expect(d).contains_entry("k", v)` — tells missing from wrong |
| `assert log.count(x) == 3` | `expect(log).contains(x, occurrences=exactly(3))` |
| `assert x == a or x == b` | `expect(x).satisfies_any(lambda s: s.is_equal_to(a), lambda s: s.is_equal_to(b))` |
| `if a: assert b` | `expect(a).implies(b)` |

The pattern in that table: **each one buys a better failure, not a shorter
line.** Where the failure is already good, leave the `assert`.

## From `pytest`

| pytest | Here |
|---|---|
| `pytest.raises(E)` | `expect_raises(E)` |
| `pytest.raises(E, match=r"...")` | `expect_raises(E)` then `.with_message(r"...")` — both are a `re.search`. Use `.with_message_containing("...")` for a plain substring |
| `pytest.warns(W)` | `expect_warns(W)` |
| `pytest.approx(x)` | `expect(v).is_close_to(x)` — [the same four calling forms](numbers.md#floating-point-is_close_to) |
| `pytest.approx(x, rel=r)` | `expect(v).is_close_to(x, rel=r)` |
| — | `expect(fn).does_not_raise()` and `.does_not_warn()`, which pytest cannot express |

```python
from lovely_assertions import expect_raises


def parse_port(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse_port("nope")

caught.with_message_containing("invalid literal")
print("the pytest.raises shape, with more to say afterwards")
```

```text
the pytest.raises shape, with more to say afterwards
```

The differences worth knowing: a failure here can be [collected by a soft
scope](soft-assertions.md) rather than ending the test, the wrong-exception
message shows you what *was* raised, and warning assertions can
[count](occurrences.md).

## From `unittest`

`AssertionFailure` derives from `AssertionError`, so nothing about your runner
changes. Drop `expect()` into a `TestCase` method and it works.

| `unittest` | Here |
|---|---|
| `assertEqual(a, b)` | `expect(a).is_equal_to(b)` |
| `assertIs(a, b)` | `expect(a).is_same_as(b)` |
| `assertIsNone(a)` | `expect(a).is_none()` |
| `assertIn(a, b)` | `expect(a).is_in(b)` |
| `assertIsInstance(a, T)` | `expect(a).is_instance_of(T)` |
| `assertRaises(E)` | `expect_raises(E)` |
| `assertWarns(W)` | `expect_warns(W)` |
| `assertAlmostEqual(a, b)` | `expect(a).is_close_to(b)` |
| `assertCountEqual(a, b)` | [`expect(a).is_equivalent_to(b, options=equivalency().ignoring_order())`](structural-equivalence.md) |
| `subTest` for a batch of checks | [`soft_assertions()`](soft-assertions.md) |

Note the argument order flips: `assertEqual(actual, expected)` becomes
`expect(actual).is_equal_to(expected)`, so the value under test stays first.

`satisfies_any` takes branches that each receive the **subject**, so all of them
are about one value — it is not a translation of an arbitrary `a or b`.
`equivalency` is imported from `lovely_assertions` alongside `expect`.

## From `assertpy`

The API will feel familiar — this is the same fluent shape. Three differences:

**`extracting` takes a callable, not a string.**

```python
from lovely_assertions import expect

orders = [{"id": "ord-118"}, {"id": "ord-119"}]
expect(orders).extracting(lambda order: order["id"]).contains("ord-118")
print("callable form")
```

```text
callable form
```

`extracting("id")` cannot be typed: a checker cannot know the attribute exists,
let alone its type, so every assertion downstream would be checked against `Any`
— an empty autocomplete list and a type error that never fires. The callable also
survives a rename.

**The catalogue is per type.** `expect(3).starts_with(...)` is caught by your
type checker before you run anything, because a `NumericExpect` has no such
method. Without a checker it is an ordinary `AttributeError` on the line that
wrote it — either way it cannot pass silently, which is the point of the
library.

**Naming carries over unchanged.** `described_as` means what it means in
`assertpy`, and `expect(value, name=...)` says the same thing a step earlier.

## From `PyHamcrest`

The matcher idea survives, in a smaller and more typed form:

| PyHamcrest | Here |
|---|---|
| `assert_that(x, equal_to(y))` | `expect(x).is_equal_to(y)` |
| `assert_that(x, instance_of(T))` | `expect(x).is_instance_of(T)` |
| `has_entries(...)` | `expect(d).contains_entries({...})` |
| `contains_inanyorder(...)` | `expect(c).satisfies_in_any_order(...)` |
| `anything()` | [`anything()`](matchers.md), used *inside* an expectation |
| `all_of(a, b)` | chain the assertions, or `satisfies` |
| `any_of(a, b)` | `satisfies_any(...)` |

The structural difference: PyHamcrest matchers are the assertion; here
[matchers](matchers.md) are placeholders that go *inside* an expected value, and
the assertions are methods chosen by the subject's type.

## Adopting it gradually

1. **Start where failures hurt.** Find the tests whose failures you have to
   investigate rather than read. Those are the ones that pay for themselves.
2. **Leave the rest alone.** A file with three `expect()` calls and twenty
   `assert`s is a healthy file.
3. **Add [`register_formatter`](controlling-output.md) once**, in a `conftest`,
   for the domain types that appear in your failures as memory addresses. This is
   the highest-value single change in most codebases.
4. **Reach for [`soft_assertions()`](soft-assertions.md)** in the tests that
   check several independent facts about one value.
5. **Write [your own assertions](extending.md)** only once you notice the same
   three-line check in several files.

---

**See also:** [design goals](../concepts/design-goals.md) — what this claims and
what it does not · [your first assertions](../getting-started/first-assertions.md)
