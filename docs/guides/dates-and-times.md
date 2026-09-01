# Dates and times

`date`, `datetime`, `time` and `timedelta` each get a subject of their own,
with a vocabulary that reads as time rather than as numbers.

> Full signatures: [`DateExpect[T]`](../reference/assertions.md#dateexpectt),
> [`DateTimeExpect`](../reference/assertions.md#datetimeexpect),
> [`TimeExpect`](../reference/assertions.md#timeexpect) and
> [`TimeDeltaExpect`](../reference/assertions.md#timedeltaexpect).

| Value | Subject | About |
|---|---|---|
| `date` | `DateExpect[T]` | a calendar day |
| `datetime` | `DateTimeExpect` | an instant, and its timezone |
| `time` | `TimeExpect` | a wall clock |
| `timedelta` | `TimeDeltaExpect` | a duration |

`DateTimeExpect` extends `DateExpect`, so a datetime has the calendar assertions
as well as its own.

> **This library never imports `datetime`.** The subjects are typed against those
> types under `TYPE_CHECKING` and matched by name at runtime, so importing
> `lovely_assertions` does not import `datetime` — see
> [Performance](../concepts/performance.md#importing-costs-almost-nothing).

## Comparison

Temporal comparisons read as time, not as numbers: `is_before`, `is_after`,
`is_on_or_before`, `is_on_or_after`, plus `is_between`, `is_strictly_between` and
`is_not_between`.

```python
from datetime import datetime

from lovely_assertions import expect, AssertionFailure

recorded_at = datetime(2024, 3, 16, 14, 30)
expect(recorded_at).is_after(datetime(2024, 3, 16, 9, 0))

try:
    expect(recorded_at).is_before(datetime(2024, 3, 16, 14, 0))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected recorded_at to be before 2024-03-16T14:00:00, but was 2024-03-16T14:30:00.
```

There is no `is_greater_than` here. A datetime is not a number, and the
vocabulary matches the domain.

## Calendar fields

```python
from datetime import date

from lovely_assertions import expect, AssertionFailure

invoice_date = date(2024, 3, 16)
expect(invoice_date).has_year(2024).and_.has_month(3).and_.has_day(16)

try:
    expect(invoice_date).has_year(2025)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected invoice_date to have year 2025, but had 2024 (2024-03-16).
```

The whole date is repeated in parentheses, so you can see the value you got
without going to find it.

```python
from datetime import date

from lovely_assertions import expect, AssertionFailure

invoice_date = date(2024, 3, 18)
try:
    expect(invoice_date).is_weekend()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected invoice_date to fall on a weekend, but 2024-03-18 is a Monday.
```

It names the **day of the week** — which is the fact you wanted and would
otherwise have to work out from the date.

`is_weekday` is the complement.

`is_today`, `is_in_the_past` and `is_in_the_future` compare against the moment
the assertion runs, and their failures state what "now" was at the time, so a
message from a CI log is still readable weeks later. "Now" is sampled in the
subject's own shape and timezone, so an aware subject meets an aware now.
Comparing a naive value with an aware one raises `TypeError` instead — see
[Two mixes no type checker can refuse](#two-mixes-no-type-checker-can-refuse).

A `date` subject is compared **by day**, so today is neither past nor future. A
`datetime` subject is compared by instant, so a timestamp earlier today is
already in the past.

When the question is "the same day" rather than "today", `is_same_date_as` asks
it of two datetimes in one call, instead of three `has_*` calls.

```python
from datetime import datetime, timedelta, timezone

from lovely_assertions import expect, AssertionFailure

shipped_at = datetime(2024, 3, 16, 23, 30, tzinfo=timezone.utc)
try:
    expect(shipped_at).is_same_date_as(
        datetime(2024, 3, 17, 8, 30, tzinfo=timezone(timedelta(hours=9)))
    )
except AssertionFailure as failure:
    print(failure)
```

```text
Expected shipped_at to fall on the same date as 2024-03-17T08:30:00+09:00, but was 2024-03-16T23:30:00+00:00.
```

Those two are the **same instant** — 23:30 UTC is 08:30 the next morning in
Tokyo. Wall clock is compared against wall clock, neither side converted, so
one moment in two zones is two different dates.

## Tolerance

Two timestamps a millisecond apart are the commonest reason a perfectly correct
result fails an equality test.

```python
from datetime import datetime, timedelta

from lovely_assertions import expect, AssertionFailure

recorded_at = datetime(2024, 3, 16, 14, 30)
expect(recorded_at).is_close_to(datetime(2024, 3, 16, 14, 31), within=timedelta(minutes=5))

try:
    expect(recorded_at).is_close_to(datetime(2024, 3, 16, 15, 0), within=timedelta(minutes=5))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected recorded_at to be within 0:05:00 of 2024-03-16T15:00:00, but was 2024-03-16T14:30:00, 0:30:00 away.
```

`within=` is keyword-only, and the message gives you the **actual distance** — so
you can see at once whether your tolerance is wrong or your code is.
`is_not_close_to` is the complement.

### Direction matters: `is_within`

`is_close_to` ignores direction. When it matters, `is_within(...)` takes
`.before(...)` or `.after(...)`:

```python
from datetime import datetime, timedelta

from lovely_assertions import expect, AssertionFailure

recorded_at = datetime(2024, 3, 16, 14, 30)
try:
    expect(recorded_at).is_within(timedelta(minutes=5)).before(datetime(2024, 3, 16, 14, 0))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected recorded_at to be within 0:05:00 before 2024-03-16T14:00:00, but was 2024-03-16T14:30:00, 0:30:00 after it.
```

`is_within(...)` on its own asserts **nothing** — it is only half a sentence, and
the assertion is the `.before(...)` or `.after(...)` that finishes it. An
unfinished chain warns rather than fails: the half-built object emits a
`RuntimeWarning` when it is collected, naming the delta it was holding. pytest
prints that in its warnings summary and still counts the test as passed —
`filterwarnings = ["error"]` in your pytest configuration is what turns it red.
`-W error::RuntimeWarning` alone will not: the warning comes from a finaliser, so
pytest re-reports it under a warning class of its own.

## Time zones

```python
from datetime import datetime, timezone

from lovely_assertions import expect, AssertionFailure

recorded_at = datetime(2024, 3, 16, 14, 30)
try:
    expect(recorded_at).is_utc()
except AssertionFailure as failure:
    print(failure)

try:
    expect(recorded_at).has_timezone(timezone.utc)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected recorded_at to be UTC, but 2024-03-16T14:30:00 is naive.
Expected recorded_at to have timezone datetime.timezone.utc, but 2024-03-16T14:30:00 has no timezone at all.
```

"is naive" is the diagnosis, not just a refusal — and naive-versus-aware is the
bug behind most timezone test failures. When that *is* the question, ask it
directly:

```python
from datetime import datetime, timezone

from lovely_assertions import expect

expect(datetime(2024, 3, 16, 14, 30)).is_naive()
expect(datetime(2024, 3, 16, 14, 30, tzinfo=timezone.utc)).is_aware()
print("asked directly")
```

```text
asked directly
```

`is_utc` is decided by **offset**, so any `tzinfo` with a zero offset counts.
`has_timezone` is decided by the `tzinfo` itself. A `tzinfo` whose `utcoffset()`
returns `None` counts as naive.

Comparing a naive datetime with an aware one does not fail — it raises. See
[Two mixes no type checker can refuse](#two-mixes-no-type-checker-can-refuse).

## Durations

```python
from datetime import timedelta

from lovely_assertions import expect, AssertionFailure

elapsed = timedelta(minutes=90)
expect(elapsed).is_positive().and_.is_shorter_than(timedelta(hours=2))

try:
    expect(elapsed).is_longer_than(timedelta(hours=2))
except AssertionFailure as failure:
    print(failure)

try:
    expect(elapsed).has_total_seconds(3600)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected elapsed to be longer than 2:00:00, but was 1:30:00.
Expected elapsed to have total seconds 3600, but had 5400.0 (1:30:00).
```

`has_total_seconds` is exact float equality — note the `5400.0` in the message.
For a duration that came out of arithmetic rather than from a literal, reach for
`is_close_to(other, within=...)` instead.

`is_longer_than` and `is_shorter_than` are **signed** comparisons, not magnitudes:
a negative duration is shorter than a positive one. `expect(abs(span))` is how to
ask about magnitude. Also available: `is_at_least`, `is_at_most`, `is_between`,
`is_zero`, `is_not_zero`, `is_negative`, `is_close_to`.

## Wall clocks

`has_hour`, `has_minute`, `has_second`, `has_microsecond`, `is_naive` and
`is_aware` are the clock half, and a `datetime` has them too — that is where you
assert the hour of a timestamp. `TimeExpect` is the clock half without the
calendar, with the same comparisons (`is_before`, `is_after`, `is_on_or_before`,
`is_on_or_after`, `is_between`, `is_strictly_between`, `is_not_between`), and one
assertion of its own:

```python
from datetime import time

from lovely_assertions import expect, AssertionFailure

opens_at = time(14, 30)
try:
    expect(opens_at).is_midnight()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected opens_at to be midnight, but was 14:30:00.
```

`is_midnight` is on `TimeExpect` and **not** on `DateTimeExpect` — for a datetime,
the question is about the whole instant.

## Gotchas

### Two mixes no type checker can refuse

```python
from datetime import date, datetime

from lovely_assertions import expect

invoice_date = date(2024, 3, 16)
try:
    expect(invoice_date).is_before(datetime(2024, 3, 17))
except TypeError as error:
    print(error)
```

```text
can't compare a date with a datetime: 2024-03-16 is a date and 2024-03-17T00:00:00 is a datetime; datetime subclasses date, so no type checker can refuse the mix
```

`datetime` subclasses `date`, so a `datetime` is assignable everywhere a `date`
is and no bound can exclude it. CPython raises `TypeError` on the comparison; the
library catches it and rewrites it to say which side is which.

Only this direction is open. A `date` operand handed to a `datetime` subject *is*
a checker error — there the operand is typed `datetime`, and a `date` is not one.
It is the subclassing that leaves the other way round unguarded.

The second mix is naive against aware, and it is the commoner crash: whether a
datetime carries a timezone is not a type-level fact at all, so there is nothing
for any checker to look at.

```python
from datetime import datetime, timezone

from lovely_assertions import expect

started_at = datetime(2024, 3, 16, 14, 30)
try:
    expect(started_at).is_before(datetime(2024, 3, 16, 15, 0, tzinfo=timezone.utc))
except TypeError as error:
    print(error)
```

```text
can't compare a timezone-aware datetime with a naive one: 2024-03-16T14:30:00 is naive and 2024-03-16T15:00:00+00:00 is aware; give both a timezone, or neither
```

Both raise `TypeError` rather than failing the assertion, deliberately: this is a
bug in the test, not a fact about the value, and
`Expected started_at to be before ...` would send you looking in the wrong place.

`is_equal_to` is left alone in both cases. `==` across either mix is well
defined and answers `False`, so a mismatched pair is an ordinary failure rather
than a `TypeError`, and the message prints both reprs — which is what makes the
mix visible in it.

### `has_day(32)` raises; `has_day(31)` in February fails

A claim no value could satisfy is a bug in the test, so it raises `ValueError` at
the call rather than failing: a component outside its range (`has_day(32)`,
`has_month(13)`, `has_hour(24)`), a negative tolerance (`within=`, or the delta
handed to `is_within`), a range that admits nothing (`is_between(high, low)`,
`is_strictly_between(x, x)`). A claim that is possible but untrue — `has_day(31)`
on a February date — is a finding about the value, so it fails.

---

**See also:** [numbers](numbers.md) · [any value](any-value.md) ·
[structural equivalence](structural-equivalence.md) for `close_within` on
timestamps inside a larger graph.
