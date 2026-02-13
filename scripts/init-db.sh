#!/bin/bash
# Initialize database with schema and seeds

set -e

echo "Initializing database..."

# Run migrations
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable extensions
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "vector";
    
    -- Run schema
    \i /docker-entrypoint-initdb.d/01-schema.sql
    
    -- Run seeds (if exist)
    \i /docker-entrypoint-initdb.d/02-seeds/seed_knowledge_base.sql
EOSQL

echo "Database initialized successfully!"