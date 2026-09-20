# M3 single-run monitor design

Added 2026-09-20 at the user's request. This is an M3 deliverable, following M2;
it does not replace publication refresh, the thesis journal or observation safety.

## Main view: task timeline with dependency links

Use a horizontal elapsed-time axis and rows grouped by role, with one bar per
**task**. Expand a task to see its individual model/tool attempts. A role may spawn
several tasks; a task may invoke several isolated worker processes. Label all three
identities accurately rather than drawing a permanent agent process that does not
exist. Start with the complete run in view; selecting a task highlights its parent,
requested answers and downstream consumers. Show other dependency links on demand
to keep crossings readable. Stable rows preserve timing, maintain the selection during updates and make
comparison across runs easier. The selectable edges explain spawning and
cooperation on the same view as elapsed time and deadlines.

```text
Run 34c0…   RESEARCH / RUNNING                 Updated 14:32:08 [Follow live]
Wall: 06:10 elapsed / 20:00 ceiling / 13:50 left
Calls: 18 / 40    Input: 340k / 1M    Output: 9k / 100k
Catalog estimate: $0.82 / $25    Final reserve: 8 calls    Sources: 12 / 250

Role / task / symbols              0m      2m      4m      6m       Deadline
Challenger · independent           [done]
Director · plan                       [done]──┐
Company · ANET/MU/META/NVDA                  [done]─request─┐
Macro · all                                [done]··reuse··┘
Technical · all                                    [RUNNING ░░░]
Geopolitics · all                                   ○ queued
Commodities · omitted: no material channel
Director · draft / challenge / final                reserved, not spawned

Selected task: Technical / task-6 / all symbols
[Brief] [Findings] [Evidence & calculations] [Trace] [Usage]
Started … | elapsed 00:42 | current worker timeout in 01:18
Turns 2 / 5 | up to 3 left | run deadline 13:50 left
```

The sketch is a layout specification, not a claim that this run is executing or
that the current sequential controller runs concurrent workers. The view must work
with one or two active slots without changing the data model.

## Visual and numerical semantics

- Creation/spawn is a timestamp marker. Queued time is a thin line from creation to
  start. Running/completed work is a solid bar from actual start to now/end. Show
  unused **hard allowance** as a light outlined segment only when that allowance
  has a meaningful time boundary. Model-call allowance is a count, not a duration.
- Use status text and icons as well as color: queued, running, completed, omitted,
  interrupted and failed. Do not show “80% researched” from elapsed time or token
  consumption. A completed task can have an `insufficient_evidence` result.
- Distinguish run wall-clock deadline (including pauses), current worker timeout,
  task turns remaining, and shared aggregate budgets. Show actual receipts and
  configured ceilings, plus reserved final-synthesis capacity. Task ceilings are
  not independent allocations of the entire run budget. An estimated catalog
  cost is not an invoice. Unknown usage is visibly unknown, with the known lower
  bound; never convert it into zero or a reassuring green remaining-budget bar.
- A completed bar shows its recorded finish time and duration. On interruption,
  freeze at the recorded stop/last observation and mark uncertainty; do not leave
  an abandoned task looking actively productive. An omitted role has a reason
  row and no invented task bar. Planned/unspawned stages are an explicitly labeled
  outline separate from the actual task list.
- Use different labeled edges for parent assignment, new research request and
  reuse of an existing answer. Reuse creates a link, not another task/process.
  A question waiting for triage or an answer appears as a dependency badge with
  age and disposition. It does not imply an occupied worker slot.

## Task inspector and trace access

Selecting a bar opens a persistent side panel with the task's neutral question,
symbols/horizon, role and prompt version, model, permitted tools, creation/start/end,
parent/request IDs and budgets. Findings show the individual accepted result,
claims, evidence links, uncertainty and conditions; before acceptance say “no
accepted result yet.” Keep rejected submissions visibly separate.

Evidence opens the task's **visible manifest**, not whichever evidence happens to
be newest. Link dated source excerpts, normalized fields, deterministic formulas,
input IDs, numeric values and source hashes. Trace lists immutable request/response
IDs, attempted tool, result/typed gap, timestamps and usage receipt for every
attempt, including rejected validation and failed attempts. Label this a recorded
request/tool/output trace; private model reasoning is neither available nor promised.
Provide copyable relative artifact paths and JSON download of the selected record.
Large raw documents load only on request. Render all source/model text escaped.

Filters: role, symbol, stage and status. A keyboard-accessible table offers the same
information as the chart. Labels, contrast, focus order and a reduced-motion mode
must make the monitor usable without color or animation. Auto-follow should not
move a user's selected task or reset inspector scroll.

## Local implementation and telemetry contract

Use a local read-only endpoint or CLI-produced snapshot over the controller's
atomic state and immutable artifact store; poll about once per second initially.
This does not require a cloud service, external account or a new orchestration
framework. The browser gets no provider credentials and cannot invoke tools or
mutate run state. Only allow known run IDs/artifact kinds and content-addressed
IDs, with no arbitrary filesystem paths. Resolve recorded model-visible evidence
aliases using that request's frozen map when linking its trace to stored evidence. Serve locally by default. Keep ordinary
Markdown reports usable without the monitor.

M2 already records task creation/start/completion, role/scope, parent links, stage
turn ceilings, worker timeout, attempt timestamps, usage receipts, questions,
accepted manifests and immutable request/response IDs. M3 must complete the
projection contract: monotonically numbered events, run/attempt/task terminal
timestamps for **all** stop paths, explicit budget-reserve/omission events,
current active worker deadline, and sequence-aware incremental reads. Add fields
under a new telemetry version; historical absent fields remain unknown. The UI
must not infer event times from file modification times or fabricate historical
progress. Persist everything needed to replay the same view after completion.
Read-only monitoring must not acquire the controller's exclusive execution lock.

## M3 acceptance additions

A single five-symbol run can be followed from source seeding through draft,
challenge, final refresh and publication, then reopened with the same results.
A user can identify who requested a task, why it exists, its allocation and time
remaining, when it finished, and open its individual result and trace in one click.
The graph/timeline never disagree with the saved task or attempt status.

Fixtures cover queued work, sequential and two-slot execution, reused answers,
optional-role omission, source failure, rejected submission, unknown cost/usage,
budget exhaustion, worker timeout, process interruption and resume. The failed
attempt remains visible exactly once and is not silently replayed. Verify that
run totals reconcile with receipts and the final frozen bundle, that a stale
browser displays its last-update time, and that special characters/source text
cannot inject HTML. Check chart/table keyboard parity and preserved inspection
state during live updates. Publication/outcome fixtures in the main M3 gate remain
required independently of this monitor.


The M2 accepted example is `reports/investment-research/m2-live-v7`: 11 tasks,
34 invocations, a reused Macro answer and a separately spawned Company follow-up.
Use it as a real replay fixture alongside the explicitly synthetic failure cases.
Its semantic review also calls for showing full review-condition fields together
in the Findings inspector: comparator, decimal threshold, share basis, expiry and
evidence date, with a distinct human-review presentation.
