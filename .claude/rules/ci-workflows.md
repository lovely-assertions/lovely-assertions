---
paths:
  - ".github/**"
  - ".pre-commit-config.yaml"
  - "cliff.toml"
  - "release-please-config.json"
  - ".release-please-manifest.json"
  - "sonar-project.properties"
  - "tests/test_workflow_conventions.py"
---

# CI/CD & GitHub Actions conventions

The pipeline is deliberately hardened and minimal-supply-chain.
`security.yml` runs `zizmor` over the **whole repository** and it MUST stay clean —
a new or edited workflow keeps every convention below. The target is `.` and not
`.github/workflows/` on purpose: zizmor also audits `dependabot.yml` and the
pre-commit configuration, so the narrower target reports a clean tree that CI then
fails on.

**Most of what follows is executable, in `tests/test_workflow_conventions.py`** —
the SHA pins and their version comments, the `uvx` pins, the read-only default,
`persist-credentials: false` on every checkout, a version on every `setup-uv`, the
zizmor verdict run, the tag contract, the third-party allow-list, and
`ci-success`'s `needs:` list. It reads the files with regexes rather than a YAML
parser: the package has zero runtime dependencies and the dev group is the tooling
that enforces that, not a library imported to read files whose formatting this
repository controls. Break a convention below and pytest says so, not a reviewer —
so a convention worth having belongs in that file too.

**Pin every action to a full commit SHA, with the version in a trailing
comment** — `uses: actions/checkout@3d3c42e5...ba90b1 # v7.0.1`. Never a floating
tag (`@v7`), never a branch. Bump the SHA and the comment together, after reading
the upstream release. Dependabot is configured to make exactly that edit, which
is what keeps "pinned" from silently becoming "pinned and three years old" — a
SHA does not expire and nothing else would notice.

**A pin is checked for shape, and only for shape.** The test proves the ref is
forty hex characters and carries a version comment; it cannot know whether either
is true. The zizmor audits that would — `impostor-commit`, `ref-version-mismatch`,
`stale-action-refs` — read the GitHub API, and zizmor goes online only when handed
a token via `--gh-token` or `GH_TOKEN`. Neither `uvx zizmor` step in `security.yml`
passes one, and Actions does not put `GITHUB_TOKEN` into a step's environment by
itself, so the run announces "offline mode" and skips them: forty zeros with a
`# v99.9.9` comment passes every gate here. What verifies a pin is a person reading
the Dependabot pull request. Turning those audits on means handing that step a
token, which is a deliberate change and not a tidy-up.

**Pin `uv` itself, through the workflow-level `UV_VERSION` every `setup-uv` step
reads.** With no version, setup-uv resolves "latest" by fetching a manifest over
the network on every job — an unpinned call per job, and a real source of run
failures. The version must be one the *pinned* setup-uv knows: it verifies the
download against a checksum table baked into the action, and for an unknown
version it skips validation **silently** rather than failing. So `UV_VERSION` and
the setup-uv SHA move together; raising one without the other leaves the pin
unverified with nothing to say so. **`UV_VERSION` is declared per workflow**,
though — every workflow that runs `uv` carries its own copy and nothing compares
them, so that bump is one edit in each. Only `ci.yml` states the reason; the rest
are bare, and a half-done bump leaves the others on an old uv under a new
setup-uv, which is the silent mis-validation above.

**And pin every `uvx` tool** — `uvx zizmor==1.29.0`, not `uvx zizmor`. A bare
invocation resolves the newest release at run time, so a gate can change its mind
without a commit, which is the exact thing SHA-pinning exists to prevent. Nothing
bumps these for you: Dependabot's `github-actions` ecosystem reads `uses:`, not the
text of a `run:` script, so the `uvx` pins and `UV_VERSION` age until somebody
moves them by hand.

**Least-privilege tokens.**
- Every workflow declares top-level `permissions: contents: read`. Elevate
  per-*job*, never globally, and only to what that job needs: `security-events:
  write` on a SARIF upload, `id-token: write` wherever an OIDC identity is minted
  (the PyPI publish, the provenance attestation, Scorecard's transparency-log
  entry), `contents: write` on the one that opens a release. `release-please.yml`
  elevates nothing at all, deliberately; see below before copying it.
