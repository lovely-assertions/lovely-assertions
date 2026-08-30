# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**This file is generated** from the commit log by
[git-cliff](https://git-cliff.org). Don't edit it -- write the commit message,
which a CI gate already requires to be a Conventional Commit.

## 0.1.0 (2026-08-30)


### Features

* fluent, strictly-typed assertions for Python tests ([c7b0448](https://github.com/lovely-assertions/lovely-assertions/commit/c7b04485d3b33c2553347d9be53b44a54ad6b378))


### Documentation

* correct what the pages got wrong, and run the README ([#2](https://github.com/lovely-assertions/lovely-assertions/issues/2)) ([42d3fc5](https://github.com/lovely-assertions/lovely-assertions/commit/42d3fc5a627cd89053adc0e2344a958feb9b96b2))


### CI

* **codeql:** analyse with security-extended, not security-and-quality ([#1](https://github.com/lovely-assertions/lovely-assertions/issues/1)) ([b3d5d6a](https://github.com/lovely-assertions/lovely-assertions/commit/b3d5d6a245be54e58d33896d089a9b35e2ab5b14))
* **release:** derive the version from the commit log with release-please ([#4](https://github.com/lovely-assertions/lovely-assertions/issues/4)) ([3c18126](https://github.com/lovely-assertions/lovely-assertions/commit/3c18126c0c6bc89a426421c11ba717aec9d49f5a))
* **release:** tag as `v0.1.0`, and pin what nothing else connects ([#6](https://github.com/lovely-assertions/lovely-assertions/issues/6)) ([729149c](https://github.com/lovely-assertions/lovely-assertions/commit/729149c1f5426169ea3b8fee7db0a67bb23fe004))
* **sonar:** harden the release gate, and scope what Sonar grades ([#3](https://github.com/lovely-assertions/lovely-assertions/issues/3)) ([30a64c4](https://github.com/lovely-assertions/lovely-assertions/commit/30a64c490d4386cb057f3af5310d4c83ec973a42))

## [0.1.0] - 2026-08-29

### Added

- Fluent, strictly-typed assertions for Python tests

  `expect(value).is_equal_to(...)`. The competition is not assertpy or
  PyHamcrest — it is pytest's own assert rewriting, which already introspects
  `assert a == b` and prints a decent diff. So this library claims three things
  instead, and breaking any one of them would leave it with no reason to exist.

  **Typed discoverability.** `expect(x).` offers only the assertions valid for
  the type of `x`. A `str` subject has no `is_positive`. Dispatch is one table
  written twice — an `@overload` chain a checker walks, and a runtime branch
  order that walks the same one — so what you are offered and what you get
  cannot disagree.

  **Real narrowing.** `expect(raw).is_not_none().subject` is a `str` to both
  pyright and mypy, not an `object`. The limitation is stated rather than
  hidden: the caller's own variable stays `str | None`, because `TypeIs` can
  only narrow a function's first positional argument and `expect()` captures
  its subject inside a wrapper. Narrowing flows through the returned subject —
  rebind it, and the type is statically guaranteed.

  **Failure messages that explain.** A sentence naming the subject, what was
  expected, and what was actually there:

      Expected server_config to contain key 'hostname' (did you mean 'host'?),
      but the keys were ['host'].

  A missing key and a key holding the wrong value are different bugs and get
  different sentences. Difference blocks are bounded, so comparing two very
  large lists costs a few hundred characters rather than the lists themselves.

  Subjects for strings, numbers, collections, sequences, mappings, dates and
  times, paths, exceptions, warnings, mocks, types and enums; soft assertions,
  asymmetric matchers, structural equivalence, occurrence counting, output
  control, and an extension API that hands a subclass the whole inherited
  catalogue.

  Zero runtime dependencies, permanently — this package is installed into test
  suites that already carry their own trees, and adding to theirs is a cost
  they did not choose. Python 3.13+, `py.typed`, full type completeness,
  pyright and mypy both strict and both green on 3.13 and 3.14.

  A passing assertion costs a comparison and a `return self`: no allocation, no
  frame inspection, no message built. The failure path may do whatever it needs
  to explain itself.

  Every Python block in the documentation is executed by the test suite and
  every failure message it quotes is compared against what the library actually
  prints, so a page cannot drift from the code without failing the build.
