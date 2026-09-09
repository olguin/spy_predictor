# Successor mathematical repairs and remaining release work

Current status: these repairs were included in the registered successor, which
subsequently stopped for compute budget. See [profile/stop](CYCLE1_SUCCESSOR_PROFILE.md).
The candidate-stage description below preserves the repair evidence and rationale.

2026-09-08. The two specific equation blockers are repaired in the **unfrozen
candidate**. Run `npm run cycle1:repair-check` to reproduce the
[repair report](../reports/cycle1-successor-repair-eed1ed473b64a721/report.json),
status `SPECIFIC_BLOCKERS_REPAIRED_NOT_REGISTERED`. Implementation:
[laws](../python/src/spy_predictor_quant/cycle1_successor_laws.py) and
[equation engine](../python/src/spy_predictor_quant/cycle1_successor_equations.py)
with explicit `repaired=True`. The default legacy branch still reproduces the
old failure; it is retained for comparison, not proposed for release.

The original v1 stop, earlier v2 proposal and failure report remain historical
records. This is an explicit pre-output equation amendment, not a silent claim
that the original nulls were valid. No scenario is removed or relabeled, and
numeric acceptance gates, model/feature formulas, design-effect amplitudes,
calendars and replication/compute budgets are unchanged. No random stream or
redesign registration has been opened.

## 1. Positive prices with an announced cash dividend

Let `B = previous_raw_close / split`, `q = 0.0025` on a distribution date, and
`o,i` be proposed overnight/intraday log increments. The old construction
`B*exp(o)-q*B` failed when `o < log(q)`.

The repair reserves the announced cash before applying the stock-price shock:

```text
D = q B                         known at the previous close
P_open = (1-q) B exp(o)          positive
P_close = (1-q) B exp(o+i)       positive
L = log((P_close + D)/B) = log((1-q) exp(o+i) + q)
delta = L - (o+i)
```

For `B>0` and `0<=q<1`, both prices are positive for every finite real shock.
The dividend amount and entitlement remain fixed before the ex-date open.
Entitled dividends are reinvested at the close using the existing shareholder
accounting. Splits continue to use post-split per-share units.

Reserve accounting changes that day's holder return by `delta`. At that close,
subtract `delta/K` from each of the `K` remaining overnight/intraday increments
in the month. Distributions occur on the first session, so later sessions exist.
The adjustment is known after the ex-date close and uses no later observed input.
Thus the sum of **holder** daily log returns still equals the original monthly
excess return plus observable cash. Both the Student monthly endpoint law and
the intended signal amplitudes survive this repair. The daily path law changes
explicitly; it is no longer an unmodified Gaussian bridge on distribution months.

The former failing overnight normal of -2000 now produces positive raw prices
and annual excess returns of 0.04 for SPY and 0.048 for QQQ in the zero-monthly-
innovation fixture. Tests also verify the wealth identity and compensation under
several large overnight/intraday moves, and monthly accounting in all ten cases.

Floating-point exponentials cannot represent all mathematically positive real
prices. Underflow, overflow or other unrepresentable paths invalidate computation;
they are never clipped, discarded or replaced with another draw. This numerical
limit is distinct from the old mathematically negative-price equation.

## 2. Global annual nulls with persistent daily volatility

Keep `h_next = phi*h + omega*eta` as the persistent daily bridge scale state.
For the required null scenarios only, use a fresh independent monthly scale:

```text
tau = omega / sqrt(1-phi^2)
return_scale_next = (0.15/sqrt(12)) exp(tau * eta_next)
bridge_scale_next = (0.15/sqrt(12)) exp(h_current)
monthly_excess_next = 0.04/12 + return_scale_next * standardized_Student_next
                      + independent_crash_next
```

The monthly log-scale marginal matches the old stationary Gaussian log-scale
variance; **its serial dependence is deliberately removed**. Persistent
macro/predictor processes and daily volatility remain. This is the substantive
null-law correction, not a claim that the previous monthly volatility clustering
has been preserved. The non-null location/scale/break scenarios retain their
original persistent monthly-scale and actual-feature feedback equations.

For no-skill, persistent-heavy-tail, rare-downside and missingness scenarios,
future monthly excess returns are iid and independent of the origin information
set `F_t`. Cash cancels exactly from each monthly excess increment and the daily
bridge/compensation does not change its endpoint. Consequently:

```text
Law(sum(next 12 monthly excess returns) | F_t) = 12-fold convolution of Law(r)
```

Every causal feature and baseline is measurable in `F_t`, so conditioning on any
of them leaves this full annual law unchanged. Overlapping annual labels remain
overlapping sums on the same daily path; they are not treated as independent.
The rare crash and missing-origin uniforms must be independent future innovations.
No downside/policy null is inferred from the primary annual-return null.

## 3. A nontrivial, observable strong-baseline partial null

