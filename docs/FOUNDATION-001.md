# FOUNDATION-001

## Scientific boundary

Snapshot construction receives a `PointInTimeMarketDataProvider` whose cutoff is
the prediction instant. Both requested query bounds and every returned record's
`firstSeenAt` are checked in code. Target generation uses a separate, explicitly
future-facing path and its output is never embedded in `MarketSnapshot`.

Snapshot identity is the SHA-256 hash of canonical content. Volatile persistence
metadata such as creation time is excluded, so rebuilding the same date from the
same dataset produces the same snapshot ID and hash.

## Current baseline

The executable vertical slice fits a Laplace-smoothed historical class-frequency
forecast on the training partition. It reports multiclass Brier score, log loss,
and accuracy on validation and test partitions. This is infrastructure proof,
not a claim of predictive value.

## Persistence

Every completed date is atomically checkpointed. Reruns load the existing
manifest and observations, reject any immutable manifest mismatch, and reuse work.
Research-definition identity is configuration-derived; concrete run identity
also includes dataset and code identity. Dirty work receives a deterministic
source-tree hash, while clean work records both that hash and its Git commit.
The final flat analytical artifact is stored in both Parquet and DuckDB.

PostgreSQL migration `001_foundation.sql` defines durable metadata tables. When
`DATABASE_URL` is set, PostgreSQL is the metadata/checkpoint truth and the
filesystem retains large analytical artifacts. A Docker Compose integration
check proves database-backed resume. JSON Schema validation runs before
persisting manifests, state, snapshots, and targets.

## Exit criteria

- A repeated snapshot build has an identical hash.
- Queries after cutoff and records first seen after cutoff fail.
- Prediction timestamps honor New York daylight-saving rules.
- Future targets are stored separately from snapshots.
- Splits are chronological and apply configured purge/embargo gaps.
- An interrupted run resumes without regenerating completed observations.
- One command produces evaluation JSON, Parquet, and DuckDB artifacts.
