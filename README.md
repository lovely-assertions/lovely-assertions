<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/lovely-assertions/lovely-assertions/main/docs/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/lovely-assertions/lovely-assertions/main/docs/assets/logo.svg" alt="lovely-assertions" width="360">
  </picture>
</p>

<p align="center"><em>Your tests will fail. They may as well be lovely about it.</em></p>

<p align="center">
  <a href="https://pypi.org/project/lovely-assertions/"><img alt="PyPI" src="https://img.shields.io/pypi/v/lovely-assertions"></a>
  <a href="https://www.python.org/"><img alt="Python 3.13 and 3.14" src="https://img.shields.io/badge/python-3.13%20%7C%203.14-blue"></a>
  <a href="https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/lovely-assertions/lovely-assertions/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://sonarcloud.io/summary/new_code?id=lovely-assertions_lovely-assertions"><img alt="Quality gate" src="https://sonarcloud.io/api/project_badges/measure?project=lovely-assertions_lovely-assertions&amp;metric=alert_status"></a>
  <a href="https://sonarcloud.io/component_measures?id=lovely-assertions_lovely-assertions&amp;metric=coverage"><img alt="Coverage" src="https://sonarcloud.io/api/project_badges/measure?project=lovely-assertions_lovely-assertions&amp;metric=coverage"></a>
  <a href="https://github.com/lovely-assertions/lovely-assertions/blob/main/LICENSE"><img alt="License: MPL 2.0" src="https://img.shields.io/badge/license-MPL--2.0-green"></a>
</p>

Fluent, strictly-typed assertions for Python tests. `expect()` offers only what
applies to your value's type, narrowing survives the chain, and a failure turns
up as a sentence rather than a shrug.

## Install

```bash
uv add --dev lovely-assertions   # or: pip install lovely-assertions
```

Python 3.13 or newer, zero runtime dependencies, `py.typed`. Pre-1.0, so the API
can still move; when it does, the reason is in
[CHANGELOG.md](CHANGELOG.md), generated from the commit log rather than written
by hand.

## A minute with it

```python
from lovely_assertions import expect

expect("hello").starts_with("he")
expect([1, 2, 3]).contains_no_duplicates()
expect({"a": 1}).contains_key("a")
expect(3).is_positive()
```

Your editor knows there is no `starts_with` on that last line: `expect(x).` is
the catalogue for the type of `x`, and nothing else. A check is also a
narrowing, and both pyright and mypy agree about the result:

```python
raw: str | None = "ada"

name: str = expect(raw).is_not_none().subject
```

And when something is wrong, you are told what:

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

Three failures, one report — that is
[soft assertions](docs/guides/soft-assertions.md). And look at the last two:
*the key is missing* and *the key holds something else* are different bugs, and
the sentence says which instead of leaving you to work it out.

## Why not just `assert`

pytest already rewrites `assert a == b` into a passable diff, so the competition
is pytest itself and the value has to be elsewhere. It is in three places, and
breaking any one of them would leave this package with no reason to exist.

- **Typed discoverability.** A `str` subject has no `is_positive`. Nothing that
  dispatches at runtime can offer that, and neither can a raw `assert`.
- **Real narrowing.** The returned subject is re-typed, as above. The *original*
  variable is not: `TypeIs` reaches only a function's first argument, so rebind
  and the type is guaranteed. No Python assertion library does better, and this
  one [writes the limitation down](docs/getting-started/chaining-and-narrowing.md)
  rather than implying otherwise.
- **Messages that explain.** A composite value adds a difference block that stays
  bounded, so two five-thousand-element lists cost four hundred characters, not
  sixty thousand.

## Also in the box

- **Exceptions**, in the shape you already reach for: `with
  expect_raises(ValueError) as caught:`, then `caught.with_message_containing(…)`.
  The wrong exception is chained onto the failure, so its traceback survives
  beside the message instead of replacing it.
- **Your own assertions**, on the same machinery: subclass `Expect[T]`, mark the
  methods `@custom_assertion`, and inherit subject naming, soft scopes, `because`
  and the whole catalogue. See [the extension guide](docs/guides/extending.md).

## Documentation

**[Full documentation →](docs/README.md)**

| | |
|---|---|
| New here | [Installation](docs/getting-started/installation.md) · [Your first assertions](docs/getting-started/first-assertions.md) · [Reading a failure](docs/getting-started/reading-failures.md) |
| How do I assert…? | [The guides](docs/README.md#guides) — by type, and by task |
| Every assertion | [The reference](docs/reference/assertions.md), generated from the source |
| Why it works this way | [Concepts](docs/README.md#concepts) — dispatch, messages, performance, typing |
| Coming from `assert` or `assertpy` | [Migrating](docs/guides/migrating.md) |

Every Python block on those pages is executed by the test suite, and every
failure message they quote is compared against what the library actually
produces. That includes this page.

## Contributing

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run mypy && uv run pytest
```

Every one of those must be green. [CONTRIBUTING.md](CONTRIBUTING.md) has the rest: what a change usually touches,
what each CI gate proves, how a release is cut, and the terms a contribution
arrives under. Taking part means agreeing to the
[code of conduct](CODE_OF_CONDUCT.md).

## Security

Report a vulnerability privately through the
[Security tab](https://github.com/lovely-assertions/lovely-assertions/security),
not as a public issue. [SECURITY.md](SECURITY.md) also documents what the library
does on the failure path — it renders your values, and it reads the source line
you wrote the assertion on — so the boundary is written down rather than
discovered. Releases go out through PyPI
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