The previous one-step mean depended on position/direction summaries whose future
evolution could depend on omitted history. Zero extra loading did not solve that.
The amended control uses a two-state regime `R in {-1,+1}`:

```text
P(R_next = R) = (1+rho)/2         rho = original predictorPersistence
P(R_next = -R) = (1-rho)/2
SPY excess_next = 0.04/12 + (0.08/12)*sign(actual_valuation_t) + iid_noise_next
```

All nine features are still computed from actual generated prices and vintage
records with the existing formulas and expanding normalization. To make the
regime provably observable through that valuation feature, this **synthetic
control only** supplies a constructed CPI release at each month-end close:

- Revise last month's CPI to that month's SPY total-return level. All old SPY
  real month-end levels are then exactly 1.
- Set current CPI to `current_SPY_TRI * exp(-marker_t)`, with
  `marker_t = valuation_economic_sign * R_t * 0.0001 * (month_ordinal+1)`.
- Keep earlier issued feature rows unchanged. The vintage revision affects only
  calculations at or after its release, using normal inclusive cutoff admission.

In the 60-month real-price trend window, 59 log levels are zero and the last is
`marker_t`. The Theil-Sen median slope, median intercept and residual MAD are
zero. Raw valuation is therefore `marker_t / madFloor`. Each new marker has a
strictly larger absolute magnitude, so it is a new maximum or minimum among
previous raw valuations. At normalization history length `n`:

```text
actual_valuation_t = R_t * (n-1)/n
sign(actual_valuation_t) = R_t
```

The equation engine decodes the signal from the computed feature and checks it
against the construction; it never inserts a latent surrogate feature vector.
The partial-null macro missingness is disabled so that, after deterministic
warmup, future loading availability cannot depend on extra historical information.
The required missingness null remains a separate unchanged acceptance case.

Let `B_t=(valuation_t,direction_t)` and `S_t=stress_t`. Since `B_t` reveals `R_t`,
and the joint next-regime/return law depends only on `R_t`, induction gives:

```text
Law(Y_t | B_t,S_t) = Law(Y_t | B_t),  Y_t = sum(next 12 monthly excess returns)
```

More explicitly, if `P` is the two-state transition matrix and
`D(u)=diag(exp(i*u*(0.08/12)*R))`, the annual characteristic function is
`exp(i*u*0.04) * noise_cf(u)^12 * e_R' * (D(u)*P)^12 * 1`.
It depends on current `R`, not extra features. The exact rational marked-kernel
check verifies the discrete regime-sum law; the continuous iid noise convolution
is common to both feature states. The engine tests additionally establish the
mapping from real computed features to `R` and couple two actual daily histories
with different stress scores but the same future annual excess return.

This baseline really is predictive: its conditional annual mean is
`0.04 + (0.08/12)*R*sum(j=0..11,rho^j)`, different in the two regimes.
Both regimes are exercised in the long deterministic fixture. No claim is made
that a fitted finite-sample baseline perfectly estimates this distribution.

The CPI construction is deliberately artificial: it proves observability in a
negative-control experiment. It is not realistic inflation dynamics, historical
CPI, or an input for the secondary Maru Cape workbench. The proof covers the SPY
primary claims; QQQ retains its own generated features and correlated shocks,
and receives no separate null or performance qualification from this proof.

## 4. What this resolves, and what remains

Resolved: mathematical price positivity, annual global-null construction, and an
actual-feature strong-baseline annual null. The repair report binds code,
equations, the original proposal and reproducible deterministic fixtures.

Integration update, 2026-09-09: the repaired configuration/schema and full
deterministic evaluator adapter now exist; see [integration status](CYCLE1_SUCCESSOR_INTEGRATION.md).
The remaining sampler/registration/profile gates below are not released.

Release checklist (configuration and deterministic integration now implemented):

1. Encode these explicit amendments in the final simulation schema and linked
   authorities; register the single successor atomically.
2. Enforce independent sampler substreams, including separate SPY/QQQ monthly
   Student innovations and the baseline-regime uniform. No sampler is opened by
   this repair. Do not reuse a daily normal as an independent monthly innovation.
3. Connect full paths to the complete shared evaluator, verify all conditional
   branches, and profile only the registered development run.
4. Run the gated locked audit at the existing 20,000-replication budget, keeping
   the 0.10 false-qualification upper bound and 0.80 design-power lower bound.

An information null and equal losses from fitted forecasting methods are different
questions. Estimation and misspecification remain reasons to run the full audit;
the literature likewise treats forecast-method evaluation as accounting for
estimation uncertainty ([Giacomini and White, 2006](https://escholarship.org/uc/item/5jk0j5jh)).
These proofs do not establish market predictive value or a probability of
investment success. The secondary notebooks remain on their separate validated
manifest workflow; their synthetic sample and pending current-source work stand.
