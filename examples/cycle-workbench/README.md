# Local workbench input example

`synthetic-manifest.json` pins `synthetic-observations.json` by SHA256. Every
measurement is handcrafted and labelled SYNTHETIC; these are not real market
inputs. Default cutoff: `2026-08-31T23:59:59+00:00`; instrument: fictional DEMO.
The price/200-period-moving-average ratio is 0.88, illustrating cheap but adverse
timing. None of the sample values came from a source provider.

The adapter validates local manifests with
`schemas/cycle-workbench-inputs-v1.schema.json`. Load with
`load_workbench_inputs(path, as_of=cutoff, allowed_root=dedicated_directory)`.
The directory must contain the manifest and relative snapshot; paths cannot
escape it or reference Cycle 1 directories. No network is accessed.

For a real local source extract, declare its actual evidence tier and provide
publisher URLs, measurement/filing references, raw units, timestamps, instrument
identity, revision identifiers and the exact snapshot hash. `OBSERVED_AS_OF` means
the supplied first-seen timestamp supports availability at cutoff;
`RECONSTRUCTED_RESEARCH` remains explicitly reconstructed. Both still require
first_seen <= cutoff; the adapter does not infer historical first-seen provenance.
Validation proves internal integrity and admissibility of the supplied extract,
not publisher authenticity or independent verification that the extraction is
correct. The report preserves that limitation. A valid checksum alone does not
qualify financial truth or establish a forecast edge.

Version `illustrative-raw-metrics-v1` uses these fixed, uncalibrated transformations.
Each score is clipped to [-1,1]. They are independent implementation choices, not
Maru Cape's exact formulas. All seven components remain required for a complete
assessment; absent rows or withdrawn metrics produce missing components.

| Raw metric | Unit/convention | Illustrative score |
|---|---|---|
| growth_yoy_pct | Year-on-year activity growth, percentage points (3 means 3%) | x / 5 |
| credit_spread_bps | Declared credit spread in basis points | (300 - x) / 300 |
| bullish_survey_pct | Survey bullish share on a 0–100 scale | (x - 50) / 50 |
| realized_vol_pct | Annualized realized volatility in percentage points; source reference must identify return/window convention | (x - 20) / 40 |
| operating_margin_pct | Company operating margin, percentage points | (x - 10) / 20 |
| trailing_pe | Company positive trailing earnings multiple | (20 - x) / 20 |
| price_to_ma200_ratio | Price divided by its trailing 200-observation simple moving average; source reference must identify period/calendar and adjustment basis | (x - 1) / .15 |

These are deliberately narrow source-extract contracts. The adapter does not
calculate raw returns, moving averages, accounting statements, sector comparison,
or a comprehensive quality assessment. Fixed P/E 20 is an illustrative reference,
not a fair-value estimate. The spread series must be identified explicitly;
substituting a lending-policy-rate spread for a corporate spread is invalid.
Survey optimism is a measurement of response share, not a calibrated forecast or
an inference that euphoria is safe. Higher stress score means higher risk; higher
other scores mean more supportive readings under the illustrative rules.

Company margin and P/E metrics are rejected for ETF manifests. An ETF without a
separately implemented aggregate-fundamental adapter therefore has partial panels
and an incomplete instrument assessment. Growth/credit/survey/volatility rows
must use `US_EQUITY` market identity; remaining rows must match manifest instrument.

Dates require explicit timezones; date-only publications must be converted to a
conservative end-of-day instant before ingestion. A later revision cannot make
an old measurement fresh. Record a withdrawal with `status: WITHDRAWN` and
`value: null`, a new revision identity and its actual availability timestamps;
it blocks fallback to an older value for that component. Newer observed periods
supersede older periods. Duplicate vintage keys/revision identities are rejected.

`metadata.selected_input_hash` and assessment input values depend only on records
admissible at cutoff. Whole-file hashes in `loaded.audit` change if future records
are appended, and remain separate from the selected-input assessment identity.
Keep the audit object as source-file lineage when exporting a report bundle.
