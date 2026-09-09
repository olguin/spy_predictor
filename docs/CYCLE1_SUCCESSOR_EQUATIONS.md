# Executable successor equation specification

**Current candidate:** the [subsequent repairs](CYCLE1_SUCCESSOR_REPAIRS.md)
implement positive reserve/compensation accounting and prove the amended annual
nulls. Run `npm run cycle1:repair-check`. Final registration and the full-procedure
audit remain pending. The equations and readiness failure described below are
the retained first candidate, executed by the engine's default legacy branch.

2026-09-08. The candidate equations are implemented in
[cycle1_successor_equations.py](../python/src/spy_predictor_quant/cycle1_successor_equations.py).
They operate on explicit supplied innovations and generate daily raw prices,
macro vintages, computed features, excess-return labels and execution returns.
This completes the deterministic equation implementation; it does not freeze a
random simulation, prove its annual null, or qualify the experiment.

**Historical first-candidate readiness: `NOT_READY_TO_FREEZE`.** The supplied-innovation engine
reproduces a positive-price support failure. See the
[readiness report](../reports/cycle1-successor-readiness-3b7d5d92f7457de2/report.json).
Run `npm run cycle1:successor-readiness` (expected exit 2). This review opens no
random stream and consumes no redesign slot. The earlier equation fixture remains
valid as an arithmetic example, not evidence that the generator is valid on its
declared innovation support.

```bash
npm run cycle1:equation-check
```

This runs a bounded zero-innovation fixture and publishes a deterministic
[report](../reports/cycle1-equation-fixture-13112c15b99cb21f/report.json).
The status is `EQUATIONS_EXECUTED_NOT_POWER_QUALIFIED`. No development or validation
random stream is called. The report binds the equation constants, scenario,
configuration, implementation files, daily paths and derived target values.

## Return and daily-price equations

At completed origin month `t`, compute the nine v5 features from each instrument's
own history. Normalize using only the expanding history already processed.
The chosen scenario selects zero, the cycle mean, stress, or the position/direction
mean as `signal_t`. Unavailable warmup or missing-origin inputs stay unavailable;
their skill loading is zero, rather than presenting a zero-valued feature vector.

The SPY monthly excess-log-return equations are:

```text
mu_t = 0.04/12 + annualLocationAmplitude/12 * signal_t * breakMultiplier_t
sigma_t = 0.15/sqrt(12) * exp(h_t + logScaleLoading * signal_t)
eps = suppliedStudentT / sqrt(df/(df-2))
excess[t+1] = mu_t + sigma_t*eps + crash[t+1]
h[t+1] = volatilityPersistence*h[t] + volatilityInnovationSd*suppliedNormal[t+1]
```

The break is evaluated at the origin month, preserving the inherited convention.
QQQ uses its own computed signal, a 1.2 mean/volatility multiplier and
`0.8*SPYshock + 0.6*independentShock`; the crash is shared outside that multiplier.
The original scenario amplitudes and qualification gates are unchanged.

Add the strictly observable GS3M monthly cash log accrual to construct nominal
equity total returns. This preserves the effects on **excess** returns instead of
accidentally changing them when cash is subtracted later.

For `N` actual XNYS sessions, split each monthly total into overnight/intraday
increments with weights `0.25/N` and `0.75/N`. For supplied Gaussian deviations
`a_j=sigma*sqrt(w_j)*z_j`, use:

```text
increment_j = w_j*monthlyTotal + a_j - w_j*sum(a)
```

The deviations sum to zero. A final floating-point residue correction preserves
the monthly Student-t total; summing independent daily t draws would change that
law. The shared crash is applied to one specified overnight interval. Innovations
are not passed to the feature calculation, and later innovations cannot alter
completed paths. Actual schedule timestamps include early closes. January 1990
uses a successor calendar helper that handles the first calendar boundary.

## Macro, releases and revisions

Four Gaussian AR(1) states use the scenario persistence. CPI/IP levels evolve
positively with 2% annual log drift and monthly state loadings 0.002/0.005.
Treasury yield is `3*exp(0.15*z_rate)` percent and prime is that yield plus
`2*exp(0.15*z_spread)` percent. This is a synthetic lending-rate proxy.

Each monthly observation is first released 15 calendar days after month end and
revised after 45 days, at 13:30 UTC. First/revised values multiply the latent
level by `exp(0.001*z)` / `exp(0.0005*z)`. Supplied uniform values encode 1% first
release missingness and 0.5% revision tombstones. These are explicit synthetic
design choices, not claims about actual publication schedules or revision rates.

The successor selector admits feature releases at the cutoff inclusively and
cash releases strictly before each holding start. Missing revisions remove the
previous value for the same observation. Cash may use an earlier nonmissing
observation under the specified latest-admissible rule. Every monthly cash
boundary is required; annual accrual cannot bridge an omitted month.

