import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';
import { requireResearchRequest, type ResearchRequest } from './pi-research-contract';

it('admits actual Python controller envelopes across roles, stages and one-to-five-stock scope', () => {
  const root = resolve(import.meta.dirname, '../../..');
  const rows: { label: string; request: ResearchRequest }[] = JSON.parse(execFileSync(
    resolve(root, 'python/.venv/bin/python'), ['python/tests/research_wire_fixture.py'],
    { cwd: root, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }));
  expect(rows.length).toBeGreaterThan(100);
  const reserved = rows.filter(row => Object.keys(row.request.tool_schemas).join(',') === 'calculate_scenarios');
  expect(reserved.length).toBe(16); // 1+2+3+4+5 company grids, plus one mixed company/ETF.
  for (const row of rows) {
    expect(() => requireResearchRequest(row.request), row.label).not.toThrow();
    if (row.request.context.task && (row.request.context.task as { stage: string }).stage === 'triage') {
      const route = row.request.tool_schemas.route_question;
      if (route) expect((route.properties as any).question_id.enum).toEqual(['question-wire']);
    }
  }
  expect(rows.some(row => row.label.startsWith('NVDA,MU,ANET,META,AAPL:director:final')
    && row.request.runtime.max_output_tokens === 20000)).toBe(true);
}, 30000);
