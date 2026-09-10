#!/usr/bin/env bash
set -euo pipefail

archive=${1:?usage: scripts/deploy-dev.sh release/opendata-<sha>.tar.gz}
checksum="${archive}.sha256"
remote=${OPENDATA_DEV_HOST:-ubuntu@10.10.0.2}
remote_root=${OPENDATA_DEV_ROOT:-/opt/opendata}

[[ -f "$archive" && -f "$checksum" ]]
(
  cd "$(dirname "$archive")"
  sha256sum --check "$(basename "$checksum")"
)
source_sha=$(basename "$archive" | sed -E 's/^opendata-([0-9a-f]{40})\.tar\.gz$/\1/')
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]

scp "$archive" "$checksum" "$remote:/tmp/"
ssh "$remote" "bash -s" -- "$source_sha" "$remote_root" "$(basename "$archive")" <<'REMOTE'
set -euo pipefail
source_sha=$1
root=$2
archive_name=$3
cd /tmp
sha256sum --check "${archive_name}.sha256"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
tar -xzf "$archive_name" -C "$stage"
[[ $(<"$stage/RELEASE_SOURCE_SHA") == "$source_sha" ]]
python3 - "$stage/dist/release-manifest.json" "$source_sha" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf8') as source:
    assert json.load(source)['source_sha'] == sys.argv[2]
PY
# Preserve ignored runtime state and venv. Replace only versioned app files + dist.
tar -C "$stage" -cf - . | tar -C "$root" --exclude=.env.local --exclude=.venv --exclude=var --exclude=.git --exclude=.hermes -xf -
sudo systemctl restart opendata-api.service opendata-worker.service
systemctl is-active opendata-api.service opendata-worker.service
REMOTE
