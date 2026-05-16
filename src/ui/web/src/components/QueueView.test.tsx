/* QueueView + RecordReadonly tests — B1.5-S7. */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueueView, QueueRow } from './QueueView';
import { RecordReadonly } from './RecordReadonly';
import type { IntakeRecord } from '../lib/intakeRecord';

const COMPLETE_RECORD: IntakeRecord = {
  id: 'aaaaaaaa-0000-0000-0000-000000000001',
  created_at: '2026-05-03T10:00:00Z',
  updated_at: '2026-05-03T10:00:00Z',
  status: 'complete',
  language: 'es',
  source_device_id: 'tent_a',
  full_name_source_script: 'Carlos',
  full_name_transliteration: 'Carlos',
  relationship_to_seeker: 'Father',
  age: 7,
  last_seen_location: 'la frontera',
  last_seen_location_transliteration: null,
  last_seen_date: '2026-05-01',
  distinguishing_marks: null,
  is_minor: false,
  is_crisis: false,
  referral_issued: false,
  referral_organization: null,
  family_roster: [],
  searcher_name: '',
  searcher_name_transliteration: '',
  searcher_relationship_to_target: '',
  separation_circumstance: null,
};

const PARTIAL_RECORD: IntakeRecord = {
  ...COMPLETE_RECORD,
  id: 'aaaaaaaa-0000-0000-0000-000000000002',
  status: 'partial',
  full_name_source_script: 'Ana',
  full_name_transliteration: 'Ana',
};

const CRISIS_RECORD: IntakeRecord = {
  ...COMPLETE_RECORD,
  id: 'aaaaaaaa-0000-0000-0000-000000000003',
  status: 'complete',
  is_crisis: true,
  full_name_source_script: 'محمد',
  full_name_transliteration: 'Mohammed',
};

const ARABIC_RECORD: IntakeRecord = {
  ...COMPLETE_RECORD,
  id: 'aaaaaaaa-0000-0000-0000-000000000004',
  language: 'ar',
  full_name_source_script: 'محمد',
  full_name_transliteration: 'Mohammed',
};

describe('QueueView', () => {
  it('Test 1 — empty state renders correct copy when records=[]', () => {
    render(<QueueView records={[]} onOpen={() => {}} onNew={() => {}} />);
    expect(screen.getByText('No records match this filter.')).toBeInTheDocument();
  });

  it('Test 1b — header renders correctly', () => {
    render(<QueueView records={[]} onOpen={() => {}} onNew={() => {}} />);
    expect(screen.getByText('Records on this device')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /New intake/ })).toBeInTheDocument();
  });

  it('Test 2a — QueueRow: Arabic record renders native script with RTL direction', () => {
    const { container } = render(
      <QueueRow record={ARABIC_RECORD} onOpen={() => {}} />,
    );
    // Latin primary (transliteration)
    expect(screen.getByText('Mohammed')).toBeInTheDocument();
    // Native Arabic script secondary is in the DOM
    expect(screen.getByText('محمد')).toBeInTheDocument();
    // A dir=rtl element is present (direction-scoped Arabic value)
    expect(container.querySelector('[dir="rtl"]')).not.toBeNull();
    // Complete status chip
    expect(screen.getByText('Complete')).toBeInTheDocument();
  });

  it('Test 2b — QueueRow: crisis record renders crisis chip', () => {
    render(<QueueRow record={CRISIS_RECORD} onOpen={() => {}} />);
    expect(screen.getByText('Crisis')).toBeInTheDocument();
    expect(screen.getByText('Mohammed')).toBeInTheDocument();
  });

  it('Test 3 — filter: incomplete excludes complete records', () => {
    render(
      <QueueView
        records={[COMPLETE_RECORD, PARTIAL_RECORD]}
        onOpen={() => {}}
        onNew={() => {}}
      />,
    );
    // Initially all records visible
    expect(screen.getByText('Carlos')).toBeInTheDocument();
    expect(screen.getByText('Ana')).toBeInTheDocument();

    // Click Incomplete filter button (the filter chip, not the Chip component)
    const filterBtns = screen.getAllByRole('button', { name: /Incomplete/ });
    // The filter button is the first one (rendered before the record rows)
    fireEvent.click(filterBtns[0]);
    // Complete record ("Carlos") no longer visible
    expect(screen.queryByText('Carlos')).toBeNull();
    // Partial record ("Ana") still visible
    expect(screen.getByText('Ana')).toBeInTheDocument();
  });
});

describe('RecordReadonly', () => {
  it('Test 4 — renders read-only banner and crisis status banner for is_crisis=true records', () => {
    render(
      <RecordReadonly
        record={CRISIS_RECORD}
        workerLanguage="en"
        onBack={() => {}}
        onNew={() => {}}
      />,
    );
    // Read-only banner
    expect(screen.getByText('Viewing previous record')).toBeInTheDocument();
    // Crisis-specific status banner
    expect(screen.getByText(/Crisis referral issued/)).toBeInTheDocument();
    // Back affordance
    expect(screen.getByRole('button', { name: /Back to queue/ })).toBeInTheDocument();
  });

  it('partial record shows amber waiting banner', () => {
    render(
      <RecordReadonly
        record={PARTIAL_RECORD}
        workerLanguage="en"
        onBack={() => {}}
        onNew={() => {}}
      />,
    );
    expect(screen.getByText(/Awaiting next turn/)).toBeInTheDocument();
  });

  it('complete record shows no status banner', () => {
    render(
      <RecordReadonly
        record={COMPLETE_RECORD}
        workerLanguage="en"
        onBack={() => {}}
        onNew={() => {}}
      />,
    );
    expect(screen.queryByText(/Crisis referral issued/)).toBeNull();
    expect(screen.queryByText(/Awaiting next turn/)).toBeNull();
  });
});
