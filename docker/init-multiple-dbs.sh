#!/bin/sh
# Creates additional databases listed in POSTGRES_MULTIPLE_DATABASES.
set -eu

if [ -z "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
    exit 0
fi

echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' '\n' | while IFS= read -r db; do
    db="$(printf '%s' "$db" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [ -z "$db" ]; then
        continue
    fi

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE "$db"' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
    echo "Database '$db' ready."
done
