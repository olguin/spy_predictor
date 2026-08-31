BEGIN;

CREATE TABLE IF NOT EXISTS experiments (
  id text PRIMARY KEY,
  research_definition_id text,
  experiment_type text NOT NULL,
  config jsonb NOT NULL,
  code_commit text NOT NULL,
  code_identity_hash text,
  source_tree_hash text,
  dirty_tree boolean,
  dataset_version text NOT NULL,
  seed bigint NOT NULL,
  status text NOT NULL CHECK (status IN ('running', 'paused', 'completed', 'failed')),
  manifest jsonb NOT NULL,
  created_at timestamptz NOT NULL,
  completed_at timestamptz
);

ALTER TABLE experiments ADD COLUMN IF NOT EXISTS research_definition_id text;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS code_identity_hash text;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS source_tree_hash text;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS dirty_tree boolean;

CREATE TABLE IF NOT EXISTS snapshots (
  id text PRIMARY KEY,
  prediction_time timestamptz NOT NULL,
  data_cutoff timestamptz NOT NULL,
  schema_version text NOT NULL,
  source_manifest jsonb NOT NULL,
  snapshot_json jsonb NOT NULL,
  hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (data_cutoff <= prediction_time)
);

CREATE TABLE IF NOT EXISTS targets (
  snapshot_id text NOT NULL REFERENCES snapshots(id),
  target_definition text NOT NULL,
  start_time timestamptz NOT NULL,
  end_time timestamptz NOT NULL,
  start_price double precision NOT NULL,
  end_price double precision NOT NULL,
  return double precision NOT NULL,
  direction_label text NOT NULL CHECK (direction_label IN ('DOWN', 'NEUTRAL', 'UP')),
  realized_volatility double precision NOT NULL,
  absolute_return double precision NOT NULL,
  high_low_range double precision NOT NULL,
  target_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (snapshot_id, target_definition),
  CHECK (end_time > start_time)
);

ALTER TABLE targets
  ADD COLUMN IF NOT EXISTS target_json jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE OR REPLACE FUNCTION enforce_target_after_snapshot_cutoff()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM snapshots
    WHERE id = NEW.snapshot_id
      AND NEW.start_time > data_cutoff
  ) THEN
    RAISE EXCEPTION 'target start_time must be after snapshot data_cutoff';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS targets_after_snapshot_cutoff ON targets;
CREATE TRIGGER targets_after_snapshot_cutoff
BEFORE INSERT OR UPDATE ON targets
FOR EACH ROW EXECUTE FUNCTION enforce_target_after_snapshot_cutoff();

CREATE TABLE IF NOT EXISTS experiment_checkpoints (
  experiment_id text PRIMARY KEY REFERENCES experiments(id),
  checkpoint_version bigint NOT NULL,
  completed_items jsonb NOT NULL,
  state jsonb NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_observations (
  experiment_id text NOT NULL REFERENCES experiments(id),
  observation_date date NOT NULL,
  snapshot_id text NOT NULL REFERENCES snapshots(id),
  target_definition text NOT NULL,
  PRIMARY KEY (experiment_id, observation_date),
  FOREIGN KEY (snapshot_id, target_definition)
    REFERENCES targets(snapshot_id, target_definition)
);

CREATE TABLE IF NOT EXISTS agents (
  id text PRIMARY KEY,
  type text NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_genomes (
  id text PRIMARY KEY,
  agent_id text NOT NULL REFERENCES agents(id),
  generation integer NOT NULL,
  genome_json jsonb NOT NULL,
  genome_hash text NOT NULL,
  parent_ids jsonb NOT NULL,
  mutation_metadata jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id text PRIMARY KEY,
  snapshot_id text NOT NULL REFERENCES snapshots(id),
  genome_id text NOT NULL REFERENCES agent_genomes(id),
  model text NOT NULL,
  model_version text NOT NULL,
  input_hash text NOT NULL,
  output_json jsonb,
  output_hash text,
  latency_ms integer,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  cost_usd numeric(14, 8) NOT NULL DEFAULT 0,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (snapshot_id, genome_id, model, model_version, input_hash)
);

CREATE TABLE IF NOT EXISTS generations (
  experiment_id text NOT NULL REFERENCES experiments(id),
  generation_number integer NOT NULL,
  population jsonb NOT NULL,
  completed_candidates jsonb NOT NULL,
  state text NOT NULL,
  checkpoint jsonb NOT NULL,
  PRIMARY KEY (experiment_id, generation_number)
);

CREATE INDEX IF NOT EXISTS snapshots_prediction_time_idx
  ON snapshots (prediction_time);
CREATE INDEX IF NOT EXISTS agent_runs_snapshot_idx
  ON agent_runs (snapshot_id);
CREATE INDEX IF NOT EXISTS experiment_observations_snapshot_idx
  ON experiment_observations (snapshot_id);

COMMIT;
