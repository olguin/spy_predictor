# Registered successor: computational stop

2026-09-09. The single permitted successor is registered and terminal. Its first
complete development replication took **88.74999 seconds**. The registered
conservative projection, maximum completed full-procedure time × 20,000, is
**1,774,999.77 seconds (20.54 days)**. The frozen validation budget is 3,600 seconds.
The profile used 88.76 seconds of its 120-second budget and stopped early on the
failed projection. This projection was measured here; the long run was not made.

Decision: **INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET**. There is one completed
development replication (scenario 0, replication 0), zero locked replications,
zero remaining redesign slots, and no real-data approval. No statistical power
failure or market-predictive result was established. Neither the required sample
count nor any effects, thresholds, scenarios, calendars or bootstrap settings
were weakened.

Evidence:

- [Atomic registration](../experiments/cycle1-power-redesign/registration.json):
  `88b0d0498607721d6140b45fe4dcec8cca974fb884dae17ec140d2083a12d59f`.
- [Terminal decision](../experiments/cycle1-power-v2/decision.json):
  `238b3770f41551a2ff85480739c5552b28bef0bf10825d9618984615b7d54268`.
- [Refreshed deterministic fixture](../reports/cycle1-successor-integration-00b9d128f8f0951b/report.json):
  `00b9d128f8f0951b57e8420edd0dc84f94f09146f8e4cd7f6cb7778245194500`.
- [Development result](../experiments/cycle1-power-v2/development/0-0.json),
  [draw claim](../experiments/cycle1-power-v2/draws/0-0.json), and
  [profile opening](../experiments/cycle1-power-v2/profile-opening.json).

The registration binds code, configuration/schema, source-audit and predecessor
identities, dependency lock, installed versions, all 9,191 scheduled daily session
opens/closes and the deterministic fixture. Atomic no-replace claims protect the
registration, profile opening and each development draw. The sampler uses 16
independent SeedSequence children and constructs the registered monthly and daily
innovations. It never substitutes a daily normal for a monthly Student shock.
The profile includes full generation, real feature extraction, annual labels,
selection/confirmation, transfer, downside and costed policy branch exercises.

No validation sampler is released by this runner. A failed budget projection or
deadline closes the experiment; arithmetic failures produce invalid evaluation
without redraw. Repeating the profile command after this stop returns the same
decision without additional draws.

```bash
npm run cycle1:successor -- status
```

Expected exit 2 reproduces computational insufficiency. Keep the original v1
stop and this successor stop immutable. Any further primary research requires an
explicit new plan addressing computational feasibility outside the closed
protocols; this result does not permit automatic redesign, source migration,
historical evaluation or confirmation opening. The secondary workbench can
continue independently.
