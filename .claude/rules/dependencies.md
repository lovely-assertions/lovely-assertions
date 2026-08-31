---
paths:
  - "pyproject.toml"
  - "uv.lock"
  - ".python-version"
  - ".pre-commit-config.yaml"
---

# Dependencies, packaging & tooling policy

**Zero runtime dependencies is a contract, not a preference.** `dependencies` in
`pyproject.toml` stays empty, permanently. There is no threshold at which a
dependency becomes acceptable and no extra to hide one in: this package is
installed into test suites that already carry their own trees, and adding to
theirs is a cost they did not choose. If something needs a third-party library,
it does not belong here. The claim is checked twice — once against
`pyproject.toml` by the suite, and once against the built wheel's `Requires-Dist`
by CI, because those are different things and only the second is what a user
installs.

**Dev tooling lives in `[dependency-groups]`** (PEP 735), never in
`project.dependencies` and never in a published extra. There are two groups:
`dev`, which every plain `uv sync` installs, and `fuzz`, which is opt-in and
carries a Linux-x86_64 marker because atheris publishes wheels for nothing else.
`uv.lock` is committed and pins development and CI only — it never constrains a
consumer, which does not make it nobody's problem: `security.yml` exports the
lock with `--all-groups` and runs `pip-audit --strict` over the result, so a CVE
in the development tree fails the build. It is also what decides which ruff,
pyright and mypy a checkout runs: those pre-commit hooks are `local` and call
`uv run --no-sync`, deliberately not `astral-sh/ruff-pre-commit`, which would
install its own ruff at whichever version that mirror last tagged and reformat a
file CI then rejects. One ruff in this repository, and the lock names it.

**A development dependency has to publish a wheel.** Installing a source
distribution runs that project's build code with the privileges of whoever ran
the install, which on a runner means a token; installing a wheel unpacks an
archive and does not. So the property worth holding is that there is no build to
sandbox, and `tests/test_packaging.py` reads it out of the lock rather than
trusting a flag: an ordinary `uv sync --no-build` cannot state it here, because
the project installs itself as an editable and the flag would reject the very
tree it is meant to protect. A candidate that ships only an sdist is replaced,
not exempted.

**Every declared floor is a claim, and the claim is tested — as far as one Linux
job can reach.** `mypy >= x` says mypy x accepts this code, and both checkers
change what they accept between releases. The weekly `lowest-tooling` job
resolves the declared minimums into a throwaway lock and runs `ruff check`, both
checkers and the whole suite against them. A floor raised without that job going
green is a guess. Know where it stops: it syncs the default group on Linux, so a
floor behind a platform marker, or one in the opt-in group, is exercised at no
version but the locked one. And it runs neither `ruff format --check` nor
`pytest --cov`, so the ruff floor is a claim about the linter rather than the
formatter, and the pytest-cov floor goes no further than the plugin loading.

**`requires-python` is the other floor**, and raising it is a breaking change.
The current one is 3.13, and two independent things hold it there. `Found`
carries a **PEP 696** type-parameter default, which 3.12 cannot parse, and
`typing.TypeIs` (PEP 742) is imported at module scope — not under
`TYPE_CHECKING` — by several of the shared helpers, which 3.12 cannot import
either. `import lovely_assertions` nevertheless succeeds there, because
`__init__` binds every public name lazily; the first attribute access is where
the syntax error lands. PEP 695 syntax alone works on 3.12 — that is not what
holds the floor up. Both rows of the supported range run in CI.

The floor is written down in more places than one — `requires-python`,
`.python-version`, the classifiers, ruff's `target-version`, each checker's
configured version, and the CI matrices — and nothing checks that they agree.
Raising it is an edit to every one of them, held together by discipline rather
than by a guard, and a stale one is silent. `.python-version` is the one that
decides most: it is what uv picks when no `--python` is given, so it chooses the
interpreter local work happens on.

**No upper bounds** unless a breakage is known and reproduced; a cap carries an
inline comment stating the exact reason and what would unlock its removal.

**Lint suppressions are scoped and explained.** A `per-file-ignores` entry names
the file, or the directory whose whole population shares the property, and every
code under it carries a comment saying which property of *those* files makes the
rule wrong there — not "noisy". A blanket ignore, or a code with no reason of its
own, gets removed. The path is the fragile half: ruff reports nothing at all
about an entry naming a file that no longer exists — no diagnostic, exit 0 —
while an unused `# noqa` is caught by RUF100. So the entry moves in the same
commit as the file, because nothing else will notice that it did not.

The same goes for `# noqa`: the reason is written in plain language at the site,
never as a pointer to where the reason is written down. Two forms are accepted,
and `tests/test_source_conventions.py` enforces exactly those two over `src/` —
in parentheses after the rule code, or in a comment on the line above where the
line already carries a second directive and has no room left.

**Coverage configuration is not a place to win an argument.** `fail_under` is a
floor and not a target; raise it when the real number rises, never lower it to
let a change through. What it can sit under is the *narrowest* run rather than
the best one: CI enforces it on the combined report of every platform — each row
passes `--cov-fail-under=0`, so no row fails for lines another row covers — while
a local run measures one platform and misses whatever only the others can
execute. The distance between the floor and the number CI prints is that
difference, not slack to spend. `exclude_also` may exempt only things that are
not code — a `TYPE_CHECKING` block, an `@overload` body — and its
`TYPE_CHECKING` pattern is anchored at column zero, so a guard nested inside a
class or a function is counted as missed rather than excluded. A
`# pragma: no cover` on a live branch is a test that was not written.

**uv pitfalls, all of which bite silently.**
- `uv lock` **preserves** already-locked versions. Upgrading needs
  `uv lock --upgrade-package <name>` (or `--upgrade`); a plain `uv lock` after a
  version bump looks like it worked and changes nothing.
- Testing lowest bounds means `rm uv.lock && uv lock --resolution lowest-direct`
  and then **`--frozen` on every subsequent sync and run**. A plain `uv sync`
  notices the lock is not the committed one and quietly re-resolves at the
  highest versions, un-testing the exact thing being tested.
- Pin the interpreter on every command that *resolves or creates* an environment
  (`uv lock --python 3.13`, `uv sync --python 3.13`). A later
  `uv run --no-sync` uses the environment that pin built, so pinning it again
  says nothing; with no pin anywhere, uv reads `.python-version`. Use
  `uv sync --locked` in CI so a stale lockfile fails rather than being papered
  over by a re-resolve.
- `astral-sh/setup-uv` enables caching by default; turn it off in any job that
  produces artifacts other people install.
