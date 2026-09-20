# Quantitative ETF pilot: diagnostic scorecard

**NOT QUALIFIED. No model promoted.** Latest revised historical prices are not certified point-in-time data. The named SPY/QQQ/XLK case study does not establish broad-stock performance.

Design: post-July-2025 data only, 63-session feature warmup, 126 training origins, five fixed quantitative candidates, no agent features. The 126-origin training window was declared before the panel was built to permit an engineering pilot; the 30-block, materiality and multiplicity gates were retained.

| Horizon | Candidate | Paired observations | Brier | Log loss | 80% interval coverage |
|---:|---|---:|---:|---:|---:|
| 5 | current_heuristic | 201 | 0.278294 | 0.750314 | 0.830846 |
| 5 | historical_frequency | 201 | 0.256034 | 0.705290 | 0.800995 |
| 5 | market_sector | 201 | 0.336431 | 1.119274 | 0.631841 |
| 5 | momentum | 201 | 0.306120 | 0.867188 | 0.706468 |
| 5 | regularized_quant | 201 | 0.332461 | 1.062286 | 0.616915 |
| 21 | current_heuristic | 153 | 0.276988 | 0.747803 | 0.960784 |
| 21 | historical_frequency | 153 | 0.237421 | 0.667800 | 0.836601 |
| 21 | market_sector | 153 | 0.201682 | 0.566923 | 0.581699 |
| 21 | momentum | 153 | 0.179045 | 0.544193 | 0.588235 |
| 21 | regularized_quant | 153 | 0.155472 | 0.490990 | 0.575163 |
| 63 | current_heuristic | 0 | — | — | — |
| 63 | historical_frequency | 0 | — | — | — |
| 63 | market_sector | 0 | — | — | — |
| 63 | momentum | 0 | — | — | — |
| 63 | regularized_quant | 0 | — | — | — |

There were no failed fitted folds. Five-session results have 67 evaluated market dates (6 effective blocks); 21-session results have 51 dates (1 block). The 63-session horizon has no eligible fold. All are below the preregistered 30-block threshold. More symbols do not replace independent dates.

The final period beginning 2026-09-16 is untouched. No claims about live LLM predictive value can be made from this quantitative-only diagnostic.

Source qualification and pre-outcome feasibility receipts are in `datasets/meta-research/quant-pilot-20260916`. The result and registration retain their hashes and audited restrictions.
