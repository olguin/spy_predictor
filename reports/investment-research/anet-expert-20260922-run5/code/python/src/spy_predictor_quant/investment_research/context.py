"""Lossless-number context projections; full source artifacts remain inspectable."""
from copy import deepcopy


def compact(value, *, catalog_only=False):
    result = {k: deepcopy(v) for k, v in value.items() if k not in {'excerpt', 'data'}}
    # Integrity/locator details are verified by the store and remain inspectable;
    # repeating hashes, raw-document IDs and long API query URLs is not research.
    for key in ('content_sha256', 'document_id', 'parent_evidence_id', 'url', 'locator'):
        result.pop(key, None)
    data = value.get('data')
    if catalog_only:
        result = {k: result[k] for k in ('kind', 'source_id', 'adapter', 'symbols', 'published_at', 'captured_at', 'retrieved_at', 'trust') if k in result}
        result['context_projection'] = 'Catalog only: inspect evidence for source content; metadata does not support unseen factual claims.'
        return result
    if isinstance(data, dict):
        data = deepcopy(data)
        adapter = value.get('adapter')
        if adapter == 'sec_companyfacts':
            data.pop('filings', None)  # matching submissions are separate evidence
            for metric in data.get('metrics', {}).values():
                for key in ('label', 'frame', 'fiscal_year', 'fiscal_period'):
                    metric.pop(key, None)  # explicit start/end and accession remain
        elif adapter == 'alpaca_daily':
            for key in ('weekly_view', 'reference_scenarios', 'support_resistance_candidates', 'greed_proxy'):
                data.pop(key, None)
        elif adapter == 'etf_holdings':
            data['holdings'] = [{k: row[k] for k in ('ticker', 'weight_pct')} for row in data['holdings']]
        result['data'] = data
        result['context_projection'] = 'Normalized fields only; some descriptive fields omitted. Numeric values and original JSON-pointer positions retained. Inspect evidence for full details.'
    elif data is not None:
        result['data'] = data
    if data is None and 'excerpt' in value:
        result['excerpt'] = value['excerpt'][:1600]
        result['context_excerpt_truncated'] = len(value['excerpt']) > 1600
    return result
