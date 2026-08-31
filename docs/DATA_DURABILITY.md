# Data durability and local PostgreSQL operations

PostgreSQL is the source of truth for experiment manifests, checkpoints,
snapshot metadata, and target metadata whenever `DATABASE_URL` is configured.
Parquet, DuckDB, NDJSON, and report files remain immutable filesystem artifacts.

## Backup

Create a logical backup before schema changes or before importing valuable data:

```bash
mkdir -p backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > backups/spy_predictor.dump
```

The `backups/` directory is local-only and must be copied to durable encrypted
storage when it contains valuable data. Verify a backup by restoring it into a
separate database; a successful `pg_dump` command alone is not a restore test.

## Non-destructive stop and restart

`npm run db:down` removes the container but preserves the named
`postgres-data` volume. `npm run db:up` reattaches that volume.

## Destructive reset

The following operation permanently deletes the local database volume and is
intentionally not exposed as an npm script:

```bash
docker compose down --volumes
```

Run it only after identifying the `spy-predictor_postgres-data` volume and
confirming that no needed experiment metadata exists solely in it. Then run
`npm run db:up && npm run check:db` to recreate and verify the schema.
