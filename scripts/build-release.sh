#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_sha=$(git -C "$root" rev-parse HEAD)
out_dir="${1:-$root/release}"
stage=$(mktemp -d)
cleanup() { rm -rf "$stage"; }
trap cleanup EXIT

rm -rf "$out_dir"
mkdir -p "$out_dir" "$stage/app"
git -C "$root" archive --format=tar "$source_sha" | tar -xf - -C "$stage/app"
OPENDATA_BUILD_SHA="$source_sha" npm --prefix "$root" run build
cp -a "$root/dist" "$stage/app/dist"
printf '%s\n' "$source_sha" > "$stage/app/RELEASE_SOURCE_SHA"
tar -C "$stage/app" -czf "$out_dir/opendata-${source_sha}.tar.gz" .
(
  cd "$out_dir"
  sha256sum "opendata-${source_sha}.tar.gz" > "opendata-${source_sha}.tar.gz.sha256"
)
printf '%s\n' "$out_dir/opendata-${source_sha}.tar.gz"
