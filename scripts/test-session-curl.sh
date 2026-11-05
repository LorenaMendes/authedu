#!/usr/bin/env bash
# Local-only API smoke test. Never source this script or run it with bash -x.
set +x
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  printf '%s\n' \
    'Usage: bash scripts/test-session-curl.sh' \
    'Requires running Docker Compose services, curl, python3, and trusted local HTTPS.' \
    'Creates one random local test account; it is not deleted automatically.' \
    'Does not print passwords, session cookies, or CSRF proofs.'
  exit 0
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."
for executable in docker curl python3; do
  command -v "$executable" >/dev/null || {
    printf 'Missing required command: %s\n' "$executable" >&2
    exit 1
  }
done

binding=$(docker compose port frontend 5173 2>/dev/null) || {
  printf 'Frontend is stopped. Start the stack with: docker compose up --build -d\n' >&2
  exit 1
}
port=${binding##*:}
if [[ ! "$port" =~ ^[0-9]+$ ]]; then
  printf 'Could not detect the frontend port. Start the Compose stack first.\n' >&2
  exit 1
fi
origin="https://localhost:$port"
configured_origin=$(docker compose exec -T backend python -c \
  'import os; print(os.environ.get("AUTHEDU_PUBLIC_ORIGIN", ""))' 2>/dev/null) || {
  printf 'Backend is stopped. Start the stack with: docker compose up --build -d\n' >&2
  exit 1
}
if [[ "$configured_origin" != "$origin" ]]; then
  printf 'Origin mismatch. Set AUTHEDU_PUBLIC_ORIGIN=%s in .env, then run:\n' "$origin" >&2
  printf 'docker compose up -d backend frontend\n' >&2
  exit 1
fi

umask 077
workdir=$(mktemp -d)
trap 'rm -rf -- "$workdir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
jar="$workdir/cookies"
base="$origin/api"

# Response bodies and curl headers stay private, including on rejected requests.
request() {
  local label=$1 expected=$2 path=$3 code
  shift 3
  if ! code=$(curl --disable --silent --show-error --connect-timeout 5 --max-time 30 \
    --output "$workdir/response.json" --write-out '%{http_code}' "$@" "$base$path"); then
    printf 'FAIL: %s — connection/TLS error at %s. Check Compose and local CA trust.\n' \
      "$label" "$origin" >&2
    exit 1
  fi
  if [[ "$code" != "$expected" ]]; then
    printf 'FAIL: %s — expected HTTP %s, received %s.\n' "$label" "$expected" "$code" >&2
    printf 'Bodies are not displayed because they may contain sensitive values.\n' >&2
    exit 1
  fi
  printf 'PASS: %s (HTTP %s)\n' "$label" "$code"
}

printf 'Testing %s using a generated throwaway account.\n' "$base"
request 'API reachable' 200 /health
python3 - "$workdir/credentials.json" <<'PY'
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

Path(sys.argv[1]).write_text(json.dumps({
    "email": f"curl-{uuid4().hex}@example.com",
    "password": secrets.token_urlsafe(32),
}))
PY

request 'Register' 200 /register \
  -H 'Content-Type: application/json' --data-binary "@$workdir/credentials.json"
request 'Login' 200 /login \
  -H "Origin: $origin" -H 'Content-Type: application/json' \
  --cookie-jar "$jar" --data-binary "@$workdir/credentials.json"
rm -f -- "$workdir/credentials.json"
request 'Current user' 200 /me --cookie "$jar"

# Write the CSRF header without exposing its value in process arguments.
python3 - "$workdir/response.json" "$workdir/csrf-header" <<'PY'
import json
import re
import sys
from pathlib import Path

try:
    token = json.loads(Path(sys.argv[1]).read_text())["csrf_token"]
    if not isinstance(token, str) or not re.fullmatch(r"v1\.[A-Za-z0-9_-]{43}\.[0-9a-f]{64}", token):
        raise ValueError
    Path(sys.argv[2]).write_text(f"X-CSRF-Token: {token}\n")
except (KeyError, ValueError, TypeError, OSError):
    raise SystemExit("FAIL: Current-user response did not contain a valid CSRF proof.") from None
PY

request 'Reject logout without CSRF' 403 /logout \
  -X POST -H "Origin: $origin" --cookie "$jar"
request 'Rejected logout preserved session' 200 /me --cookie "$jar"
cp "$jar" "$workdir/old-cookies"
request 'Logout' 204 /logout -X POST \
  -H "Origin: $origin" -H "@$workdir/csrf-header" --cookie "$jar" --cookie-jar "$jar"
request 'Logged-out client rejected' 401 /me --cookie "$jar"
request 'Revoked cookie rejected' 401 /me --cookie "$workdir/old-cookies"
printf 'Done. Private temporary files removed on exit; the local test account remains.\n'