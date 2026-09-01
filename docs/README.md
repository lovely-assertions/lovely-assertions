# lovely-assertions documentation

Fluent, strictly-typed assertions for Python tests: your editor offers only
the assertions that fit the value, and a failure explains itself in a
sentence.

```python
from lovely_assertions import expect

hostname = "db-01.internal"
open_ports = [5432, 6379]
labels = {"tier": "primary", "region": "eu-west-1"}

expect(hostname).ends_with(".internal")
expect(open_ports).contains(5432).and_.has_length(2)
expect(labels).contains_entry("tier", "primary", because="a replica cannot take writes")
```

Three things make this different from writing `assert` by hand, and everything
here follows from them:

- **Your editor only offers what applies.** `expect(name).` on a `str` proposes
  `starts_with`; it does not propose `is_positive`. The subject you get is chosen
  from the value's type, statically and at runtime, by [one table](concepts/typed-dispatch.md).
- **Narrowing is real.** `expect(raw).is_not_none().subject` is a `str` to both
  pyright and mypy — not an `object`, not a cast.
- **A failure leads with a sentence.** It names the value, what was expected, and
  what was there instead; a diff follows only where one says something the
  sentence cannot. [Why that matters](concepts/failure-messages.md).

---

## Start here

**New to the library?** Read these four, in order. About twenty minutes.

| # | Page | What you get |
|---|------|--------------|
| 1 | [Installation](getting-started/installation.md) | Installed, imported, working |
| 2 | [Your first assertions](getting-started/first-assertions.md) | The shape of every assertion you will write |
| 3 | [Reading a failure](getting-started/reading-failures.md) | How to get a message that ends the investigation |
| 4 | [Chaining and narrowing](getting-started/chaining-and-narrowing.md) | `and_`, `.subject`, and how types flow through a chain |

**Coming from plain `assert`, `assertpy`, or `unittest`?**
[Migrating](guides/migrating.md) maps what you write today onto what you would
write here, and is honest about where a plain `assert` is still the better call.

---

## Guides

Task-oriented. Each page answers "how do I assert *this*?", and each of the
subject pages below links into the reference for the exhaustive list.

### By what you are asserting on

| Page | Covers |
|------|--------|
| [Any value](guides/any-value.md) | Equality, identity, `None`, truthiness, types, predicates — available on every subject |
| [Strings](guides/strings.md) | Containment, prefixes, regex, wildcards, character classes |
| [Numbers and booleans](guides/numbers.md) | Comparisons, ranges, sign, tolerance, `nan`/`inf`, `implies` |
| [Collections](guides/collections.md) | Membership, length, set relations, duplicates, per-item checks |
| [Sequences](guides/sequences.md) | Order, position, sorting, element-by-element comparison |
| [Mappings](guides/mappings.md) | Keys, values, entries — and why the difference shows up in the message |
| [Dates and times](guides/dates-and-times.md) | Comparison, tolerance, time zones, durations |
| [Paths](guides/paths.md) | Pure path shape, and assertions that touch the filesystem |
| [Exceptions](guides/exceptions.md) | `expect_raises`, message and cause assertions, "must not raise" |
| [Warnings](guides/warnings.md) | `expect_warns`, counting, "must not warn" |
| [Mocks](guides/mocks.md) | Calls, arguments, counts — and the misspellings `mock` lets through |
| [Types and enums](guides/types-and-enums.md) | Subclassing, protocols, members, flags |

### By what you are doing

| Page | Covers |
|------|--------|
| [Soft assertions](guides/soft-assertions.md) | Collect every failure in a block instead of stopping at the first |
| [Matchers](guides/matchers.md) | Assert the shape of a value when you cannot name all of it |
| [Structural equivalence](guides/structural-equivalence.md) | Compare two object graphs member by member |
| [Counting occurrences](guides/occurrences.md) | `exactly(3)`, `at_least(1)`, and friends |
| [Controlling output](guides/controlling-output.md) | Print more of a value, or teach a message how your types read |
| [Extending](guides/extending.md) | Your own assertions and your own subjects, with the same machinery |

---

## Reference

[The assertion reference](reference/assertions.md) — every assertion on every
subject, generated from the source and verified against it on every run.
[How the reference is built](reference/README.md) says what in it is derived,
what is checked, and where the one gap is.

---

## Concepts

Why it is built the way it is. Useful when you are deciding whether to adopt it,
extending it, or debugging something surprising.

| Page | Question it answers |
|------|---------------------|
| [Design goals](concepts/design-goals.md) | What this claims over pytest's `assert` rewriting, and what it does not |
| [Typed dispatch](concepts/typed-dispatch.md) | How `expect()` picks a subject, and why the order is what it is |
| [Failure messages](concepts/failure-messages.md) | The grammar every message follows, and the rules behind it |
| [Performance](concepts/performance.md) | What a passing assertion costs, and what a failing one is allowed to |
| [Type-checker divergences](concepts/typing-divergences.md) | Where pyright and mypy disagree, and what was decided |

---

## Should you depend on this?

The questions that decide it, answered in one place.

| | |
|---|---|
| **Maturity** | First release. The catalogue, exception and warning assertions, the difference engine and the extension API are complete and tested. |
| **Stability** | The public surface is `__all__`, and it is what the [reference](reference/assertions.md) documents. Until a 1.0, treat it as settled but not promised — changes are recorded in [CHANGELOG.md](../CHANGELOG.md). |
| **Dependencies** | None, permanently. Python 3.13+. |
| **Cost to your suite** | A passing assertion is a comparison and a return: nothing retained, no message built. Importing the package imports almost nothing. [Performance](concepts/performance.md) says exactly what is measured and what is not. |
| **Lock-in** | None. `expect()` is a function you import, its failures are ordinary `AssertionError`s, and it mixes freely with `assert` in the same file. There is no plugin, no fixture and no base class. |
| **When it does not fit** | Use a plain `assert`. [Design goals](concepts/design-goals.md) is explicit about what this does *not* claim, and [Migrating](guides/migrating.md) opens by saying where a bare `assert` is still the better call. |
| **Escape hatches** | `matches(predicate)` for a condition with no assertion; `satisfies` for nested ones; [your own assertions](guides/extending.md) with the same machinery; `.subject` to leave the library with a typed value. |
| **Type checkers** | pyright and mypy, both strict, both green in CI on Python 3.13 and 3.14. Where they disagree, the disagreement is [written down](concepts/typing-divergences.md) rather than designed around. |
| **Are these docs true?** | Every Python example on every page is run by the test suite — the few that cannot are marked on the page, with the reason — and every failure message they quote is compared byte for byte against what really came back. The same examples are type-checked, by pyright alone. A page that drifts from the library fails the build. |
