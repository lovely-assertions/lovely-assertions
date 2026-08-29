---
paths:
  - "tests/**/*.py"
  - "typing_tests/**/*.py"
---

# Testing conventions

**Three suites, three jobs.** `tests/` pins runtime behaviour. `typing_tests/`
pins what a checker sees — `positive/` must type-check clean, `negative/` must be
rejected, both verified by shelling out to the real pyright and mypy. `benchmarks/`
measures and asserts nothing. A change that touches the public surface usually
needs all three.

**Name the property, not the call.** `test_<unit>_<condition>_<expected>`: the
name alone should state what is guaranteed. One behaviour per test; Arrange /
Act / Assert as blocks separated by blank lines.

**Assert on the message, not just the failure.** `pytest.raises(AssertionFailure,
match=...)` — a test that only checks *that* it failed is passing on a message
this library exists to get right. Pin the sentence.

**A guard you have not tried to break is not a guard.** Before trusting a new
check, mutate the code it protects and confirm the test goes red. A test that
passes against the broken version is worse than no test: it reports coverage it
does not have.

**Shared doubles live in `conftest.py`.** One booby-trapped stand-in for the
failure machinery, one fixture that disables it, one autouse fixture that fails
any test leaking a soft scope. Never fork a private copy of a double into a test
module — divergent copies trap different things and each one silently narrows
what the suite checks.

**Performance claims are tests only when they hold on any machine.** No
allocation on a passing assertion, a module that must not be imported, a happy
path that must not reach the naming machinery: those are ordinary tests. Wall
clock, throughput and ratios belong in `benchmarks/`, printed for a human.

**Exemption tables are pinned by count.** When a table lists cases a guard skips,
assert its length too, so a new case cannot join the exemptions unnoticed.

**Determinism.** No wall clock, no network, no reliance on dict iteration order
or on set ordering. Interpreter-version-dependent expectations are gated on the
version explicitly, never left to fail on the next release.

**Coverage is a floor, not a target.** `uv run pytest --cov` enforces
`fail_under` from `[tool.coverage.report]`, and CI holds the same number over the
combined data of every platform — so what is measured is the union of what CI
actually ran, not one runner's view of a package whose filesystem assertions
differ by platform. Write a test because a behaviour needs pinning, never to move
the number, and never lower the floor to make a change pass. A `# pragma: no
cover` on a live branch is a test that was not written; the honest alternative,
when a defensive `return` is genuinely unreachable, is to leave it uncovered and
say why in a comment.

**Run it untraced too, and know why.** Several performance invariants read a
measurement that cannot be taken while `sys.settrace` is active and skip
themselves under coverage. A traced run is therefore not a superset of a plain
one — it is a different run with a few hundred tests missing. Coverage is opt-in
for exactly that reason and never goes in `addopts`.
