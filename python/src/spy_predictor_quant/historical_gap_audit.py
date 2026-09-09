"""Verify bounded IBKR gap attempts without modifying data or running models."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from spy_predictor_quant import historical_development as dev

FOLDERS = ('gap-capture-20260909', 'gap-capture-variants-20260909',
           'gap-capture-venues-20260909', 'gap-capture-hourly-20260909')
TARGETS = ('2004-07-12', '2007-07-02')


def assess(payload, original):
    target = payload['targetSession']
    if target not in TARGETS:
        raise ValueError('Unregistered target session')
    if payload.get('status') == 'REQUEST_FAILED':
        return {'target': target, 'exchange': payload['exchange'],
                'status': 'REQUEST_FAILED', 'error': payload['error'], 'eligibleReplacement': False}
    if (payload['instrument'] != 'SPY' or payload['contract']['conId'] != 756733
            or payload['whatToShow'] != 'TRADES' or payload['useRTH'] != 1):
        raise ValueError('Wrong market-data contract')
    daily = payload['barSize'] == '1 day'
    if payload['barSize'] not in ('1 day', '1 hour'):
        raise ValueError('Unexpected bar size')
    dates = [(datetime.strptime(b['date'], '%Y%m%d').date().isoformat() if daily else
              datetime.fromtimestamp(int(b['date']), timezone.utc).date().isoformat()) for b in payload['bars']]
    if any(d > '2007-07-06' and target == '2007-07-02' or d > '2004-07-16' and target == '2004-07-12' for d in dates):
        raise ValueError('Capture extends beyond the bounded repair window')
    if daily and len(dates) != len(set(dates)):
        raise ValueError('Duplicate daily capture')
    overlap, close_mismatches, ohlc_mismatches = [], [], []
    if daily:
        for b, d in zip(payload['bars'], dates, strict=True):
            if b['date'] not in original:
                continue
            old = original[b['date']]
            overlap.append(d)
            differences = {k: {'captured': float(b[k]), 'archived': float(old[k])}
                           for k in ('open', 'high', 'low', 'close') if float(b[k]) != float(old[k])}
            if differences:
                ohlc_mismatches.append({'date': d, 'differences': differences})
            if 'close' in differences:
                close_mismatches.append({'date': d, **differences['close']})
    present = target in dates
    bracketed = any(d < target for d in overlap) and any(d > target for d in overlap)
    # No venue-specific series is silently spliced into the consolidated archive.
    eligible = daily and present and bracketed and not ohlc_mismatches
    return {'target': target, 'exchange': payload['contract']['exchange'],
            'barSize': payload['barSize'], 'status': 'CAPTURED', 'bars': len(dates),
            'targetPresent': present, 'overlapSessions': len(overlap),
            'bracketingOverlapPresent': bracketed, 'closeMismatches': close_mismatches,
            'ohlcMismatches': ohlc_mismatches, 'eligibleReplacement': eligible}


def audit(root):
    c, _ = dev.load_contract(root)
    first_root = root / 'datasets/historical-development/03608a029ae35517'
    first = json.loads((first_root / 'manifest.json').read_text())
    if first['datasetHash'] != '03608a029ae355172a880777f31ac53ede175000678bc7798392319da3b217ad':
        raise ValueError('First dataset identity changed')
    if dev.content_hash(first['identity']) != first['datasetHash'] or first['identity']['contractHash'] != dev.content_hash(c):
        raise ValueError('First dataset authority changed')
    dev.verify(root, first['artifacts'])
    dev.verify(root, first['identity']['sourceHashes'])
    dev.verify(root, first['identity']['codeHashes'])
    dev.verify(root, first['stoppedExperimentHashes'])
    first_report_root = root / 'reports/historical-development/5ffd4a7b879d3237'
    receipt = json.loads((first_report_root / 'verification.json').read_text())
    dev.verify(root, receipt['artifacts'])
    preserved = {str(p.relative_to(root)): dev.file_sha256(p)
                 for folder in (first_root, first_report_root) for p in folder.iterdir() if p.is_file()}
    preserved.update(first['stoppedExperimentHashes'])
    original_path = root / 'datasets/cycle1/raw/80a80d252c65abe9/ibkr/SPY/trades.json'
    original = {b['date']: b for b in json.loads(original_path.read_text())['bars']}
    attempts, capture_hashes = [], {}
    for name in FOLDERS:
        folder = root / 'datasets/historical-development' / name
        receipt_path = folder / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        hashes = {**receipt['captures'], str((folder/'plan.json').relative_to(root)): receipt['planSha256']}
        dev.verify(root, hashes)
        capture_hashes.update(hashes)
        capture_hashes[str(receipt_path.relative_to(root))] = dev.file_sha256(receipt_path)
        for path in receipt['captures']:
            payload = json.loads(dev.confined(root, path).read_text())
            attempts.append({'capturePath': path, **assess(payload, original)})
    recovered = {a['target'] for a in attempts if a['eligibleReplacement']}
    result = {'schemaVersion': 'historical-development-gap-audit-v1',
              'status': 'DATA_REPAIR_NOT_QUALIFIED' if recovered != set(TARGETS) else 'REPAIR_CANDIDATES_AVAILABLE',
              'attempts': attempts, 'requestedSessions': list(TARGETS),
              'qualifiedReplacementSessions': sorted(recovered),
              'gatewayAccessible': True, 'newDatasetBuilt': False, 'modelsRefitted': False,
              'finalEvaluationOpened': False, 'firstRunPreserved': True,
              'preservedHashes': preserved, 'captureHashes': capture_hashes,
              'auditCodeSha256': dev.file_sha256(Path(__file__)),
              'reason': 'A replacement requires its target session plus matching bracketing OHLC bars; venue-specific bars are not interchangeable with SMART.'}
    result['reportHash'] = dev.content_hash(result)
    folder = root / 'reports/historical-development' / f"gap-audit-{result['reportHash'][:16]}"
    dev.verify(root, preserved)
    dev.write_once(folder / 'report.json', dev.encode(result))
    print(json.dumps({'reportPath': str(folder/'report.json'), 'status': result['status'],
                      'requestsAudited': len(attempts), 'qualifiedReplacements': sorted(recovered)}, indent=2))
    return folder / 'report.json'


if __name__ == '__main__':
    audit(Path('.').resolve())
