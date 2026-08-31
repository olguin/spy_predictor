import { fileURLToPath } from "node:url";
import { runFoundation } from "./foundation";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const [, , area, command, ...args] = process.argv;

if (area !== "foundation" || command !== "run") {
  console.error("Usage: npm run foundation -- [--stop-after N]");
  process.exitCode = 2;
} else {
  const stopIndex = args.indexOf("--stop-after");
  const stopAfter =
    stopIndex >= 0 ? Number.parseInt(args[stopIndex + 1] ?? "", 10) : undefined;
  if (stopIndex >= 0 && (!Number.isInteger(stopAfter) || (stopAfter ?? 0) <= 0)) {
    throw new Error("--stop-after must be a positive integer");
  }
  const result = await runFoundation(repoRoot, stopAfter);
  console.log(JSON.stringify(result, null, 2));
}
