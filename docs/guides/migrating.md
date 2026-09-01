# Migrating

Row-by-row translations from plain `assert`, pytest, unittest, assertpy and
PyHamcrest — and where a bare `assert` is still the better call.

## Where a plain `assert` is still the right call

Start here, because adopting this library everywhere is the wrong move.

```python
from lovely_assertions import expect

result = 2 + 2

assert result == 4  # already says everything
expect(result).is_equal_to(4)  # says the same thing, longer
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
| `assert x == a or x == b` | `expect(x).is_one_of(a, b)` |
| `if flag: assert b` (`flag` a `bool`) | [`expect(flag).implies(b)`](numbers.md#implies) — `b` is evaluated before the call, so it has to be safe to compute when `flag` is false |

The pattern in that table: **each one buys a better failure, not a shorter
line.** Where the failure is already good, leave the `assert`.

`implies` is on the boolean subject alone. An `if` guarding on an object, a
list or an int has no row here and stays an `if`.

## From `pytest`

| pytest | Here |
|---|---|
| `pytest.raises(E)` | `expect_raises(E)` |
| `pytest.raises(E, match=r"...")` | `expect_raises(E)` then `.with_message(r"...")` — both are a `re.search`. Use `.with_message_containing("...")` for a plain substring |
| `pytest.warns(W)` | `expect_warns(W)` |
| `pytest.approx(x)` | `expect(v).is_close_to(x)` — [the same four calling forms](numbers.md#floating-point-is_close_to) |
| `pytest.approx(x, rel=r)` | `expect(v).is_close_to(x, rel=r)` |
| `pytest.approx(x, abs=a)` | `expect(v).is_close_to(x, tol=a)` — `abs` is spelled `tol` |
| `values == pytest.approx([...])` | `expect(values).is_equivalent_to([close_to(a), close_to(b)])` — a collection has no `is_close_to`, so its items take the [`close_to`](matchers.md) matcher instead |
| — | `expect(fn).does_not_warn()`, which `pytest.warns` cannot express, and `expect(fn).does_not_raise(E)` — calling the function already fails the test on any exception, but only this bans *one* type, lets the others travel on, and names the failure |

```python
from lovely_assertions import expect_raises


def parse_port(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse_port("nope")

caught.with_message_containing("invalid literal")
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

unittest calls its two arguments `first` and `second` and never says which is
which. `expect()` does: the subject is the value under test. So `assertEqual(a,
b)` maps straight across, and a suite written in the JUnit habit —
`assertEqual(expected, actual)` — has to swap.

`equivalency` is imported from `lovely_assertions` alongside `expect`.

## From `assertpy`

The same fluent shape, under some different names.

| `assertpy` | Here |
|---|---|
| `assert_that(x)` | `expect(x)` |
| `is_length(n)` | `has_length(n)` |
| `is_type_of(T)` | `is_exactly_instance_of(T)` |
| `is_equal_to_ignoring_case(s)` | `is_equal_ignoring_case(s)` |
| `assert_that(fn).raises(E).when_called_with(a)` | `expect(lambda: fn(a)).raises(E)`, or [`expect_raises(E)`](exceptions.md) around the call |

Three differences go deeper than the spelling:

**`extracting` takes a callable, not a string.**

```python
from lovely_assertions import expect

orders = [{"id": "ord-118"}, {"id": "ord-119"}]
expect(orders).extracting(lambda order: order["id"]).contains("ord-118")
```

`extracting("id")` cannot be typed;
[collections](collections.md#asserting-on-a-field-of-every-item) has the
reasoning and the rest of the assertion.

**The catalogue is per type.** `expect(3).starts_with(...)` is caught by your
type checker before you run anything, because a `NumericExpect` has no such
method. Without a checker it is an ordinary `AttributeError` on the line that
wrote it — either way it cannot pass silently, which is the point of the
library.

**`described_as` takes a name, not a description.** assertpy brackets your text
in front of an otherwise untouched message — `[checking the totals] Expected <1>
to be equal to <2>, but was not.` Here the argument replaces the subject inside
the sentence, so `described_as("checking the totals")` gives you *Expected
checking the totals to equal 2, but was 1.* Pass a noun phrase — `"rows[3]"`,
`"the refund total"`. `expect(value, name=...)` says the same thing a step
earlier.

## From `PyHamcrest`

The matcher idea survives, in a smaller and more typed form:

| PyHamcrest | Here |
|---|---|
| `assert_that(x, equal_to(y))` | `expect(x).is_equal_to(y)` |
| `assert_that(x, instance_of(T))` | `expect(x).is_instance_of(T)` |
| `has_entries(...)` | `expect(d).contains_entries({...})` |
| `contains_inanyorder(1, 2)` (values) | [`expect(c).is_equivalent_to([1, 2], options=equivalency().ignoring_order())`](structural-equivalence.md) — one-to-one, duplicates counted, as PyHamcrest pairs them |
| `contains_inanyorder(m1, m2)` (matchers) | `expect(c).satisfies_in_any_order(p1, p2)` — one predicate per item |
| `anything()` | [`anything()`](matchers.md), used *inside* an expectation |
| `all_of(a, b)` | chain the assertions, or `satisfies` |
| `any_of(a, b)` | `satisfies_any(...)` |

`satisfies_any` takes branches that each receive the **subject**, so all of them
are about one value — it is not a translation of an arbitrary `a or b`.

The structural difference: PyHamcrest matchers are the assertion; here
[matchers](matchers.md) are placeholders that go *inside* an expected value, and
the assertions are methods chosen by the subject's type.

## Adopting it gradually

1. **Start where failures hurt.** Find the tests whose failures you have to
   investigate rather than read. Those are the ones that pay for themselves.
2. **Leave the rest alone.** A file with three `expect()` calls and twenty
   `assert`s is a healthy file.
3. **Add [`register_formatter`](controlling-output.md) once**, in a `conftest`,
   for the domain types that appear in your failures as memory addresses.
4. **Reach for [`soft_assertions()`](soft-assertions.md)** in the tests that
   check several independent facts about one value.
5. **Write [your own assertions](extending.md)** only once you notice the same
   three-line check in several files.

---

**See also:** [design goals](../concepts/design-goals.md) — what this claims and
what it does not · [your first assertions](../getting-started/first-assertions.md)
