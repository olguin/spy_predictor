\set ON_ERROR_STOP on

DO $$
DECLARE
  table_count integer;
BEGIN
  SELECT count(*) INTO table_count
  FROM information_schema.tables
  WHERE table_schema = 'public'
    AND table_name IN (
      'experiments',
      'snapshots',
      'targets',
      'experiment_checkpoints',
      'experiment_observations',
      'agents',
      'agent_genomes',
      'agent_runs',
      'generations'
    );

  IF table_count <> 9 THEN
    RAISE EXCEPTION 'Expected 9 foundation tables, found %', table_count;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.triggers
    WHERE trigger_schema = 'public'
      AND trigger_name = 'targets_after_snapshot_cutoff'
  ) THEN
    RAISE EXCEPTION 'Point-in-time target trigger is missing';
  END IF;
END;
$$;

BEGIN;

INSERT INTO snapshots (
  id,
  prediction_time,
  data_cutoff,
  schema_version,
  source_manifest,
  snapshot_json,
  hash
) VALUES (
  'schema-verification-snapshot',
  '2024-01-03T14:29:00Z',
  '2024-01-03T14:29:00Z',
  'market-snapshot-v1',
  '[]'::jsonb,
  '{}'::jsonb,
  repeat('a', 64)
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO targets (
  snapshot_id,
  target_definition,
  start_time,
  end_time,
  start_price,
  end_price,
  return,
  direction_label,
  realized_volatility,
  absolute_return,
  high_low_range
) VALUES (
  'schema-verification-snapshot',
  'valid-target',
  '2024-01-03T14:31:00Z',
  '2024-01-03T15:00:00Z',
  470,
  471,
  0.002125,
  'UP',
  0.004,
  0.002125,
  0.005
)
ON CONFLICT DO NOTHING;

DO $$
BEGIN
  BEGIN
    INSERT INTO targets (
      snapshot_id,
      target_definition,
      start_time,
      end_time,
      start_price,
      end_price,
      return,
      direction_label,
      realized_volatility,
      absolute_return,
      high_low_range
    ) VALUES (
      'schema-verification-snapshot',
      'invalid-before-cutoff',
      '2024-01-03T14:28:00Z',
      '2024-01-03T15:00:00Z',
      470,
      471,
      0.002125,
      'UP',
      0.004,
      0.002125,
      0.005
    );
    RAISE EXCEPTION 'cutoff trigger did not reject invalid target';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = 'cutoff trigger did not reject invalid target' THEN
      RAISE;
    END IF;
    IF SQLERRM <> 'target start_time must be after snapshot data_cutoff' THEN
      RAISE;
    END IF;
  END;
END;
$$;

ROLLBACK;

SELECT 'foundation schema verified' AS result;
