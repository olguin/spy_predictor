from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def materialize(input_path: Path, parquet_path: Path, database_path: Path) -> int:
    """Materialize newline-delimited experiment records as Parquet and DuckDB."""
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            "CREATE OR REPLACE TABLE observations AS "
            "SELECT * FROM read_json_auto(?, format = 'newline_delimited')",
            [str(input_path)],
        )
        escaped_path = str(parquet_path).replace("'", "''")
        connection.execute(
            f"COPY observations TO '{escaped_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        count = connection.execute("SELECT count(*) FROM observations").fetchone()[0]

    return int(count)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()

    count = materialize(args.input, args.parquet, args.database)
    print(json.dumps({"rows": count, "parquet": str(args.parquet)}))


if __name__ == "__main__":
    main()
