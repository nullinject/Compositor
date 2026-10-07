#!/bin/bash
# Uses installed CLT / SDK 15.5. No installation, download or security-policy change.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/build-clt.py" "$@"
