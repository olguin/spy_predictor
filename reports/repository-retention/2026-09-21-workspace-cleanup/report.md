# Repository retention audit

Action: DELETE_DISPOSABLE_CACHES_AFTER_CHECKS

| Path | Size (MiB logical) | Disposition |
|---|---:|---|
| datasets | 2216.01 | RETAIN |
| reports | 374.04 | RETAIN |
| backups | 313.48 | RETAIN |
| experiments | 0.06 | RETAIN |
| node_modules | 188.20 | RETAIN |
| python/.venv | 439.96 | RETAIN |
| .vendor-local | 33.95 | RETAIN |
| .git | 29.45 | RETAIN |
| python/src/spy_predictor_quant/__pycache__ | 0.22 | Deleted regenerable cache |
| python/src/spy_predictor_quant/investment_research/__pycache__ | 0.22 | Deleted regenerable cache |
| python/tests/__pycache__ | 0.25 | Deleted regenerable cache |

Estimated reclaimable allocation: 0.76 MiB; hardlinks outside each candidate are excluded. Actual filesystem savings may differ.

Preserved:
- All investment-research accepted runs, incomplete/failed attempts, source checks and code archives.
- M4 old-pipeline comparator outputs, frozen development/release cases and associated hashes.
- Legacy observations, issued theses, prospective evidence, protected historical cohorts and experiment failures.
- Raw and normalized datasets: future reuse/provenance not disproven by present code references.
- Backup archive and restored tree: independent durable backup is not verified.
- Installed node_modules, Python environment and vendor sources remain available for the current system.
- Git history is untouched; deleting ignored caches only reduces the local working directory.

Future deletion queue: empty. No research artifact was proven permanently unnecessary.

After M4 acceptance, reassess archived legacy working copies only after dependency/lineage audit and verified durable restoration. No automatic deletion is scheduled.
