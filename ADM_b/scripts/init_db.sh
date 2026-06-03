#!/usr/bin/env bash
#
# ADM Backend - DB & environment initializer (idempotent)
#
# Bootstraps PostgreSQL roles, the database, applies migrations, and creates
# a fresh .env populated with strong secrets. Safe to re-run.
#
#   ./scripts/init_db.sh
#
# Requirements: psql in PATH, openssl, python3, an admin PG role with CREATEDB
# (defaults to the current OS user via peer auth on local dev).

set -euo pipefail

# Move to ADM_b root (scripts/.. == ADM_b)
cd "$(dirname "$0")/.."

# -------- 1. .env --------
if [ ! -f .env ]; then
  echo "[init_db] creating .env from .env.example with generated secrets"
  cp .env.example .env
  python3 - <<'PY'
import pathlib, secrets, string

def token(n):
    alpha = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alpha) for _ in range(n))

p = pathlib.Path('.env')
text = p.read_text()
text = text.replace('__APP_PASSWORD__', token(32))
text = text.replace('__MIGRATOR_PASSWORD__', token(32))
text = text.replace('__JWT_SECRET__', token(64))
text = text.replace('__SIGNED_URL_SECRET__', token(64))
text = text.replace('__LICENSE_SECRET__', token(64))
import subprocess
lic_enc_key = subprocess.check_output(['openssl', 'rand', '-hex', '32']).decode().strip()
text = text.replace('__LIC_ENC_KEY__', lic_enc_key)
p.write_text(text)
PY
  chmod 600 .env
else
  echo "[init_db] .env already exists, leaving in place"
fi

# Load .env
set -a
# shellcheck disable=SC1091
source .env
set +a

ADMIN_DB="${ADMIN_DB:-postgres}"

# -------- 2. PG roles (idempotent) --------
# Uses psql variables (:'role'/:'pw') + format(%I,%L) so role/password are
# safely quoted regardless of contents.
ensure_role() {
  local role=$1
  local pw=$2
  psql -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 -v role="${role}" -v pw="${pw}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role', :'pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec
SQL
}

echo "[init_db] ensuring PG roles ${DB_MIGRATOR_USER} / ${DB_APP_USER}"
ensure_role "${DB_MIGRATOR_USER}" "${DB_MIGRATOR_PASSWORD}"
ensure_role "${DB_APP_USER}" "${DB_APP_PASSWORD}"

# -------- 3. Database (idempotent) --------
EXISTS=$(psql -d "${ADMIN_DB}" -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'")
if [ "${EXISTS}" != "1" ]; then
  echo "[init_db] creating database ${DB_NAME} owned by ${DB_MIGRATOR_USER}"
  psql -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_MIGRATOR_USER}\""
else
  echo "[init_db] database ${DB_NAME} already exists"
fi

# -------- 4. Python deps --------
if [ ! -d venv ]; then
  echo "[init_db] creating venv"
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo "[init_db] installing requirements"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# -------- 5. Alembic upgrade --------
echo "[init_db] running migrations"
alembic upgrade head

# -------- 6. Grant least-privilege to app role --------
echo "[init_db] granting DML privileges to ${DB_APP_USER}"
psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 <<SQL
GRANT CONNECT ON DATABASE "${DB_NAME}" TO "${DB_APP_USER}";
GRANT USAGE ON SCHEMA public TO "${DB_APP_USER}";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${DB_APP_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${DB_APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${DB_MIGRATOR_USER}" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${DB_APP_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${DB_MIGRATOR_USER}" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO "${DB_APP_USER}";
SQL

# -------- 7. Storage dir --------
mkdir -p "${STORAGE_DIR}"
echo "[init_db] storage dir ready: ${STORAGE_DIR}"

echo "[init_db] done. DB=${DB_NAME} migrator=${DB_MIGRATOR_USER} app=${DB_APP_USER}"
