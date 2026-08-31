import { readFile } from "node:fs/promises";
import { join } from "node:path";
import Ajv2020, { type ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";
import type {
  ExperimentManifest,
  ExperimentState,
  MarketSnapshot,
  MarketTarget
} from "@spy-predictor/domain";

type ArtifactKind = "experiment-manifest" | "experiment-state" | "market-snapshot" | "market-target";

export class ArtifactSchemaValidator {
  private constructor(private readonly validators: Record<ArtifactKind, ValidateFunction>) {}

  static async fromRepository(repoRoot: string): Promise<ArtifactSchemaValidator> {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    addFormats(ajv);
    const kinds: ArtifactKind[] = [
      "experiment-manifest",
      "experiment-state",
      "market-snapshot",
      "market-target"
    ];
    const validators = {} as Record<ArtifactKind, ValidateFunction>;
    for (const kind of kinds) {
      const schema = JSON.parse(
        await readFile(join(repoRoot, "schemas", `${kind}.schema.json`), "utf8")
      );
      validators[kind] = ajv.compile(schema);
    }
    return new ArtifactSchemaValidator(validators);
  }

  private validate(kind: ArtifactKind, value: unknown): void {
    const validate = this.validators[kind];
    if (!validate(value)) {
      throw new Error(
        `${kind} schema validation failed: ${JSON.stringify(validate.errors)}`
      );
    }
  }

  manifest(value: ExperimentManifest): void { this.validate("experiment-manifest", value); }
  state(value: ExperimentState): void { this.validate("experiment-state", value); }
  snapshot(value: MarketSnapshot): void { this.validate("market-snapshot", value); }
  target(value: MarketTarget): void { this.validate("market-target", value); }
}
