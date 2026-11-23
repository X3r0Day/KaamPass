#!/usr/bin/env bash
# Source the idempotent local configuration from the repository root.
set -euo pipefail
umask 077
if [[ ! -e .env ]]; then
  python3 - <<'PY'
from pathlib import Path
from secrets import token_hex

password = token_hex(24)
Path(".env").write_text(f"""LOCAL_DB_PASSWORD={password}
DATABASE_URL=postgresql+psycopg://kaampaas:{password}@127.0.0.1:55464/kaampaas
APP_ENV=local
WEB_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
CSRF_SECRET={token_hex(40)}
FIREBASE_PROJECT_ID=demo-kaampaas
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:19099
LOCAL_API_ORIGIN=http://127.0.0.1:18031
NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL=http://127.0.0.1:19099
NEXT_PUBLIC_FIREBASE_PROJECT_ID=demo-kaampaas
NEXT_PUBLIC_FIREBASE_API_KEY=local-emulator-only
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=localhost
NEXT_PUBLIC_FIREBASE_APP_ID=local-kaampaas
""")
PY
fi
