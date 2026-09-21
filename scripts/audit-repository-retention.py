"""Inventory retention; optionally delete only explicitly disposable local caches.

Never classifies research by age or absence of references. No dataset, report,
backup, environment, vendor tree or Git object is eligible for this deletion path.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def stats(path):
    files = [p for p in path.rglob('*') if p.is_file() and not p.is_symlink()] if path.is_dir() else [path]
    inodes = {}
    for p in files:
        s = p.stat()
        item = inodes.setdefault((s.st_dev, s.st_ino), {'bytes': s.st_size, 'blocks': s.st_blocks*512, 'links': s.st_nlink, 'inside': 0})
        item['inside'] += 1
    return {'files':len(files), 'logical_bytes':sum(p.stat().st_size for p in files),
            'unique_allocated_bytes':sum(i['blocks'] for i in inodes.values()),
            'estimated_reclaimable_bytes':sum(i['blocks'] for i in inodes.values() if i['links'] <= i['inside']),
            'qualification':'Allocated-block estimate excludes hardlinks outside this path; filesystem clones/compression may further change actual savings.'}


def candidates():
    paths = [ROOT/p for p in ('.uv-cache', '.npm-cache', '.pytest_cache')]
    for base in ('python/src', 'python/tests', 'scripts'):
        paths += list((ROOT/base).rglob('__pycache__'))
    return sorted(p for p in paths if p.exists() and not p.is_symlink())


def audit(delete=False):
    tracked = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    paths = candidates()
    eligible = []
    for path in paths:
        rel = str(path.relative_to(ROOT))
        if any(p == rel or p.startswith(rel+'/') for p in tracked if p):
            raise ValueError('Tracked artifact in cache candidate: '+rel)
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError('Unsafe cache path')
        eligible.append({'path':rel, 'classification':'DISPOSABLE_REGENERABLE_CACHE', 'reason':'Package download/index cache or generated Python/test cache; no unique research evidence.', **stats(path)})
    inventory = []
    for name in ('datasets','reports','backups','experiments','node_modules','python/.venv','.vendor-local','.git'):
        path = ROOT/name
        if path.exists():
            inventory.append({'path':name,'classification':'RETAIN', **stats(path)})
    backup = ROOT/'backups/cycle1-amendment-20260908T033825Z/verification.json'
    backup_status = None
    if backup.exists():
        value = json.loads(backup.read_text())
        backup_status = {k:value[k] for k in ('status','archive','archiveSha256','restoredFiles','restoredBytes','limitation')}
    record = {'schema_version':'repository-retention-audit-v1','audited_at':datetime.now(timezone.utc).isoformat(),
        'action':'DELETE_DISPOSABLE_CACHES_AFTER_CHECKS' if delete else 'PLAN_ONLY',
        'inventory':inventory, 'eligible':eligible, 'backup_status':backup_status,
        'preserved':[
            'All investment-research accepted runs, incomplete/failed attempts, source checks and code archives.',
            'M4 old-pipeline comparator outputs, frozen development/release cases and associated hashes.',
            'Legacy observations, issued theses, prospective evidence, protected historical cohorts and experiment failures.',
            'Raw and normalized datasets: future reuse/provenance not disproven by present code references.',
            'Backup archive and restored tree: independent durable backup is not verified.',
            'Installed node_modules, Python environment and vendor sources remain available for the current system.',
            'Git history is untouched; deleting ignored caches only reduces the local working directory.'],
        'future_deletion_queue':[],
        'future_review_only':['After M4 acceptance, reassess archived legacy working copies only after dependency/lineage audit and verified durable restoration. No automatic deletion is scheduled.'],
        'deleted':[]}
    if delete:
        for item, path in zip(eligible, paths):
            shutil.rmtree(path)
            record['deleted'].append(item['path'])
    record['estimated_reclaimable_bytes'] = sum(p['estimated_reclaimable_bytes'] for p in eligible)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete-disposable-caches',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain previous audits; choose a new output directory')
    record=audit(args.delete_disposable_caches)
    args.output.mkdir(parents=True)
    (args.output/'audit.json').write_text(json.dumps(record,indent=2)+'\n')
    lines=['# Repository retention audit','',f"Action: {record['action']}", '', '| Path | Size (MiB logical) | Disposition |','|---|---:|---|']
    for item in record['inventory']+record['eligible']:
        lines.append(f"| {item['path']} | {item['logical_bytes']/1024**2:.2f} | {'Deleted regenerable cache' if item['path'] in record['deleted'] else item['classification']} |")
    lines += ['',f"Estimated reclaimable allocation: {record['estimated_reclaimable_bytes']/1024**2:.2f} MiB; hardlinks outside each candidate are excluded. Actual filesystem savings may differ.",'','Preserved:',*['- '+s for s in record['preserved']], '', 'Future deletion queue: empty. No research artifact was proven permanently unnecessary.', '', *record['future_review_only']]
    (args.output/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'output':str(args.output),'deleted_paths':len(record['deleted']),'estimated_reclaimable_bytes':record['estimated_reclaimable_bytes']}))


if __name__=='__main__':
    main()
