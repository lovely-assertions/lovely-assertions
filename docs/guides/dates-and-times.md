# Dates and times

Four subjects, for four different types:

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
`is_on_or_before`, `is_on_or_after`, plus `is_between` and `is_strictly_between`.

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
subject's own shape and timezone, so an aware subject meets an aware now — the
alternative would raise the very `TypeError` this module exists to explain.

A `date` subject is compared **by day**, so today is neither past nor future. A
`datetime` subject is compared by instant, so a timestamp earlier today is
already in the past.

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
the assertion is the `.before(...)` or `.after(...)` that finishes it.

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

`is_longer_than` and `is_shorter_than` are **signed** comparisons, not magnitudes:
a negative duration is shorter than a positive one. Also available:
`is_at_least`, `is_at_most`, `is_between`, `is_zero`, `is_not_zero`,
`is_negative`, `is_close_to`.

## Wall clocks

`TimeExpect` has the calendar-free half: `has_hour`, `has_minute`, `has_second`,
`has_microsecond`, the comparisons (`is_before`, `is_after`, `is_on_or_before`,
`is_on_or_after`, `is_between`, `is_strictly_between`), `is_naive`, `is_aware`,
and one of its own:

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

### The one mix no type checker can refuse

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

Deliberately a `TypeError` and not an assertion failure: this is a bug in the
test, not a fact about the value, and reporting it as
`Expected invoice_date to be before ...` would send you looking in the wrong
place. The same applies to comparing a naive datetime with an aware one.

### `has_day(32)` raises; `has_day(31)` in February fails

A day number outside 1–31 could never be any date's day, so it is a bug in the
test and raises at the call. A valid day that this date does not have is a
finding about the value, so it fails.

---

**See also:** [numbers](numbers.md) · [any value](any-value.md) ·
[structural equivalence](structural-equivalence.md) for `close_within` on
timestamps inside a larger graph.
