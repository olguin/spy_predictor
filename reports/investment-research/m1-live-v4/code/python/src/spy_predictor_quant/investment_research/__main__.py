"""CLI for unpublished V1 research drafts. No issue/review/scoring command yet."""
import argparse
import json
from pathlib import Path

from .contracts import load_mandate
from .controller import Controller
from .broker import Broker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--mandate", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check-sources", help="Bounded source capability check with no model calls")
    check.add_argument("--mandate", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    for command in ("resume", "inspect"):
        commands.add_parser(command).add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    controller = Controller(args.output)
    if args.command in {"run", "check-sources"}:
        controller.create(load_mandate(args.mandate))
    if args.command == "check-sources":
        state = controller.store.load()
        broker = Broker(controller.store, state)
        results = {}
        for source in state["mandate"]["sources"]:
            result = broker.call("read_source", {"source_id": source["source_id"]})
            results[source["source_id"]] = {k: result[k] for k in ("status", "evidence_id", "reason", "error_type") if k in result}
        state["status"] = "CAPABILITY_CHECK"
        state["capabilities"]["source_results"] = results
        controller.store.save(state)
        print(json.dumps({"sources": results, "usage": state["usage"], "model_calls": 0}, indent=2))
        return 0 if all(r["status"] == "OK" for r in results.values()) else 1
    state = controller.store.load() if args.command == "inspect" else controller.run()
    print(json.dumps({"run_id": state["run_id"], "status": state["status"], "usage": state["usage"],
                      "usage_unknown": state["usage_unknown"], "stop_reason": state.get("stop_reason"),
                      "tasks": [{"task_id": t["task_id"], "role": t["role"], "status": t["status"]} for t in state["tasks"]],
                      "output": str(args.output.resolve())}, indent=2))
    return 0 if state["status"] == "DRAFT" or args.command == "inspect" else 1


if __name__ == "__main__":
    raise SystemExit(main())