- Every `actions/checkout` sets `persist-credentials: false` — don't leave the
  token on disk for later steps.
- **Never interpolate event payload text into a shell script body.** A commit
  subject or PR title on a fork's pull request is attacker-controlled, and
  `${{ github.event.* }}` inside `run:` is string substitution before the shell
  ever sees it. Pass it through `env:` and reference `"$VAR"`.

**Publishing is tokenless.** PyPI uploads go through Trusted Publishing: the
credential is minted per-run from the workflow's OIDC identity, and the publisher
is bound to this repository, this workflow file *and* the environment name. No
API token exists in the repository or in a maintainer's keychain. Renaming
`release.yml` or the `pypi` environment breaks publishing until the configuration
on PyPI is updated to match — that coupling is the security property, not an
inconvenience to route around. The same identity signs what it ships: a build
provenance attestation, carried across to the Releases page as a `.sigstore.json`
so a wheel taken from there can be verified with nothing but the files, and PEP 740
attestations on the index itself.

**The version number is derived, not chosen.** `release-please.yml` reads the
commit log on every push to `main` and keeps a standing release pull request
carrying the next version; merging it writes `__version__` and `CHANGELOG.md`,
tags, and opens the GitHub release — and that tag push is what wakes `release.yml`.
`release-please-config.json` and `.release-please-manifest.json` are its two files.
It declares no elevated `permissions:` and does its writing with a token minted
from a GitHub App installation, and that is not a tidiness choice: a pull request
opened with `GITHUB_TOKEN` triggers no workflows, so the release pull request
would arrive with no `CI success` and be unmergeable without an administrator
bypassing the rule. The App token asks for `contents`, `pull-requests` and
`issues` by name rather than inheriting the installation's grants, so widening
the App later cannot silently widen the one workflow that writes to `main`.
Without `vars.RELEASE_PLEASE_APP_ID` and `secrets.RELEASE_PLEASE_PRIVATE_KEY` the
job skips with a warning.

**Two files have to agree about one string, and nothing else makes them.**
`include-component-in-tag` defaults to *true*, which tags `lovely-assertions-vX.Y.Z`,
and `release.yml` triggers on `tags: ["v*"]`. Get that wrong and every visible part
of a release still succeeds — the pull request merges, the version is written, the
tag is pushed, the release page appears — while only the publish never runs, and
nothing says so. The test pins the pair; changing either side means changing it.

**The changelog is release-please's. git-cliff renders release notes.**
`CHANGELOG.md` is written into the release pull request, before the tag, from the
commit subjects. No job regenerates it, and none should: committing from a release
workflow would put a bot commit after the tag describing it. `cliff.toml` drives
git-cliff in two narrower places — a local `--unreleased` preview of what your
commits will say, and the notes for a release cut from a *hand-pushed* tag, which
has no release page yet. On the ordinary path `release.yml` finds the release
release-please already opened and only uploads to it, so that render goes unused.
The two generators classify differently on purpose and are not interchangeable:
`cliff.toml` skips `chore`, `ci`, `style` and `test`, while
`release-please-config.json` gives `ci` and `test` visible sections. Both rest on
the commit gate — a subject that is not a Conventional Commit is classified by
neither and dropped silently by both, so weakening the gate quietly empties the
changelog. git-cliff needs the full history and the tags, so any job that runs it
checks out with `fetch-depth: 0`.

**The release runs the suite against the built wheel, not the source tree** — the
dev group is synced with `--no-install-project --no-build`, the wheel goes in with
`uv pip install --only-binary :all:`, and every test module that reads the
repository rather than the installed package is `--ignore`d by name. Add one and
it must join that list, or it fails the release at the tag, after review.
`--no-build` holds because every locked dependency publishes a wheel, which
`tests/test_packaging.py` reads out of the lock so a dependency that stops doing
so fails review instead.

**Prefer self-contained gates over third-party actions.** The conventional-commit
gate, the wheel-contract check and the release step are plain `bash` and
`python` — nothing extra to pin, audit or trust. `gh` is on the runner; reach for
it before reaching for an action that wraps it. Add a new gate the same way
unless a maintained, SHA-pinnable action is clearly better.

