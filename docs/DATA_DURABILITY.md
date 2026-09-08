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

## Immutable archive backup and restore verification

Database backups do not contain the Git-ignored raw research data. A complete
backup must also preserve `datasets/`, required experiment/report artifacts,
manual source snapshots, and the corresponding code/config/schema revisions.
Use private encrypted storage consistent with each source's retention rules;
never add credentials or restricted raw data to Git or a public backup.

Verify restoration into a separate directory: check every artifact against its
manifest hash and reproduce the corresponding approved offline run. For the
suspended Cycle 1 v4 archive, reproduce `cycle1:preflight` and its blocked
findings; do not mistake the intentionally failing corrected dataset build for
archive corruption. A hash match proves preserved bytes, not scientific validity.

Record the backup date, source identities, restore destination, verified hashes,
and verification outcome. Do not overwrite the only local archive to test a
restore. No raw-archive backup or restore is claimed completed by this repair.

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
