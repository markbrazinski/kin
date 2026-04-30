/* CrisisReferralCard + TransliterationMatch tests.

   CrisisReferralCard: body falls back to CRISIS_COPY[lang] when the
   optional `message` prop is absent or whitespace-only, and uses the
   message verbatim when provided. ADR-004 REV 3.

   TransliterationMatch (S7): merged card carries both kin-rise (entry)
   and kin-merge-pulse (Beat 6 success pulse) classes only when phase
   is 'merged'. The classes themselves; we don't assert on visual
   timing — that's covered by the index.css keyframe definitions. */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CrisisReferralCard, TransliterationMatch } from './CrisisAndTranslit';

describe('CrisisReferralCard', () => {
  it('renders Gemma-supplied message when provided', () => {
    const gemma = 'يرجى الاتصال بالرقم الموحد للدعم';
    render(
      <CrisisReferralCard
        workerLanguage="en"
        speakerLanguage="ar"
        message={gemma}
        onResolved={() => {}}
        onDeEscalated={() => {}}
      />,
    );
    expect(screen.getByText(gemma)).toBeInTheDocument();
  });

  it('falls back to CRISIS_COPY[speakerLanguage] body when message is absent', () => {
    render(
      <CrisisReferralCard
        workerLanguage="en"
        speakerLanguage="es"
        onResolved={() => {}}
        onDeEscalated={() => {}}
      />,
    );
    // CRISIS_COPY.es.body starts with "Está a salvo aquí."
    expect(screen.getByText(/Está a salvo aquí/)).toBeInTheDocument();
  });

  it('falls back to CRISIS_COPY[speakerLanguage] body when message is whitespace-only', () => {
    render(
      <CrisisReferralCard
        workerLanguage="en"
        speakerLanguage="es"
        message="   "
        onResolved={() => {}}
        onDeEscalated={() => {}}
      />,
    );
    expect(screen.getByText(/Está a salvo aquí/)).toBeInTheDocument();
  });

  it('S6 chrome split: workerLanguage drives operator chrome (English) while speakerLanguage drives body (Spanish)', () => {
    render(
      <CrisisReferralCard
        workerLanguage="en"
        speakerLanguage="es"
        onResolved={() => {}}
        onDeEscalated={() => {}}
      />,
    );
    // Operator chrome (small red header) in English.
    expect(screen.getByText('Crisis signal detected')).toBeInTheDocument();
    expect(screen.getByText(/Primary record paused/)).toBeInTheDocument();
    // Dismiss buttons in English (workerLanguage).
    expect(screen.getByRole('button', { name: /De-escalated/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Referral provided/ })).toBeInTheDocument();
    // Speaker surface (BIG title) in Spanish.
    expect(screen.getByText('Ayuda disponible')).toBeInTheDocument();
  });

  it('S6 dir split: speaker section gets dir=rtl when speakerLanguage=ar; operator chrome stays ltr', () => {
    const { container } = render(
      <CrisisReferralCard
        workerLanguage="en"
        speakerLanguage="ar"
        onResolved={() => {}}
        onDeEscalated={() => {}}
      />,
    );
    const dialog = container.querySelector('[role="dialog"]')!;
    // Outer dialog inherits workerLanguage direction (LTR).
    expect(dialog.getAttribute('dir')).toBe('ltr');
    // Speaker surface (the BIG-title block) has its own dir=rtl.
    const arabicTitle = screen.getByText('المساعدة متاحة');
    const speakerSection = arabicTitle.closest('[dir="rtl"]');
    expect(speakerSection).not.toBeNull();
  });
});

describe('TransliterationMatch — Beat 6 merge animation (S7)', () => {
  it('merged phase renders kin-rise + kin-merge-pulse on the merged card', () => {
    const { container } = render(
      <TransliterationMatch phase="merged" onBack={() => {}} />,
    );
    // The "Match confirmed" label is the unique anchor inside the
    // merged card — its parent div carries the animation classes.
    const matchLabel = screen.getByText('Match confirmed');
    const mergedCard = matchLabel.closest('.kin-rise');
    expect(mergedCard).not.toBeNull();
    expect(mergedCard!.classList.contains('kin-merge-pulse')).toBe(true);
    // Negative control: when phase !== merged the merged card is
    // not rendered at all (single Match confirmed in DOM only when
    // we're on the merged phase).
    expect(container.querySelectorAll('.kin-merge-pulse').length).toBe(1);
  });

  it('split + linking phases render no merged card and no kin-merge-pulse', () => {
    const { container, rerender } = render(
      <TransliterationMatch phase="split" onBack={() => {}} />,
    );
    expect(container.querySelectorAll('.kin-merge-pulse').length).toBe(0);
    expect(screen.queryByText('Match confirmed')).toBeNull();

    rerender(<TransliterationMatch phase="linking" onBack={() => {}} />);
    expect(container.querySelectorAll('.kin-merge-pulse').length).toBe(0);
    expect(screen.queryByText('Match confirmed')).toBeNull();
  });
});
