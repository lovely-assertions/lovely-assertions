# lovely-assertions

Fluent, strictly-typed assertions for Python tests.

[![CI](https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml/badge.svg)](https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/lovely-assertions/lovely-assertions/badge)](https://scorecard.dev/viewer/?uri=github.com/lovely-assertions/lovely-assertions)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue)](https://www.python.org/)
[![Checked with pyright and mypy](https://img.shields.io/badge/types-pyright%20%2B%20mypy%20strict-2a6db2)](#design-commitments)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Status: pre-release.** The catalogue, exception and warning assertions, rich
> differences, matchers and the extension API are in place, tested and
> documented, and the pipeline that will publish them is wired. Nothing has been
> released to PyPI yet — see [CHANGELOG.md](CHANGELOG.md).

## Why another assertion library

The competition is not `assertpy` or `PyHamcrest` — it is pytest's own `assert`
rewriting, which already introspects `assert a == b` and prints a decent diff.
So the value has to be somewhere else, and it is in three places. Break any one
of them and the package has no reason to exist.

**Typed discoverability.** `expect(x).` offers only the assertions that are valid
for the type of `x`. A raw `assert` never does that, and neither does any
assertion library that dispatches dynamically.

```python
expect("hello").starts_with("he")  # str assertions
expect([1, 2, 3]).contains_no_duplicates()
expect({"a": 1}).contains_key("a")
expect(3).is_positive()  # `starts_with` is not offered here
```

**Real narrowing.** The subject a chain returns is re-typed, statically, and both
pyright and mypy agree:

```python
name: str = expect(raw).is_not_none().subject  # raw: str | None
count: int = expect(payload).is_instance_of(int).subject  # payload: object
```

Honest limitation, stated up front: the *original variable* stays `str | None` as
far as the checker is concerned. Python's `TypeGuard`/`TypeIs` can only narrow a
function's first positional argument, and `expect()` captures the subject inside
a wrapper, so the caller's variable is out of reach. Narrowing therefore flows
through the returned subject — rebind it, and you have a statically guaranteed
type. No Python assertion library does better; this one says so instead of
pretending otherwise.

**Failure messages that locate the problem.** The competition prints a diff; this
prints an explanation.

```
Expected order_totals to be sorted, but 1 at index 1 came after 3: [3, 1, 2].
Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host'].
Expected config to contain entry 'port': 9090, but that key held 8080.
```

That last pair is the point: *the key holds a different value* and *the key is
missing* are different bugs, and the message says which instead of leaving you to
find out. Equality on a composite value adds a difference block — a unified diff
for multi-line text, the first offending index for a sequence, the keys that moved
for a mapping — and it stays bounded, so comparing two five-thousand-element lists
is four hundred characters, not sixty thousand.

## What else you get

**Exceptions, in the form you already reach for.**

```python
with expect_raises(ValueError) as caught:
    parse("nope")
caught.with_message_containing("invalid literal")
```

When the wrong exception is raised, the failure is chained onto the real one, so
its traceback survives next to the message rather than being replaced by it.

**Your own assertions, with the same machinery.** Subclass `Expect[T]`, mark your
methods with `@custom_assertion`, and they get subject naming, soft scopes,
`because` and the whole inherited catalogue. See
[the extension guide](docs/guides/extending.md).

## Documentation

**[Full documentation →](docs/README.md)**

| | |
|---|---|
| New here | [Installation](docs/getting-started/installation.md) · [Your first assertions](docs/getting-started/first-assertions.md) · [Reading a failure](docs/getting-started/reading-failures.md) |
| How do I assert…? | [The guides](docs/README.md#guides) — by type, and by task |
| Every assertion | [The reference](docs/reference/assertions.md), generated from the source |
| Why it works this way | [Concepts](docs/README.md#concepts) — dispatch, messages, performance, typing |
| Coming from `assert` or `assertpy` | [Migrating](docs/guides/migrating.md) |

Every Python example in those pages is executed by the test suite, and every
failure message they quote is compared against what the library actually
produces.

## Design commitments

- **Zero runtime dependencies**, permanently. Python 3.13+.
- **A passing assertion costs a comparison and a `return self`** — no frame
  inspection, no message building, no context lookups. Failure messages are
  formatted only in the failure branch, never as an argument to a helper.
- **`py.typed`, 100% annotated, pyright strict and mypy strict both green in CI.**
  Where mypy and pyright genuinely disagree, the divergence is documented and
  frozen — the API never gets shaved down to accommodate a checker.
- **The typing surface is tested like any other surface**, with a negative corpus
  that both checkers are required to reject. Every line that must be rejected
  carries an `expect-error` marker, and the harness is symmetric: a marked line
  no checker reports fails the suite, and a reported line nobody marked fails it
  too. A harness that cannot detect a wrong `assert_type` proves nothing about
  the ones it accepts.
- **Messages are tested as output, not as behaviour.** A message is not wrong for
  being sixty thousand characters long — no assertion fails because of it — so
  size and shape are pinned explicitly.

## Development

```bash
uv sync
```

Then, all of which must be green:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run mypy && uv run pytest
```

[CONTRIBUTING.md](CONTRIBUTING.md) has the rest: what a change usually touches,
what CI runs and what each gate proves, and how a release is cut. Taking part
means agreeing to the [code of conduct](CODE_OF_CONDUCT.md).

## Security

Report a vulnerability privately through the
[Security tab](https://github.com/lovely-assertions/lovely-assertions/security),
not as a public issue. [SECURITY.md](SECURITY.md) also sets out what this library
does on the failure path — it renders your values, and it reads the source line
you wrote the assertion on — so that the boundary is documented rather than
discovered.

Releases are published through PyPI
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), with no API
token anywhere in this repository, and every artifact carries a signed build
provenance attestation.

## License

MIT — see [LICENSE](LICENSE).
