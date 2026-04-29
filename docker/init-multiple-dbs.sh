#!/bin/bash
# Creates additional databases listed in POSTGRES_MULTIPLE_DATABASES
set -e
IFS=',' read -ra DBS <<< "$POSTGRES_MULTIPLE_DATABASES"
for db in "${DBS[@]}"; do
    db="$(echo -e "${db}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE "$db"' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
    EOSQL
    echo "Database '$db' ready."
done
