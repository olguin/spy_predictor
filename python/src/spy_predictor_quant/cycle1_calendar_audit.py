"""Inspect immutable calendar and CPI missingness metadata, never candidate scores."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from spy_predictor_quant.cycle1_feasibility import _verified
from spy_predictor_quant.market_archive import content_hash, file_sha256


def calendar_audit(repo_root: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    tracks = []
    for item in manifest['tracks']:
        if item['role'] != 'ACTUAL_ETF_VALIDATION':
            continue
        track = json.loads(_verified(repo_root, item['manifestPath'], item['manifestSha256']))
        artifacts = {a['kind']: a for a in track['normalizedArtifacts']}
        def metadata(kind):
            a = artifacts[kind]
            rows = [json.loads(line) for line in _verified(repo_root, a['path'], a['sha256']).splitlines()]
            if len(rows) != a['records']:
                raise ValueError('Artifact record count mismatch')
            return rows
        target_dates = {r['snapshotDate'][:7] for r in metadata('targets')}
        confirmation = track['resolvedPartitions']['confirmation']
        start, end = confirmation['start'][:7], confirmation['end'][:7]
        years = range(int(start[:4]), int(end[:4])+1)
        expected = [f'{year:04d}-{month:02d}' for year in years for month in range(1,13)
                    if start <= f'{year:04d}-{month:02d}' <= end]
        missing = [month for month in expected if month not in target_dates]
        macro = metadata('macro-vintages')
        endpoints = []
        for month in missing:
            observation = f'{int(month[:4])+1:04d}{month[4:]}-01'
            records = [r for r in macro if r['seriesId']=='CPIAUCSL' and r['observationDate']==observation]
            endpoints.append({'targetOriginMonth': month, 'cpiEndpointObservation': observation,
                              'vintageRecords':len(records),
                              'nonmissingVintageRecords':sum(not r['missing'] for r in records)})
        tracks.append({'instrument':track['instrument'], 'confirmationStart':confirmation['start'],
                       'confirmationEnd':confirmation['end'], 'fixedCalendarMonths':len(expected),
                       'archivedTargetMonths':sum(m in target_dates for m in expected),
                       'missingOriginMonths':missing, 'endpointCpiMetadata':endpoints})
    report = {'schemaVersion':'cycle1-calendar-audit-v1', 'datasetIdentityHash':manifest['datasetIdentityHash'],
              'manifestSha256':file_sha256(manifest_path), 'implementationSha256':file_sha256(Path(__file__)),
              'tracks':tracks, 'candidateMetricsComputed':False, 'confirmationMetricsOpened':False,
              'decision':'KEEP_FIXED_DATES_DO_NOT_COMPRESS_CALENDAR',
              'interpretation':'v4 CPI eligibility can remove primary excess labels although the common deflator cancels;v5 needs independent primary-label eligibility and full-path qualification'}
    return {**report, 'reportHash':content_hash(report)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path('.'))
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=calendar_audit(args.repo_root.resolve(),args.manifest)
    text=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output.exists() and args.output.read_text()!=text:
        raise ValueError('Refusing to overwrite a different audit')
    args.output.write_text(text)
    print(text,end='')


if __name__=='__main__':
    main()
