---
paths:
  - "tests/**/*.py"
  - "typing_tests/**/*.py"
  - "benchmarks/**/*.py"
  - "fuzz/**/*.py"
---

# Testing conventions

**Four corpora, four jobs.** `tests/` pins runtime behaviour, and also carries the
guards over everything a green build would otherwise never notice: the shipped
source's prose, the workflows, the packaging, the docstring examples and the
executable docs. `typing_tests/` pins what a checker sees, in two halves enforced
by different commands — `negative/` must be rejected on exactly the lines carrying
an `# expect-error` marker, which `tests/test_typing_surface.py` verifies by
shelling out to the real pyright and mypy, while `positive/` must type-check clean
under the top-level `uv run pyright` and `uv run mypy`, which list it in their own
`include` and `files`. pytest never checks the positive half; it asserts only that
the directory is not empty. `benchmarks/` measures and asserts nothing, but it is
also where the invariant tests import their measurement primitives from —
`pythonpath = ["."]` exists for that, and its comment states the direction the
dependency runs in: nothing in `benchmarks/` may import from `tests/`, which no
guard enforces. `fuzz/properties.py` holds the properties, and because the fuzzer
that drives them reaches one platform, `tests/test_fuzzing.py` runs the same
properties over a seeded corpus everywhere else. A new property goes in three
places — `properties.py`, a driver, and that file's `PROPERTIES` — and only the
driver is checked.

**Name the property, not the call.** The name alone should state what is
guaranteed, at whatever length that takes; these are sentences, not slots in a
template. One behaviour per test. Where the name cannot carry the reason, the
docstring says what would go wrong without the test rather than restating what the
body does.

**Assert on the message, not just the failure.** `pytest.raises(AssertionFailure)
as caught`, then `assert str(caught.value) == "<the whole sentence>"`. A test that
only checks *that* it failed is passing on a message this library exists to get
right — and `match=` is `re.search`, so it pins a fragment and lets the rest of
the sentence rot. Reach for it only where the fragment really is the whole claim.

**A guard you have not tried to break is not a guard**, so the attempt is
committed as a test rather than performed once by hand. A scanner is handed a
violation it must report; a measurement is shown the distinct bugs it must tell
apart; an exemption is removed and the thing it covered must come back. Every file
in the suite passes every scan, so without this a scanner that returned nothing at
all would look exactly like a working one.

**Shared machinery sits beside the tests, never inside one of them.**
`conftest.py` holds the doubles and the fixtures: a booby-trapped stand-in for the
failure machinery and the fixture that installs it wherever a name is bound, an
autouse fixture that fails any test leaking a soft scope, the session monitor, and
the `measured` skip marker. `tests/_package.py` holds the walk of the package and
`tests/_happy_calls.py` the catalogue tables. Never fork a private copy of a
double into a test module: divergent copies trap different things and each one
silently narrows what the suite checks — a rule that holds by discipline, since
nothing scans for it. The spelling *is* enforced, by pyright rather than by a
test: a name imported across a test-module boundary carries no leading
underscore, because `reportPrivateUsage` fires on one and silencing it to keep a
private spelling is not something this repo writes. Everything a helper module
does not publish stays private.

**One walk of the package, in `tests/_package.py`.** A guard that states a rule
about every module in `src/` gets its file list from `sources()`, which recurses
into subpackages, and never writes its own `glob` or `rglob`.
`tests/test_guard_enumeration.py` scans each test module for a walk of its own and
fails it; an exemption goes in `NOT_THE_PACKAGE` and has to name a walk that still
exists. The failure this prevents is the quiet one: a non-recursive walk keeps the
rule's wording and applies it to fewer files than it claims, with the build green.

**Subjects are assembled from mixins, so resolve the owner.** An assertion is
declared on a seam — a mixin named `<Something>Assertions` — and not on the
subject that carries it, so `vars(SubjectClass)` holds none of them. Anything
enumerating assertions maps the declaring class back through `owning_subject()`,
by class object rather than by name, since two packages name a seam alike. Skip
that and every core assertion reads as belonging to nothing: a guard reporting
coverage it does not have.

**The catalogue is covered in both directions.** `HAPPY_CALLS` holds exactly one
passing call per public assertion, read by two guards that see different bugs —
one traps the failure machinery, the other measures allocation — and it is written
once precisely so the second cannot become a sample of the first. The failing
direction needs no table: a session monitor records every assertion seen failing,
and `pytest_sessionfinish` fails an otherwise green run in which one never was,
since an assertion with a passing exercise and no failing one could be neutered to
`return self` with the suite still green. Adding an assertion means a row in
`HAPPY_CALLS` and a test that fails it, or an argued entry in `NO_HAPPY_PATH` or
`CANNOT_FAIL`.

**Performance claims are tests only when they hold on any machine.** No allocation
on a passing assertion, a module that must not be imported, a bounded import cost,
a happy path that must not reach the naming machinery: those are ordinary tests.
Per-call timings, and their ratios against a bare `assert`, belong in
`benchmarks/`, printed for a human. A wall-clock bound is a test in one shape
only — loose by orders of magnitude, so that it separates a hang from an answer
instead of measuring speed.

**Every exemption is re-verified as still load-bearing.** A table of cases a guard
skips is the one place that guard can be made green by giving up, so it says why —
per entry wherever the reasons differ — and a test either removes an entry and
requires the violation back or checks that what it names still exists. A count is
not that check: an entry left behind after its call site went away leaves a slot a
new violation drops into without the total ever moving. Some tables carry a count
on top of it — a shrink-only ceiling, or an exact pin — so that an exemption
cannot join unremarked, but that is a supplement to the staleness check and never
a substitute for it.

**Determinism.** No network, no reliance on dict iteration order or on set
ordering. The clock is read only where the assertion under test reads it —
`is_today` cannot be exercised otherwise — and the expectation is then derived
from that same read rather than written down. Whatever depends on the interpreter
version or on the platform is gated explicitly, and gated on the behaviour instead
of on a version number wherever the behaviour can be asked for directly, so what
is named is the property rather than a number to revisit on the next release.

**Coverage is a floor, not a target.** `uv run pytest --cov` enforces `fail_under`
from `[tool.coverage.report]`, and CI holds the same number over the combined data
of every platform — so what is measured is the union of what CI actually ran, not
one runner's view of a package whose filesystem assertions differ by platform.
Write a test because a behaviour needs pinning, never to move the number, and
never lower the floor to make a change pass. A `# pragma: no cover` on a live
branch is a test that was not written; on a defensive `return` that genuinely
cannot be reached it is the right tool, and it carries its reason on the same line
— `# pragma: no cover - filtered out on the way in`. Nothing checks that the
reason is there: the guard over silenced suppressions reads `# noqa:` only.

**Run it untraced too, and know why.** A tracer allocates on the path it traces,
so a peak-allocation reading taken under coverage is the instrument reading
itself. Every such claim is marked `@measured` and skips itself — not only in the
invariants file, and one per assertion the allocation sweep reaches. A traced run
is therefore not a superset of a plain one but a different run with every
peak-allocation claim missing, which is why coverage is opt-in and never goes in
`addopts`. The marker asks `watching_the_interpreter()` what is instrumenting
execution rather than reading `sys.gettrace()` itself, because coverage uses
`sys.monitoring` where the interpreter offers it — though on the reference
interpreter, under this project's configuration, it is `sys.settrace` that trips.
