# Local research workspace and first real M3 pilot

September 21, 2026 UTC (September 20 local). Question entry and conclusions are
available before launching the user's real NVDA/MU/QQQ development pilot. This
does not evaluate frozen release cases or change M4 acceptance requirements.

## Use the workspace

```sh
node --env-file=.env scripts/investment-research.mjs workspace --port 8766
```

Open <http://127.0.0.1:8766/>. This version supports **NVDA and MU against QQQ**, a
**63-trading-session** horizon, USD and long-only research. The visible universe
and horizon remain fixed; free text refines the research question within that
scope. Broader ticker selection requires a separately registered source universe.

1. Enter the question and read the displayed budget. **Start research** makes
   real provider calls and creates a separate saved run.
2. Open its **Monitor** for current activity, specialist findings, tools, evidence,
   receipts and remaining budgets. Browser refresh does not start or stop research.
3. Read **Reports & conclusions** for each instrument's thesis/demand drivers,
   valuation assumptions, downside/counter-case and evidence that would change
   the assessment. Claims link to the exact saved evidence.
4. A completed run is initially a **draft**. Review its claims and limitations,
   then choose **Reviewed — refresh & publish** within the original run deadline.
   The bounded final refresh can withdraw affected guidance. Publication means a
   dated immutable research record; it is not release approval or a trade order.

Port 8765 now serves a compatibility address for the latest workspace run, after
the user found the separate old-run address confusing. Run
`python/.venv/bin/python scripts/redirect-investment-research-monitor.py` alongside
the workspace to provide it. New navigation redirects to the canonical workspace
monitor; old open tabs can still poll its read-only snapshot/artifact APIs. This
relay never starts research and does not change a run's frozen code identity.
An explicitly launched standalone `monitor --output ...` on another port remains
a single-run saved replay. Its banner states clearly when no research is running.

## Execution status

- **Research running:** evidence acquisition, an active worker or scheduling.
- **Ready — research has not started:** a controller has not begun execution.
- **Finished — draft ready / report published:** saved replay, with finish time.
- **Stopped — saved replay:** incomplete, failed or interrupted; stop reason shown.
- **Status uncertain / connection lost / view paused:** ongoing execution cannot
  be confirmed from the page. A working polling connection alone is never labeled
  as proof of an active research worker.

There is no automatic paid retry after failure, interruption or server restart.
An unchanged repeated form submission retains its request UUID, avoiding duplicate
runs after a lost response. Only one research/publication operation runs in a
workspace at a time. Keep the server process open while research is running.

## Bounds and artifacts

The existing provider/model and budget remain: `openai-codex/gpt-5.6-terra`, medium
reasoning, 40 model calls, 1,000,000 input tokens, 100,000 output tokens, 1,200
seconds and $25 catalog estimate ceiling. Provider-reported consumption is still
validated after a response, so this is not a prepaid billing cap. Eight calls
remain reserved for final work; publication reserves its source/tool capacity.

Workspace questions, mandates, job records and runs are under
`reports/investment-research/workspace-v1/<job-uuid>/`. Publication bundles and
the journal are under `datasets/investment-research/workspace-v1/`. Each mandate
freezes its source window and policy before the run. Earlier accepted runs,
failed candidates, synthetic artifacts and frozen M4 records remain untouched.

Browser mutation routes require the exact local Host, a matching Origin and a
server-session token. They accept only question/request IDs or the explicit
publication action. The browser cannot supply runtime commands, model changes,
filesystem paths, budgets or arbitrary source URLs. Credentials stay server-side.
The standalone monitor remains read-only.

Published conclusions are read from the verified immutable bundle, rather than
the original draft product. If the final refresh withdraws guidance, its summary,
valuation, counter-case and review conditions cannot remain presented as current;
the original findings remain archived for audit.

## Pilot registration and checks

Question: “Research NVDA and MU over the next three months. Compare their
valuation assumptions, demand drivers, and downside risks against QQQ. Explain
what evidence would change each assessment.”

The no-model source check is retained in
`reports/investment-research/nvda-mu-qqq-pilot-preflight-v1/`. All critical sources
passed. FRED timed out and the BIS page was unavailable. The live QQQ sponsor page
did not deliver current holdings; dated sponsor captures retain their original
dates. Issuer releases and upcoming-event announcements were registered as
primary sources. The extractor now prefers a publisher's semantic HTML `main`
region, keeping navigation from consuming the excerpt; complete raw documents
remain archived without modification.

Launch receipt: `reports/investment-research/nvda-mu-qqq-pilot-launch-v1.json`.
Workspace job: `cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d`.

Before launch: 32 workspace/M3 tests and 15 M2 tests passed. Headless Chrome passed
question entry, synthetic form submission, draft conclusions, mobile entry layout
and the running/draft/published/failed/interrupted/uncertain status banners with
zero browser exceptions. The standalone replay browser check also passed. No
provider calls were made by these engineering tests. Browser scripts:
`scripts/check-investment-research-workspace.py` and
`scripts/check-investment-research-monitor.py`.

## Pilot outcome

The pilot completed and published, with no automatic paid retry:

- Run `04bc90a5-dc91-4fe7-8df8-f0a88d7f3c31`, publication
  `20a51b05-4441-464b-abcd-e36f088da231`, published September 21 at
  `03:10:20.148513 UTC` (00:10 local).
- Ten tasks, 28 actual model calls, 565,541 input tokens, 18,568 output tokens,
  $1.3393828 catalog estimate, 822.46 seconds of research. Including manual review
  and publication, 972.22 seconds elapsed, within the original 1,200-second limit.
- All 12 registered refresh sources succeeded. No material changes or guidance
  invalidations were detected. Daily closes remain dated September 18; executable
  quotes are unavailable. There was no trade or order submission.
- Seven final claims were reviewed against stored primary sources/normalized
  observations, with no critical factual or numerical output error identified.
  Four specialist roles completed; Commodities was explicitly omitted. The
  Technical→Macro question reused an existing answer. All five questions and
  eight objections have recorded dispositions.
- **Usefulness is partial:** the report differentiates demand, downside mechanisms
  and change-of-view evidence, but does not calculate company valuation scenarios
  or support a relative preference. All three assessments are
  `insufficient_evidence`. Evidence gaps remain explicit. This is not a completed
  relative valuation analysis or a positive usefulness evaluation.
- Follow-up priorities: assumption-based company valuation scenarios and comparable
  valuation inputs; targeted filing sections and working policy/holdings sources;
  narrower treatment of missing evidence instead of blanket abstention. Actual
  user feedback on usefulness remains pending.

Acceptance, draft/publication/replay audits and manual review are saved in
`reports/investment-research/workspace-v1/cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d/`.
Publication and observation contracts are immutable. The observation origin is
the September 21 regular open, with the 63rd-session target at the December 17
close; those prices remain unobserved, and no performance result is claimed.

After publication the user requested that the monitor lead with the exact
research question, instruments and horizon. That presentation change passed
32 focused checks and the updated browser check, and was verified against the
real published API. It changes current source identity, so the completed pilot
must not be execution-resumed under the newer runtime. Its frozen archive and
publication hashes still verify; read-only replay is supported.

M4 acceptance gates remain unchanged and open. No frozen release case was
evaluated. Comparator and frozen-case hashes still match their registrations.
