---
paths:
  - ".github/**"
  - "cliff.toml"
---

# CI/CD & GitHub Actions conventions

The pipeline is deliberately hardened and minimal-supply-chain.
`security.yml` runs `zizmor` over the **whole repository** and it MUST stay clean —
a new or edited workflow keeps every convention below. The target is `.` and not
`.github/workflows/` on purpose: zizmor also audits `dependabot.yml` and the
pre-commit configuration, so the narrower target reports a clean tree that CI then
fails on. That exact mismatch has already cost one red build here.

**Pin every action to a full commit SHA, with the version in a trailing
comment** — `uses: actions/checkout@3d3c42e5...ba90b1 # v7.0.1`. Never a floating
tag (`@v7`), never a branch. Bump the SHA and the comment together, after reading
the upstream release. Dependabot is configured to make exactly that edit, which
is what keeps "pinned" from silently becoming "pinned and three years old" — a
SHA does not expire and nothing else would notice.

**Pin `uv` itself, through the workflow-level `UV_VERSION` every `setup-uv` step
reads.** With no version, setup-uv resolves "latest" by fetching a manifest over
the network on every job — an unpinned call per job, and a real source of run
failures. The version must be one the *pinned* setup-uv knows: it verifies the
download against a checksum table baked into the action, and for an unknown
version it skips validation **silently** rather than failing. So `UV_VERSION` and
the setup-uv SHA move together; raising one without the other leaves the pin
unverified with nothing to say so.

**And pin every `uvx` tool** — `uvx zizmor==1.29.0`, not `uvx zizmor`. A bare
invocation resolves the newest release at run time, so a gate can change its mind
without a commit, which is the exact thing SHA-pinning exists to prevent.

**Least-privilege tokens.**
- Every workflow declares top-level `permissions: contents: read`. Elevate
  per-*job*, never globally, and only to what that job needs: `security-events:
  write` on a SARIF upload, `id-token: write` on the publish job, `contents:
  write` on the one that opens a release.
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
inconvenience to route around.

**The changelog is generated, and the release body comes from the same
template.** `cliff.toml` drives git-cliff over the commit log; `CHANGELOG.md` is
regenerated at release time and the GitHub release body is rendered from the
commits in the tag. The two therefore cannot disagree about the same release, and
nobody has to remember to write an entry. This only works because the commit gate
holds: a subject that is not a Conventional Commit cannot be classified, and
`filter_unconventional` drops it silently. So the gate and the generator are one
mechanism — weakening the gate quietly empties the changelog. git-cliff needs the
full history and the tags, so any job that runs it checks out with
`fetch-depth: 0`.

**Prefer self-contained gates over third-party actions.** The conventional-commit
gate, the wheel-contract check and the release step are plain `bash` and
`python` — nothing extra to pin, audit or trust. `gh` is on the runner; reach for
it before reaching for an action that wraps it. Add a new gate the same way
unless a maintained, SHA-pinnable action is clearly better.

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
in `scheduled.yml`, not behind an `if:` in `ci.yml`.** Benchmarks (measured,
never asserted), the next Python beta (`continue-on-error`), and the
lowest-declared-tooling resolution run weekly there. Keeping them in their own
workflow makes their exclusion from `CI success` structural rather than something
a reader has to infer from a condition. A suite that runs on no trigger at all is
the failure mode this guards against.

**CodeQL is the advanced configuration**, in `codeql.yml`. GitHub's "default
setup" for code scanning is mutually exclusive with it: enabling default setup in
the repository settings makes every run of that workflow fail. Pick one — this
repository picks the file.

**Three jobs need the repository to be public**, and will be red on a private one
however correct they are: anything uploading SARIF to code scanning (CodeQL, and
the `zizmor` job in `security.yml`) needs code scanning, which on a private
repository means GitHub Advanced Security; and Scorecard grades a repository from
what it can read publicly, so on a private one there is nothing to read. Scorecard
is gated on `github.event.repository.visibility` for that reason. None of the
three is in `CI success`, so none of them blocks a merge — but a permanently red
tab trains people to stop looking, so if the repository is going to stay private,
turn them off rather than leaving them failing.

**Concurrency groups cancel superseded runs on CI (`cancel-in-progress: true`)
but never on a release (`false`)** — a half-published version cannot be taken
back.

**Don't invent gates that aren't wired.** Reference the checks that exist. If a
capability isn't set up — a secret that has not been added, an environment that
has not been created — say so, and make the job that needs it skip loudly rather
than fail permanently.
