---
paths:
  - "pyproject.toml"
  - "uv.lock"
  - ".python-version"
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
`project.dependencies` and never in a published extra. `uv.lock` is committed and
pins development and CI only — it never constrains a consumer.

**Every declared floor is a claim, and the claim is tested.** `mypy >= x` says
mypy x accepts this code, and both checkers change what they accept between
releases. The weekly `lowest-tooling` job resolves the declared minimums into a
throwaway lock and runs ruff, both checkers and the whole suite against them. A
floor raised without that job going green is a guess.

**`requires-python` is the other floor**, and raising it is a breaking change.
The current one is 3.13, and it is 3.13 for a specific reason: **PEP 696**
type-parameter defaults. PEP 695 syntax alone works on 3.12 — that is not what
holds the floor up. Both rows of the supported range run in CI.

**No upper bounds** unless a breakage is known and reproduced; a cap carries an
inline comment stating the exact reason and what would unlock its removal.

**Lint suppressions are scoped and explained.** A `per-file-ignores` entry names
the file and carries a comment saying which property of *that file* makes the
rule wrong there — not "noisy". A blanket ignore, or one without a reason, gets
removed. The same goes for `# noqa`: the reason is written in plain language at
the site, never as a pointer to where the reason is written down.

**Coverage configuration is not a place to win an argument.** `fail_under` is a
floor and sits just under what the suite actually reaches; raise it when the real
number rises, never lower it to let a change through. `exclude_also` may exempt
only things that are not code — a `TYPE_CHECKING` block, an `@overload` body.
A `# pragma: no cover` on a live branch is a test that was not written.

**uv pitfalls, all of which bite silently.**
- `uv lock` **preserves** already-locked versions. Upgrading needs
  `uv lock --upgrade-package <name>` (or `--upgrade`); a plain `uv lock` after a
  version bump looks like it worked and changes nothing.
- Testing lowest bounds means `rm uv.lock && uv lock --resolution lowest-direct`
  and then **`--frozen` on every subsequent sync and run**. A plain `uv sync`
  notices the lock is not the committed one and quietly re-resolves at the
  highest versions, un-testing the exact thing being tested.
- Pin the interpreter explicitly on every `uv` command (`--python 3.13`), and use
  `uv sync --locked` in CI so a stale lockfile fails rather than being papered
  over by a re-resolve.
- `astral-sh/setup-uv` enables caching by default; turn it off in any job that
  produces artifacts other people install.
