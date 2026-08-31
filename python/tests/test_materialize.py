import json

import duckdb

from spy_predictor_quant.materialize import materialize


def test_materializes_ndjson_to_duckdb_and_parquet(tmp_path):
    source = tmp_path / "observations.ndjson"
    source.write_text(
        "\n".join(
            [
                json.dumps({"snapshotId": "s1", "return": 0.01}),
                json.dumps({"snapshotId": "s2", "return": -0.02}),
            ]
        )
        + "\n"
    )
    parquet = tmp_path / "observations.parquet"
    database = tmp_path / "experiment.duckdb"

    assert materialize(source, parquet, database) == 2
    assert parquet.exists()

    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute("select count(*) from observations").fetchone()[0] == 2
