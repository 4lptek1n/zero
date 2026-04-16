#!/usr/bin/env bash
# Decompress the *.sqlite.gz files committed under results/ back into *.sqlite.
# These are gzip-compressed only because GitHub's blob API caps individual
# uploads — the underlying SQLite files are exactly what `zero` writes.
set -euo pipefail
cd "$(dirname "$0")/.."

found=0
while IFS= read -r -d '' gz; do
    target="${gz%.gz}"
    if [ -f "${target}" ] && [ "${target}" -nt "${gz}" ]; then
        echo "[decompress] up-to-date: ${target}"
    else
        echo "[decompress] ${gz} -> ${target}"
        gunzip -k -f -c "${gz}" > "${target}"
    fi
    found=$((found+1))
done < <(find results -name '*.sqlite.gz' -print0)

echo "[decompress] done (${found} files)"
