# Security policy

## Supported versions

This project is pre-1.0. Security fixes go onto the latest released version
only; there are no maintained release branches yet. When that changes, this
section will say so.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting: go to the
[Security tab](https://github.com/lovely-assertions/lovely-assertions/security)
and choose **Report a vulnerability**. That opens a private thread with the
maintainers, and it is the only channel that does not disclose the problem while
it is being fixed.

Useful things to include, in rough order of usefulness:

- the version of `lovely-assertions`, and the Python version;
- a snippet that reproduces the behaviour;
- what you expected instead, and what an attacker gains from the difference.

You should get an acknowledgement within a week. If a fix is warranted, you will
be credited in the changelog entry unless you ask not to be.

## What is in scope

This is a test-time assertion library with **no runtime dependencies**. It is
not a sandbox and does not claim to be one, so a few things are worth stating
plainly rather than leaving to be discovered:

- **Failure messages render values you give it.** Building a message calls
  `repr()` — and any formatter you registered — on the subject. If a subject's
  `__repr__` has a side effect, an assertion failure triggers it. Values whose
  `repr` raises are caught and rendered as an unusable-repr placeholder; values
  whose `repr` is merely enormous are clipped.
- **Subject naming reads your source file.** When an assertion fails, the
  library recovers the expression you wrote by reading the calling frame's
  source line from disk and parsing it. It reads only the file the frame names,
  and only on the failure path. If that is unacceptable in your environment,
  nothing you do is affected on the passing path — no source is read there at all.
- **Predicates and inspectors you pass are called.** `satisfies`, `where` and
  matchers built from `matching(...)` run your callable. The library does not
  sandbox it.

Reports that these documented behaviours exist are not vulnerabilities. A way to
make one of them do something it does not document — reading a file the frame
does not name, evaluating source it was not given — is.

## Supply chain

- Releases are published to PyPI through
  [Trusted Publishing](https://docs.pypi.org/trusted-publishers/): no API token
  exists in this repository or in any maintainer's keychain, and the credential
  is minted per-run from the release workflow's own identity.
- Every artifact carries a signed
  [build provenance attestation](https://github.com/lovely-assertions/lovely-assertions/attestations)
  linking it to the commit and workflow that produced it.
- Every GitHub Action is pinned to a full commit SHA. `zizmor` audits the whole
  repository — the workflows, `dependabot.yml` and the pre-commit configuration —
  and `pip-audit` checks the locked development tree. Both run on every push to
  `main`, on any pull request touching a workflow, `uv.lock` or `pyproject.toml`,
  and again on a weekly schedule, so a finding published after a change still
  surfaces without one.
- Dependabot keeps the Actions and the development dependencies current, and its
  pull requests go through the same required checks as any other.