**Adding a third-party action is two edits, and one of them is not in this tree.**
The repository's Actions policy is *selected actions* with GitHub-owned allowed, so
anything outside the `actions` and `github` owners must be permitted in the
repository settings as well as written in a file. `ALLOWED_THIRD_PARTY_ACTIONS` in
the test is a copy of that policy kept here so adding one is a diff somebody has
to look at; it also fails on an entry no workflow uses. Doing only the file half is the
quiet failure: the pull request is green, and after the merge the workflow refuses
to *start*, with no annotation, because a workflow that cannot start produces
nothing to annotate.

**One required status check: `CI success`.** The `ci-success` job (`if: always()`
with `needs:` listing every real job) collapses the whole OS × Python matrix plus
every gate into a single status context, so branch protection never enumerates
job names. **Add a real job, add it to that `needs:` list** — a job missing from
it is a gate that cannot block anything. PR-only gates are conditioned on
`github.event_name == 'pull_request'` and are tolerated as "skipped" on a push to
`main`.

**The suite runs twice, and neither run substitutes for the other.** `test` runs
it untraced; `coverage` runs it traced. Several performance invariants read a
measurement that cannot be taken while `sys.settrace` is active and skip
themselves under coverage — folding the two jobs into one would retire those
tests without any output saying so. Coverage is collected on every platform and
combined, because the filesystem assertions branch on what the platform can
express.

**Suites too slow, too noisy or too permitted-to-fail to gate a pull request live
in `scheduled.yml`, not behind an `if:` in `ci.yml`.** Benchmarks (measured, never
asserted), the fuzzing targets (time-boxed, uploading the reproducer when
libFuzzer finds one), the next Python beta (`continue-on-error`), and the
lowest-declared-tooling resolution run weekly there. Keeping them in their own
workflow makes their exclusion from `CI success` structural rather than something
a reader has to infer from a condition. A suite that runs on no trigger at all is
the failure mode this guards against.

**CodeQL is the advanced configuration**, in `codeql.yml`. GitHub's "default
setup" for code scanning is mutually exclusive with it: enabling default setup in
the repository settings makes every run of that workflow fail. Pick one — this
repository picks the file.

**Sonar carries the same trap and takes the other way out of it.** SonarQube
Cloud's Automatic Analysis ignores `sonar-project.properties` entirely, so with it
left on the dashboard grades `tests/` and `typing_tests/negative/` as production
code and none of the scoping recorded in that file applies. Turning the `sonar`
job on means turning Automatic Analysis off in the project settings. Both of these
are a setting outside the tree deciding whether a file inside it means anything,
which is the class of thing to write down rather than rediscover.

**A job that needs code scanning either waits or degrades, and never sits red.**
Uploading SARIF needs code scanning, which a private repository only has with
GitHub Advanced Security; and Scorecard grades a repository from what it can read
publicly, so on a private one there is nothing to read. CodeQL and Scorecard
therefore gate the whole job on `github.event.repository.visibility == 'public'`
and skip. `security.yml`'s zizmor job takes the other route and splits the report
from the verdict: the SARIF upload is `continue-on-error` with a step that warns
when it failed, and the run supplying the exit code is `if: always()`, so the audit
decides the job whether or not its findings can be filed. Keep one of those two
shapes when adding anything that uploads to the Security tab. None of these jobs is
in `CI success`, so a red one blocks nothing — and a permanently red tab trains
people to stop reading the tab.

**Concurrency groups cancel superseded runs on CI (`cancel-in-progress: true`)
but never on a release (`false`)** — a half-published version cannot be taken
back, and a second push while the release pull request is being written would race
it. The rule is not universal: `scheduled.yml` and `scorecard.yml` declare no group
at all. zizmor reports that as `concurrency-limits` under the pedantic persona and
CI runs the regular one, so nothing currently objects.

**Don't invent gates that aren't wired.** Reference the checks that exist. If a
capability isn't set up — a secret that has not been added, an environment that
has not been created — say so, and make the job that needs it skip loudly rather
than fail permanently.
