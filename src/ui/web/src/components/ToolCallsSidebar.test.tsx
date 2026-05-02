/* ToolCallsSidebar rendering tests — S3 plan Tests 1–3. */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ToolCallsSidebar } from './ToolCallsSidebar';
import type { ToolCall } from '../state/toolCalls';

const STARTED_CALL: ToolCall = {
  id: 'call-0',
  name: '…',
  status: 'started',
  args: null,
  result: undefined,
  tMs: 500,
};

const RESOLVED_CALL: ToolCall = {
  id: 'fill_rfl_record-0',
  name: 'fill_rfl_record',
  status: 'resolved',
  args: { full_name: 'Carlos', age: 7 },
  result: { latency_s: 1.4 },
  tMs: 1900,
};

describe('ToolCallsSidebar', () => {
  it('Test 1 — empty state renders prototype copy', () => {
    render(<ToolCallsSidebar calls={[]} />);
    expect(screen.getByText(/No invocations yet/)).toBeInTheDocument();
    expect(screen.getByText('Tool calls')).toBeInTheDocument();
    expect(screen.getByText('gemma · e2b')).toBeInTheDocument();
    expect(screen.getByText('function invocations · live')).toBeInTheDocument();
  });

  it('Test 2 — started row: muted name placeholder, running indicator, no args/result', () => {
    const { container } = render(<ToolCallsSidebar calls={[STARTED_CALL]} />);
    // "running" indicator visible
    expect(screen.getByText('running')).toBeInTheDocument();
    // No args or result labels
    expect(screen.queryByText('args')).toBeNull();
    expect(screen.queryByText('result')).toBeNull();
    // Function name has text-muted class (started state)
    const nameEl = container.querySelector('.font-mono.text-muted.font-medium');
    expect(nameEl).not.toBeNull();
  });

  it('Test 3 — resolved row: primary-color name, args block, result block, kin-populate on isLatest', () => {
    const { container } = render(
      <ToolCallsSidebar calls={[RESOLVED_CALL]} />,
    );
    // Function name visible
    expect(screen.getByText('fill_rfl_record')).toBeInTheDocument();
    // No "running" indicator on resolved row
    expect(screen.queryByText('running')).toBeNull();
    // Args label and key visible
    expect(screen.getByText('args')).toBeInTheDocument();
    expect(screen.getByText(/"full_name"/)).toBeInTheDocument();
    // Result label visible
    expect(screen.getByText('result')).toBeInTheDocument();
    // isLatest=true (only one call) → kin-populate class applied
    const row = container.querySelector('.kin-populate');
    expect(row).not.toBeNull();
  });

  it('kin-populate NOT applied to non-latest resolved row', () => {
    const calls: ToolCall[] = [
      RESOLVED_CALL,
      { ...RESOLVED_CALL, id: 'fill_rfl_record-1', tMs: 3000 },
    ];
    const { container } = render(<ToolCallsSidebar calls={calls} />);
    const pulseRows = container.querySelectorAll('.kin-populate');
    // Only the last row gets kin-populate
    expect(pulseRows.length).toBe(1);
  });

  it('footer shows resolved count and in-flight count', () => {
    const calls: ToolCall[] = [STARTED_CALL, RESOLVED_CALL];
    render(<ToolCallsSidebar calls={calls} />);
    expect(screen.getByText('1 resolved')).toBeInTheDocument();
    expect(screen.getByText('1 in flight')).toBeInTheDocument();
  });
});
