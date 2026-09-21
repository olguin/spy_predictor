"""Bounded research, read-only monitoring, manual publication and linked reviews."""
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
    monitor = commands.add_parser('monitor')
    monitor.add_argument('--output', type=Path, required=True)
    monitor.add_argument('--port', type=int, default=8765)
    monitor.add_argument('--snapshot', action='store_true')
    publish = commands.add_parser('publish')
    publish.add_argument('--output', type=Path, required=True)
    publish.add_argument('--ledger', type=Path, required=True)
    publish.add_argument('--review-of')
    for name in ('feedback', 'review', 'observe'):
        sub = commands.add_parser(name)
        sub.add_argument('--ledger', type=Path, required=True)
        sub.add_argument('--publication', required=True)
        sub.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    if args.command in {'feedback', 'review', 'observe'}:
        from .publication import feedback, review, read_publication
        value = json.loads(args.input.read_text())
        if args.command == 'observe':
            from .observations import observe
            from .store import Store
            publication = read_publication(args.ledger, args.publication)
            result = observe(publication['observation_contract'], value['symbol'], value['horizon'], value['instrument'], value['benchmarks'])
            result['publication_id'] = args.publication
            result['observation_id'] = Store(args.ledger).put('observations', result)
        else:
            result = (feedback if args.command == 'feedback' else review)(args.ledger, args.publication, value)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == 'monitor':
        from .monitor import serve, project
        from .store import Store
        if args.snapshot:
            print(json.dumps(project(Store(args.output)), indent=2))
        else:
            serve(args.output, args.port)
        return 0
    controller = Controller(args.output)
    if args.command == 'publish':
        from .publication import publish
        record = publish(controller.store, args.ledger, parent_publication_id=args.review_of)
        print(json.dumps({'publication_id': record['publication_id'], 'published_at': record['published_at'],
                          'bundle': str(args.ledger / 'publications' / record['publication_id'])}, indent=2))
        return 0
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
        from spy_predictor_quant.market_archive import utc_now
        state['completed_at'] = utc_now()
        for task in state['tasks']:
            task.update(status='OMITTED_CAPABILITY_CHECK', completed_at=state['completed_at'])
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
