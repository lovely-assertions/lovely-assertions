# lovely-assertions

Fluent, strictly-typed assertions for Python tests.

[![CI](https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml/badge.svg)](https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/lovely-assertions/lovely-assertions/badge)](https://scorecard.dev/viewer/?uri=github.com/lovely-assertions/lovely-assertions)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue)](https://www.python.org/)
[![Checked with pyright and mypy](https://img.shields.io/badge/types-pyright%20%2B%20mypy%20strict-2a6db2)](#design-commitments)
[![License: MPL 2.0](https://img.shields.io/badge/license-MPL--2.0-green)](LICENSE)

> **Status: 0.1.0, the first release.** The catalogue, exception and warning
> assertions, rich differences, matchers and the extension API are in place,
> tested and documented. Before 1.0 the API may still move; when it does, the
> reason is in [CHANGELOG.md](CHANGELOG.md), which is generated from the commit
> log rather than written by hand.

## Install

```bash
pip install lovely-assertions
```

Or, with uv:

```bash
uv add --dev lovely-assertions
```

It has no runtime dependencies and it needs Python 3.13 or newer.

```python
from lovely_assertions import expect

expect("hello").starts_with("he")
```

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
raw: str | None = "ada"
payload: object = 7

name: str = expect(raw).is_not_none().subject
count: int = expect(payload).is_instance_of(int).subject
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

```python
from lovely_assertions import soft_assertions

with soft_assertions():
    expect([3, 1, 2], name="order_totals").is_sorted()
    expect({"host": "x"}, name="server_config").contains_key("hostname")
    expect({"port": 8080}, name="config").contains_entry("port", 9090)
```

```text
3 assertions failed:
  (1) Expected order_totals to be sorted, but 1 at index 1 came after 3: [3, 1, 2].
  (2) Expected server_config to contain key 'hostname' (did you mean 'host'?), but the keys were ['host'].
  (3) Expected config to contain entry 'port': 9090, but that key held 8080.
```

(One scope, three failures, one report — that is
[soft assertions](docs/guides/soft-assertions.md), and it is why you see all
three instead of only the first.)

That last pair is the point: *the key holds a different value* and *the key is
missing* are different bugs, and the message says which instead of leaving you to
find out. Equality on a composite value adds a difference block — a unified diff
for multi-line text, the first offending index for a sequence, the keys that moved
for a mapping — and it stays bounded, so comparing two five-thousand-element lists
is four hundred characters, not sixty thousand.

## What else you get

**Exceptions, in the form you already reach for.**

```python
from lovely_assertions import expect_raises


def parse(text: str) -> int:
    return int(text)


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

[Mozilla Public License 2.0](LICENSE) — file-level copyleft. Use it in anything,
commercial included, and nothing about your own code is affected. Modify *these*
files and those files stay under this licence, which is the whole of the
obligation: it reaches the files it came in, and no further.

Releases up to and including `0.1.0` were published under the MIT licence and
remain so permanently for anyone holding them. The change applies from `0.2.0`.
