#!/usr/bin/env bash
# Commit subjects are `<type>(<scope>): <description>` and carry no attribution
# trailers. Both rules were enforced by the devenv layer this repo used to
# import; they live here so the convention outlives the layer.
set -euo pipefail

message_file="$1"
subject="$(head -n 1 "$message_file")"

# Git writes these itself, or writes them on the developer's behalf during a
# rebase, so they are not the author's to conform.
case "$subject" in
fixup!* | squash!* | amend!* | Merge* | Revert*) exit 0 ;;
esac

types='feat|fix|docs|refactor|perf|test|build|ci|chore'

if ! printf '%s' "$subject" | grep -qE "^($types)(\([a-z0-9._/-]+\))?!?: .+"; then
  echo "commit subject does not follow <type>(<scope>): <description>" >&2
  echo "  subject: $subject" >&2
  echo "  types:   ${types//|/, }" >&2
  exit 1
fi

if grep -qiE '^(co-authored-by|signed-off-by):' "$message_file"; then
  echo "attribution trailers are not used in this repository" >&2
  exit 1
fi
