#!/usr/bin/env bash

set -euo pipefail

PYTHON="${PYTHON:-python3}"

echo "Python: $("$PYTHON" --version)"

STREAMING_FILE="$(
    "$PYTHON" - <<'PY'
import inspect
import schwab.streaming
print(inspect.getfile(schwab.streaming))
PY
)"

"$PYTHON" - <<'PY'
import inspect
import schwab
import websockets

print(f"schwab-py: {getattr(schwab, '__version__', 'unknown')}")
print(f"websockets: {websockets.__version__}")
print(inspect.getfile(schwab.streaming))
PY

echo "schwab/streaming.py:"
echo "  $STREAMING_FILE"

if [[ ! -f "$STREAMING_FILE" ]]; then
    echo "ERROR: Schwab streaming module not found." >&2
    exit 1
fi

if grep -qF \
    'import websockets.asyncio.client as ws_client' \
    "$STREAMING_FILE"
then
    echo "WebSockets compatibility: already patched."

elif grep -qF \
    'import websockets.legacy.client as ws_client' \
    "$STREAMING_FILE"
then
    echo "WebSockets compatibility: legacy import detected."

    echo "Makeing BACKUP file"
    BACKUP_FILE="${STREAMING_FILE}.trading_app_backup"
    if [[ ! -f "$BACKUP_FILE" ]]; then
        cp "$STREAMING_FILE" "$BACKUP_FILE"
    fi
    echo "Applying compatibility patch..."

    sed -i \
        's/import websockets\.legacy\.client as ws_client/import websockets.asyncio.client as ws_client/' \
        "$STREAMING_FILE"

    if ! grep -qF \
        'import websockets.asyncio.client as ws_client' \
        "$STREAMING_FILE"
    then
        echo "ERROR: Compatibility patch failed." >&2
        exit 1
    fi

    echo "WebSockets compatibility: patch applied."

else
    echo "ERROR: Unexpected schwab/streaming.py version." >&2
    echo "Neither legacy nor modern WebSockets import was found." >&2
    exit 1
fi

echo "Starting trading application..."

exec "$PYTHON" -m trading_app.main
