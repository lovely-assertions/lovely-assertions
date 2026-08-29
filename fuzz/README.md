# Fuzzing

Three targets, driven by [Atheris](https://github.com/google/atheris), each
pointed at a promise this library makes in prose and could otherwise only be
spot-checked by hand:

| target | the promise it attacks |
|---|---|
| `fuzz_equality.py` | a failing comparison raises `AssertionFailure`, never anything else, and its message stays bounded |
| `fuzz_strings.py` | the string catalogue survives arbitrary text — every code point, every length |
| `fuzz_hostile.py` | a value whose `__repr__`, `__eq__` or `__hash__` misbehaves cannot turn a failure into an error |

The third is the one worth having. The library runs somebody else's code on the
failure path — a `__repr__`, an `__eq__`, a registered formatter, a caller's
predicate — behind a documented promise that doing so never raises. That promise
is checked by hand in a handful of tests; here it is checked by a machine that
does not share the author's imagination.

## The shape, and why

Each target is a thin Atheris driver around a plain function in `properties.py`.
Nothing that decides anything lives in the driver. Two reasons:

- **Atheris publishes manylinux x86_64 wheels and nothing else.** A maintainer on
  macOS or Windows cannot run it at all. With the properties separated,
  `tests/test_fuzzing.py` runs the same functions over a seeded corpus on every
  platform, on every ordinary `uv run pytest` — so the claims are exercised
  everywhere and merely *driven harder* on Linux.
- A property you can call directly is a property you can debug. A crash found by
  the fuzzer reduces to one call with one argument.

## Running them

```bash
uv sync --group fuzz                     # Linux x86_64 only
uv run python fuzz/fuzz_hostile.py -atheris_runs=200000
```

CI runs all three weekly in `.github/workflows/scheduled.yml`, time-boxed. They
are deliberately not on the pull-request path: a fuzzer that finds nothing is a
slow way to learn nothing, and one that finds something should interrupt a
maintainer rather than a contributor.

A crash writes its input to `crash-*` in the working directory. Reduce it to a
call against `properties.py`, add it to `tests/` as an ordinary pinned test, then
fix it — the suite is where a found bug stays found.
