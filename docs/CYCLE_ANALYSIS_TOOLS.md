# Exploratory cycle-analysis tools

`spy_predictor_quant.cycle_analysis_tools` contains reusable, cutoff-safe
diagnostics inspired by public cycle concepts. They are an independent
formalization, not Maru Cape's proprietary or exact method. They do not modify
the frozen `CYCLE-ASYMMETRY-001` configuration, models, candidate count, or
promotion rules.

## Public API

- `compute_trailing_structural_trend`: fits an exact Theil-Sen log trend for
  every explicitly supplied trailing window, averages those available trend
  estimates, calculates `log(price) - average_trend`, and robustly scales the
  causal deviation history. A result is unavailable until every requested
  trend window and the scaling warm-up are available.
- `compute_trailing_robust_scores`: exposes causal median/MAD normalization for
  any already cutoff-safe series, preserving unavailable rows without filling
  them from future observations.
- `decompose_embedded_expectations`: provides either the log identity
  `log(P) = log(F_proxy) + residual` or level identity `P = F_proxy + residual`.
  `F_proxy` is caller supplied. The residual is not identified sentiment and
  can contain model error, omitted risk, and other effects.
- `evaluate_expectations_surprise`: compares an actual result with an explicit
  embedded-expectation proxy; it does not infer expectations from price.
- `calculate_cycle_architecture`: preserves the separation
  `Macro -> CycleLocation`, `Fundamental -> AssetQuality/Valuation`,
  `Technical -> Timing`, and `Psychology/Credit -> RiskTemperature`.
  The underlying `calculate_dimension` requires positive weights and separate
  `economic_sign` values of exactly `-1` or `1`.
- `calculate_credit_amplifier`: distinguishes credit ease, risk tolerance,
  current stress, and latent boom-created fragility from six standardized
  caller-provided proxies. The outputs are descriptive, not causal estimates.
- `calculate_cycle_top_score`: requires a complete, explicit weight and sign
  configuration. No default weights or silent missing values are allowed.
- `classify_exploratory_states`: assigns `CRISIS`, `EARLY_RECOVERY`, `NORMAL`,
  `GREED`, `EUPHORIA`, or `CORRECTION` using transparent ordered rules.
- `filter_latent_states`: performs fixed-parameter forward filtering only.
  It does not fit an HMM, look backward from future data, or participate in the
  frozen Cycle 1 run.
- `diagnose_nested_cycles`: overlays an undervalued/normal/overvalued
  structural zone with rally/correction/recovery phases. A correction is not
  asserted to be the end of the megacycle.
- `map_state_probabilities_to_exposure`: maps the six state probabilities to a
  bounded, probability-weighted aggressive/defensive research budget, with an
  optional confidence fallback and rate limit. It is not an order generator.

## Data contract

Inputs described as normalized or standardized must be produced with trailing
or expanding history known at the cutoff. Revised macro data must be selected
from the vintage available at that cutoff before calling these tools. The
functions reject non-finite values and ambiguous signs, but they cannot detect
whether a caller supplied revised or future information.
