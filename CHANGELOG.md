# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**This file is generated** from the commit log by
[git-cliff](https://git-cliff.org). Don't edit it -- write the commit message,
which a CI gate already requires to be a Conventional Commit.

## [0.2.0](https://github.com/lovely-assertions/lovely-assertions/compare/v0.1.0...v0.2.0) (2026-09-01)


### ⚠ BREAKING CHANGES

* **license:** the Mozilla Public License 2.0, from 0.2.0 on ([#30](https://github.com/lovely-assertions/lovely-assertions/issues/30))

### Features

* **license:** the Mozilla Public License 2.0, from 0.2.0 on ([#30](https://github.com/lovely-assertions/lovely-assertions/issues/30)) ([93b5462](https://github.com/lovely-assertions/lovely-assertions/commit/93b54621a495f16079c21aa147eb0d835d3e1613))


### Performance

* **imports:** load a subject the first time a value needs one, not at import ([#21](https://github.com/lovely-assertions/lovely-assertions/issues/21)) ([2523965](https://github.com/lovely-assertions/lovely-assertions/commit/2523965f97da5af64ab14f3583dfd1a4b3355466))


### Documentation

* **concepts:** correct what the design pages claim about the library ([#34](https://github.com/lovely-assertions/lovely-assertions/issues/34)) ([d0cd564](https://github.com/lovely-assertions/lovely-assertions/commit/d0cd564e6c2b53ce4819e1bdf7145451f5bc587f))
* **contributing:** state the terms a contribution arrives under ([#29](https://github.com/lovely-assertions/lovely-assertions/issues/29)) ([a5b9687](https://github.com/lovely-assertions/lovely-assertions/commit/a5b96877855d23ce01bd283864a38a1ed187ce68))
* **getting-started:** correct the entry path, and give two pages an opening ([#33](https://github.com/lovely-assertions/lovely-assertions/issues/33)) ([682ccd0](https://github.com/lovely-assertions/lovely-assertions/commit/682ccd0a327dbffc3d82b56b29018fcec4752259))
* give each repeated lesson one owner, and define the words the tree relies on ([#38](https://github.com/lovely-assertions/lovely-assertions/issues/38)) ([adff86e](https://github.com/lovely-assertions/lovely-assertions/commit/adff86eba435a46b20139a43186a2162ad6ec687))
* **guides:** correct the last seven guides, and state the halves that fail silently ([#37](https://github.com/lovely-assertions/lovely-assertions/issues/37)) ([802546d](https://github.com/lovely-assertions/lovely-assertions/commit/802546d215786dd2130db8bab74f3ccf7c298f40))
* **guides:** correct the translation tables, and the Jest claim the source made too ([#36](https://github.com/lovely-assertions/lovely-assertions/issues/36)) ([24e297d](https://github.com/lovely-assertions/lovely-assertions/commit/24e297df043187661782b124df9ceb0630c27fcd))
* **internal:** the guidance describes the tree it is guidance for ([#28](https://github.com/lovely-assertions/lovely-assertions/issues/28)) ([5e0e265](https://github.com/lovely-assertions/lovely-assertions/commit/5e0e2652d9004aa90a82a5834039e48bccf1015f))
* **readme:** keep the logo out of the documentation corpus, and restore the H1 ([#32](https://github.com/lovely-assertions/lovely-assertions/issues/32)) ([a174a60](https://github.com/lovely-assertions/lovely-assertions/commit/a174a6067193d25304a4f73c52a1aaeda0424127))
* **readme:** the logo, five fewer paragraphs, and badges that report something ([#31](https://github.com/lovely-assertions/lovely-assertions/issues/31)) ([8d2af02](https://github.com/lovely-assertions/lovely-assertions/commit/8d2af02127279816d4498dd5f5d352b65332f513))


### Refactoring

* **callable:** three families, split by what each one is asked ([#20](https://github.com/lovely-assertions/lovely-assertions/issues/20)) ([0d6b90b](https://github.com/lovely-assertions/lovely-assertions/commit/0d6b90bfecaab401e0000ca57588113ac1a4d22a))
* **collection:** one file per seam, over a shared root ([#16](https://github.com/lovely-assertions/lovely-assertions/issues/16)) ([4b282e3](https://github.com/lovely-assertions/lovely-assertions/commit/4b282e323b6ce4fa808cd4c89897167070328bc4))
* **core:** assemble the subject from one mixin per seam ([#14](https://github.com/lovely-assertions/lovely-assertions/issues/14)) ([194bbea](https://github.com/lovely-assertions/lovely-assertions/commit/194bbeaaa060a1efdc3388205a9eeff90a48546c))
* **datetime:** the seams are the classes, made into files ([#19](https://github.com/lovely-assertions/lovely-assertions/issues/19)) ([77cafdc](https://github.com/lovely-assertions/lovely-assertions/commit/77cafdc6513c5a5312556ae8302ea346e3208cc2))
* **diff:** one file per kind of thing being compared ([#10](https://github.com/lovely-assertions/lovely-assertions/issues/10)) ([443efb5](https://github.com/lovely-assertions/lovely-assertions/commit/443efb5300dfee6190e7197133beb4829120c1fd))
* **enum:** three families of question, and the helpers behind them ([#25](https://github.com/lovely-assertions/lovely-assertions/issues/25)) ([668292d](https://github.com/lovely-assertions/lovely-assertions/commit/668292d2c2724d455e00496e371a987d2d0a7bea))
* **equivalence:** one file per question the engine has to answer ([#22](https://github.com/lovely-assertions/lovely-assertions/issues/22)) ([92dbf2e](https://github.com/lovely-assertions/lovely-assertions/commit/92dbf2ef24827073f7448dfaf59fb47c5b357c03))
* **formatting:** separate the registries, the limits and the scope ([#12](https://github.com/lovely-assertions/lovely-assertions/issues/12)) ([0976a68](https://github.com/lovely-assertions/lovely-assertions/commit/0976a68b9b4293c88f49fd7a62fb42b48c9a612f))
* **matching:** one file per placeholder, and the naming halves apart ([#13](https://github.com/lovely-assertions/lovely-assertions/issues/13)) ([605bc90](https://github.com/lovely-assertions/lovely-assertions/commit/605bc9051f36705bdce30ac59570a00ab146093a))
* **occurrence:** the protocol, the constraints, and the words for them ([#26](https://github.com/lovely-assertions/lovely-assertions/issues/26)) ([d7c009b](https://github.com/lovely-assertions/lovely-assertions/commit/d7c009b7df5424c9c01fe40f265f9e2f96f29343))
* **ordered:** the protocol, the words, and three families of comparison ([#27](https://github.com/lovely-assertions/lovely-assertions/issues/27)) ([479f573](https://github.com/lovely-assertions/lovely-assertions/commit/479f573514166de5df84a675b2fd9666396e6dae))
* **path:** two subjects, split by whether the disk is asked ([#18](https://github.com/lovely-assertions/lovely-assertions/issues/18)) ([4641808](https://github.com/lovely-assertions/lovely-assertions/commit/4641808c5dc3097bf9506299f75a77340d6bf160))
* **reflection:** split the leaves by the question they answer ([#11](https://github.com/lovely-assertions/lovely-assertions/issues/11)) ([decf57f](https://github.com/lovely-assertions/lovely-assertions/commit/decf57f69a4fc4b1332446f7f02cf176136f6b57))
* **sequence:** split the two subjects that inherit a catalogue ([#17](https://github.com/lovely-assertions/lovely-assertions/issues/17)) ([ddcebb3](https://github.com/lovely-assertions/lovely-assertions/commit/ddcebb33853aa0bb37491f7b09f92506410fb2b6))
* **string:** one file per seam of the widest catalogue ([#15](https://github.com/lovely-assertions/lovely-assertions/issues/15)) ([5624f33](https://github.com/lovely-assertions/lovely-assertions/commit/5624f332d7a20aed059f84da9b3f64e168c4e93b))
* **type:** four families of question, and the helpers behind them ([#23](https://github.com/lovely-assertions/lovely-assertions/issues/23)) ([e68a4c4](https://github.com/lovely-assertions/lovely-assertions/commit/e68a4c4f6046025ed165f1629fdd631fc482ffd7))


### Tests

* **guards:** walk the package once, so a subpackage cannot blind a rule ([#8](https://github.com/lovely-assertions/lovely-assertions/issues/8)) ([024fcd4](https://github.com/lovely-assertions/lovely-assertions/commit/024fcd47fd8a042c9566598edc45bc32001a0bad))

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