## Corporate actions, targets and execution

The candidate uses a 2-for-1 split in January of calendar years divisible by ten
and a 0.25% distribution on the first session of March/June/September/December.
Dividend amounts are per post-split share and known before the ex-date open.
With previous raw close `P`, split factor `k` and distribution `D`:

```text
rawOpen = (P/k)*exp(overnightIncrement) - D
rawClose = (P/k)*exp(overnightIncrement + intradayIncrement) - D
TRI_new / TRI_old = k*(rawClose+D)/P
```

Nonpositive prices or inconsistent action units are invalid; such supplied paths
must not be silently clipped, discarded or redrawn to obtain favorable evidence.

Execution uses separate shareholder accounting. A buyer at an ex-date open does
not receive that day's dividend. An existing holder selling at the next ex-date
open retains the dividend entitlement. Intermediate entitled cash is reinvested
at the close; splits adjust held shares before the per-share distribution.
This avoids using a generic close-TRI ratio as an open-to-open return.

Annual labels use 13 consecutive month-end boundaries and the complete daily
session inventory. They report nominal equity minus rolled cash; CPI is not
required for the cancelled excess label. Drawdown includes the starting close.
Policy equity and cash returns use the actual next-open interval. All returned
evidence is synthetic and carries `realDataApproval: false`.

## Feature parity and remaining scientific work

[SuccessorFeatureState](../python/src/spy_predictor_quant/cycle1_successor_features.py)
reuses the nine existing raw formulas and expanding-midrank normalization, with
explicit successor vintage admission. It requires chronological unchanged market
history, every daily session and every monthly update. Complete-vintage fixtures
match the old raw/normalized features and dimension scores exactly. An exact-lag
withdrawal prevents the old spread value from reappearing. A long deterministic
fixture proves actual computed SPY and QQQ features drive their next-month means.

Still required before any random simulation release:

- Repair the dividend/return support incompatibility described below.
- Prove the **annual** null for this actual path/feature process, including the
  strong-baseline case. The finite-state examples are not a proof for these
  continuous equations, and zero one-step loading is insufficient.
- Reconcile/freeze the final equation specification and authority links as the
  single successor; register it before any development draw.
- Profile and audit the full statistical procedure on the permitted development
  streams, then release locked validation only if its gates pass.

No statistical power, false-positive rate, current investment recommendation or
real-data qualification follows from the deterministic equation fixtures.

### Scientific findings from the readiness review

On an ex-date the proposed equation is `raw_open = base * (exp(o) - q)`,
where `q = 0.0025` is known before the open. It becomes negative whenever
`o < log(q)`, approximately -5.9915. The Gaussian bridge has unbounded support.
A supplied first-March-session overnight normal of -2000 reproduces the strict
failure; neighboring innovations do too. This establishes nonzero probability
under the proposed support, without estimating how often it occurs. Rejecting
such paths and replacing them would change the specified probability law.

The next equation revision must jointly specify dividends and positive prices.
It cannot simultaneously preserve a strictly positive predetermined dividend,
arbitrarily small gross total wealth, and a positive residual share price.
Choose and document the changed economic assumption and corresponding return law
before freezing; silently clipping prices or dividends is not a repair.

For the no-loading, no-crash case, let `g` be log volatility used in the last
completed month, `phi` its persistence, and `omega` its innovation scale. The
engine updates volatility after that month. Under independent proposed shocks:

```text
Var(next 12 months of SPY excess log returns | g)
  = 0.15^2/12 * sum(j=1..12,
      exp(2*phi^j*g + 2*omega^2*sum(i=0..j-1, phi^(2*i))))
```

The executable review evaluates this expression at three supplied states. It
increases with `g` when persistence is positive, despite zero direct skill loading.
Daily bridge variation also measures the same latent scale. This identifies an
information path requiring analysis; **latent-state dependence alone does not
prove extra predictability conditional on the actual normalized features**.
The annual conditional null, especially relative to the position/direction
baseline, remains unproven. The finite-state null examples do not discharge that
obligation. No false-positive rate or model-performance conclusion was calculated.

Successor registration and full-procedure runtime profiling remain pending these
scientific prerequisites. The earlier 1,801-second projection belongs only to
the stopped v1 available branch and does not qualify this successor.

Verification: compilation, 15 TypeScript tests and 245 Python tests passed.
Fifteen equation tests include monthly-total preservation, cash cancellation,
raw actions, entry/exit entitlement, actual sessions, future-input noninterference,
origin-based breaks and full nine-feature feedback. Four feature-bridge tests
verify complete-vintage parity and missing/chronological boundaries. Both
manifest-connected notebooks executed successfully on the synthetic sample.
