#!/usr/bin/env bash
# End-to-end smoke test through the UI server only (the API is never called directly).
#
# Walks: register, log in, create team, create project, create task, comment, upload and
# download an attachment, search, CSV export, log out. Exits non-zero on the first failure.
#
# Usage: scripts/smoke.sh            (defaults to http://localhost:3000)
#        SMOKE_BASE_URL=https://taskboard.example scripts/smoke.sh
set -euo pipefail

BASE="${SMOKE_BASE_URL:-http://localhost:3000}"
WORK="$(mktemp -d)"
JAR="$WORK/cookies.txt"
trap 'rm -rf "$WORK"' EXIT

RUN_ID="$(date +%s)-$RANDOM"
EMAIL="smoke-${RUN_ID}@example.com"
PASSWORD="smoke-password-${RUN_ID}"
TITLE="Smoke task ${RUN_ID}"
COMMENT="Smoke comment ${RUN_ID}"
UUID_RE='[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}'

step() { printf '==> %s\n' "$*"; }
fail() { printf 'SMOKE FAILED: %s\n' "$*" >&2; exit 1; }

# GET a page with the cookie jar; prints the body.
get() { curl -sS --fail-with-body -b "$JAR" -c "$JAR" "$BASE$1"; }

# The CSRF form token on a page.
csrf_from() {
  get "$1" | grep -o 'name="_csrf" value="[^"]*"' | head -n 1 | sed 's/.*value="//; s/"$//'
}

# POST a urlencoded form; prints "<status> <location>".
post_form() {
  local path="$1" from="$2"
  shift 2
  local token
  token="$(csrf_from "$from")"
  [ -n "$token" ] || fail "no CSRF token on $from"
  local args=(--data-urlencode "_csrf=$token")
  for field in "$@"; do args+=(--data-urlencode "$field"); done
  curl -sS -o /dev/null -b "$JAR" -c "$JAR" -w '%{http_code} %{redirect_url}' \
    -H "Origin: $(origin)" "${args[@]}" "$BASE$path"
}

origin() { printf '%s' "$BASE" | sed -E 's#^(https?://[^/]+).*#\1#'; }

expect_redirect() {
  local result="$1" pattern="$2" what="$3"
  local status="${result%% *}" location="${result#* }"
  [ "$status" = "303" ] || fail "$what: expected 303, got $status"
  printf '%s' "$location" | grep -q "$pattern" || fail "$what: unexpected redirect to $location"
  printf '%s' "$location"
}

step "waiting for $BASE/readyz"
for _ in $(seq 1 60); do
  if curl -sS -o /dev/null --fail "$BASE/readyz" 2>/dev/null; then break; fi
  sleep 2
done
curl -sS --fail "$BASE/readyz" >/dev/null || fail "UI server is not ready"

step "register $EMAIL"
expect_redirect "$(post_form /register /register "email=$EMAIL" "display_name=Smoke $RUN_ID" \
  "password=$PASSWORD" "password_confirm=$PASSWORD")" '/login$' "register" >/dev/null

step "log in"
expect_redirect "$(post_form /login /login "email=$EMAIL" "password=$PASSWORD")" '/$' "login" >/dev/null
get / | grep -q "Smoke $RUN_ID" || fail "dashboard does not show the user"

step "create team"
TEAM_URL="$(expect_redirect "$(post_form /teams / "name=Smoke team $RUN_ID")" "/teams/$UUID_RE" "create team")"
TEAM_PATH="/${TEAM_URL#*://*/}"

step "create project"
PROJECT_URL="$(expect_redirect "$(post_form "$TEAM_PATH/projects" "$TEAM_PATH" "name=Smoke project" "webhook_url=")" \
  "/projects/$UUID_RE" "create project")"
PROJECT_PATH="/${PROJECT_URL#*://*/}"

step "create task"
TASK_URL="$(expect_redirect "$(post_form "$PROJECT_PATH/tasks" "$PROJECT_PATH" "title=$TITLE" \
  "description=**Smoke** test" "status=todo" "priority=high" "assignee_id=" "due_date=2030-01-01" \
  "labels=smoke")" "/tasks/$UUID_RE" "create task")"
TASK_PATH="/${TASK_URL#*://*/}"
get "$PROJECT_PATH" | grep -q "$TITLE" || fail "board does not show the task"

step "comment"
expect_redirect "$(post_form "$TASK_PATH/comments" "$TASK_PATH" "body=$COMMENT")" "$TASK_PATH" "comment" >/dev/null
get "$TASK_PATH" | grep -q "$COMMENT" || fail "task page does not show the comment"

step "upload attachment"
printf 'smoke attachment %s\n' "$RUN_ID" >"$WORK/upload.txt"
TOKEN="$(csrf_from "$TASK_PATH")"
UPLOAD="$(curl -sS -o /dev/null -b "$JAR" -c "$JAR" -w '%{http_code}' -H "Origin: $(origin)" \
  -F "_csrf=$TOKEN" -F "file=@$WORK/upload.txt;type=text/plain;filename=smoke.txt" "$BASE$TASK_PATH/attachments")"
[ "$UPLOAD" = "303" ] || fail "upload: expected 303, got $UPLOAD"

step "download attachment"
DOWNLOAD_PATH="$(get "$TASK_PATH" | grep -o "/attachments/$UUID_RE/download" | head -n 1)"
[ -n "$DOWNLOAD_PATH" ] || fail "task page has no attachment link"
curl -sS --fail -b "$JAR" -D "$WORK/headers.txt" -o "$WORK/download.txt" "$BASE$DOWNLOAD_PATH"
cmp -s "$WORK/upload.txt" "$WORK/download.txt" || fail "downloaded bytes differ from the upload"
grep -qi '^content-disposition: attachment' "$WORK/headers.txt" || fail "download is not an attachment"

step "search"
get "/search?q=$(printf '%s' "$RUN_ID" | sed 's/-/%2D/g')" | grep -q "$TITLE" || fail "search did not find the task"

step "CSV export"
get "$PROJECT_PATH/export.csv" | grep -q "$TITLE" || fail "CSV export does not contain the task"

step "log out"
expect_redirect "$(post_form /logout / )" '/login$' "logout" >/dev/null
STATUS="$(curl -sS -o /dev/null -b "$JAR" -w '%{http_code}' "$BASE/")"
[ "$STATUS" = "303" ] || fail "dashboard still reachable after logout (status $STATUS)"

step "smoke test passed"
