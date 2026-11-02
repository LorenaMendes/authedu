# Continuous integration

The [CI workflow](../.github/workflows/ci.yml) runs on every pull request, pushes to `main`, and manual dispatch. No path filters omit checks for documentation-only changes. Its three stable job names are suitable for required status checks once a repository administrator enables branch protection:

| Job | Checks |
| --- | --- |
| Backend | Locked install, Ruff, pytest (including migrations and PostgreSQL integration), pip-audit |
| Frontend | `npm ci`, ESLint, Vitest component/configuration tests, Vite build, npm audit |
| Repository security and workflows | actionlint (including ShellCheck), redacted Gitleaks scan of all fetched Git history |

Jobs use GitHub-hosted Ubuntu 24.04 runners. The backend reads CPython 3.14.10 from its version file and installs uv 0.13.6. The frontend reads Node.js 26.13.0 from its version file and explicitly installs npm 12.2.1 instead of relying on bundled npm. Dependency installs enforce the committed lockfiles; missing/stale locks fail rather than updating silently. There is no configured Python or JavaScript static type checker yet: Ruff/ESLint are lint checks, not type checking. Add appropriate type-check commands here and to CI when the codebase adopts one.

## Database isolation and credentials

The backend tests use the existing Testcontainers fixture with PostgreSQL 18.6 Bookworm and Ryuk 0.8.1 (Testcontainers' cleanup helper), both pinned by digest in [the test configuration](../backend/tests/conftest.py). This matters especially for Ryuk, which needs the Docker socket to clean up containers. A disposable database container receives a random process-local password; each test gets a uniquely named migrated database, removed at teardown. GitHub-hosted Linux runners provide Docker. CI does not start the persistent Compose stack, load a developer's environment, or need local secrets, TLS keys, or hosted-provider credentials.

The workflow token has only `contents: read`. Checkout does not persist Git credentials. Jobs use the normal `pull_request` event, never `pull_request_target`, and receive no explicitly configured repository secrets. Do not move these jobs to a persistent/self-hosted runner or pass secrets to PR-controlled code. An administrator may need to approve workflows from outside contributors before execution.

Actions are pinned to full commit SHAs and scanner images to immutable digests. Caches and artifact uploads are intentionally absent in this initial pipeline, reducing cross-PR cache and credential/artifact exposure. Gitleaks redacts complete secret values. Never enable shell tracing, dump environments, or publish database URLs/test credentials in logs, reports, screenshots, or artifacts. Redaction is a secondary defense, not permission to commit a secret.

## Run the same checks locally

Follow the [backend setup](../backend/README.md) and [frontend setup](../frontend/README.md). Backend integration tests require Docker; they do not touch your Compose database. From `backend/`:

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest --tb=short
```

To audit the exact locked Python runtime **and development** dependencies, export to a temporary file (excluded from Git), then remove it when finished:

```sh
(
	set -eu
	requirements_file=$(mktemp)
	trap 'rm -f "$requirements_file"' EXIT
	uv export --locked --all-groups --no-emit-project --format requirements-txt --output-file "$requirements_file"
	test -s "$requirements_file"
	uv run --locked pip-audit --strict --disable-pip --no-deps --require-hashes --requirement "$requirements_file"
)
```

The subshell stops on export/audit failure, rejects an empty export, and cleans up the temporary file without changing your shell settings. The local application is excluded from that export because it is not a published dependency. Every exported dependency is pinned and hashed. `--disable-pip --no-deps` audits that resolution without installing or re-resolving it; `--strict` fails on collection errors. Do not use blanket advisory ignores to make checks green. Registry/advisory-service unavailability fails the audit; investigate or rerun rather than suppressing it.

From `frontend/`, with Node.js 26.13.0 and npm 12.2.1:

```sh
npm ci
npm run lint
npm test
npm run build
npm audit --audit-level=low
```

Both audits include development dependencies; npm audit fails on low-or-higher advisories. Neither audit proves that the application is secure. Update a vulnerable dependency and its lockfile deliberately, then rerun the tests. Do not run automatic force-fixes without reviewing their compatibility impact.

From the repository root, validate workflows and scan committed history using the same pinned images as CI:

```sh
docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 -color
docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f git /repo --redact=100 --no-banner --log-opts="--all"
```

The history scan covers fetched commits, not ignored/untracked local files. CI checks the PR's committed changes after checkout. Treat scanner findings as sensitive even when the value is redacted. If a real secret entered Git, revoke/rotate it first and follow an agreed history-remediation process; simply deleting it in a later commit does not remove it from this scan. This scanner needs no Gitleaks Action license or separate token.

## Failure behavior and remote acceptance

Every command's nonzero exit status fails its step/job. There are no `continue-on-error` settings, advisory suppressions, or test-failure fallbacks. Job timeouts bound stalled checks; new runs cancel older runs for the same PR/ref.

The initial CI changes were merged in [PR #20](https://github.com/LorenaMendes/authedu/pull/20). Its Checks tab showed the `CI/Backend`, `CI/Frontend`, and `CI/Repository security and workflows` jobs passing; GitGuardian also passed. This confirms a passing pull-request run, not the failure-path or repository-policy checks below:

1. In a temporary branch/PR commit, deliberately change an ordinary health/component test assertion so it fails. Confirm the corresponding job fails remotely.
2. Remove the deliberate failure, push the correction, and confirm the jobs pass again before merging.
3. Have an administrator select the stable job names as required branch-protection checks if desired. Workflow files alone do not enable branch protection.

Record remote success/failure observations in the issue; local runs cannot substitute for them. Do not change repository settings without the owner's approval.

### Local implementation verification (2026-11-01)

- Backend: locked installation, Ruff, and all 30 tests passed on CPython 3.14.10; database tests used the digest-pinned disposable PostgreSQL/Ryuk images. The local test runner used a temporary host-networked container with loopback Testcontainers settings because `uv` was not installed on the host. This runner configuration is not needed on GitHub-hosted runners.
- Frontend: `npm ci`, ESLint, all 7 tests, Vite build, and npm audit passed on Node.js 26.13.0/npm 12.2.1.
- Strict pip-audit and npm audit reported no known vulnerabilities at verification time. This is a dated observation, not a permanent guarantee.
- actionlint/ShellCheck and the redacted full-history Gitleaks scan passed.
- A temporary ordinary pytest assertion failure returned exit code 1 as required. The probe was outside the repository and was removed; it is not a permanent failing test.
- The passing remote PR run is verified above. Remote deliberate-failure verification and branch-protection configuration remain pending.

## Later browser security flows

There is **no Playwright/browser authentication coverage yet**. When E2–E4 add registration, sessions, ownership/admin policy, and JWT flows, add a separate browser job. It should provision isolated data and local HTTPS, install pinned Playwright browsers, wait for service readiness, and exercise success/rejection flows and cookie/token-storage guarantees. Keep traces, screenshots, and recordings disabled unless they are demonstrably credential-free. Component tests and a successful build are not evidence of browser security-flow coverage.

**Learning exercise:** Make an ordinary test fail on a temporary branch. Why must a failed security audit or unavailable advisory service also block a green CI result rather than being ignored?