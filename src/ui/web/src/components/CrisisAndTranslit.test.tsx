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
  it('merged phase renders kin-merge-pulse on the merged card', () => {
    const { container } = render(
      <TransliterationMatch phase="merged" onBack={() => {}} />,
    );
    // S8: merged card no longer has kin-rise (that belongs on the
    // absolute-positioned crisis modal only). It carries kin-merge-pulse.
    const matchLabel = screen.getByText('Match confirmed');
    const mergedCard = matchLabel.closest('.kin-merge-pulse');
    expect(mergedCard).not.toBeNull();
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

// S8 — dual-language rendering
type MiniData = Parameters<typeof TransliterationMatch>[0]['recordA'];

const AR_RECORD_A: MiniData = {
  title: "Intake A · Session #089",
  tone: "warm",
  reporter: "محمد الأحمد · الأب",
  reporterLatin: "Mohammed Al-Ahmad · Father",
  speakerLanguage: "ar",
  missingName: "محمد",
  missingNameLatin: "Mohammed",
  age: "8",
  lastSeen: "منطقة الحدود · منذ أسبوعين",
  lastSeenLatin: "Border zone · ~2 weeks ago",
  circumstance: "انفصل عن عائلته أثناء الفوضى عند نقطة التفتيش",
  circumstanceLatin: "Separated from family during chaos at the checkpoint",
};

const AR_RECORD_B: MiniData = {
  title: "Intake B · Session #147",
  tone: "cool",
  reporter: "أمل الأحمد · الأم",
  reporterLatin: "Amal Al-Ahmad · Mother",
  speakerLanguage: "ar",
  missingName: "محمد",
  missingNameLatin: "Mohamad",
  age: "8",
  lastSeen: "منطقة الحدود · منذ أسبوعين تقريباً",
  lastSeenLatin: "Border crossing area · ~2 weeks ago",
  circumstance: "فُقد أثناء حشود اللاجئين عند نقطة العبور",
  circumstanceLatin: "Lost during refugee crowd at the crossing",
};

const ES_RECORD: MiniData = {
  title: "Intake A · Session #001",
  tone: "warm",
  reporter: "Ana García · Madre",
  speakerLanguage: "es",
  missingName: "Carlos",
  age: "7",
  lastSeen: "la frontera con Colombia",
  circumstance: "Se separó durante el cruce",
};

describe('TransliterationMatch — S8 dual-language rendering', () => {
  it('Arabic-Arabic: value containers have dir=rtl; field labels stay in LTR chrome', () => {
    const { container } = render(
      <TransliterationMatch
        phase="split"
        onBack={() => {}}
        recordA={AR_RECORD_A}
        recordB={AR_RECORD_B}
      />,
    );
    // At least some value blocks are dir=rtl (one per card per field)
    const rtlBlocks = container.querySelectorAll('[dir="rtl"]');
    expect(rtlBlocks.length).toBeGreaterThan(0);

    // Field label "Reporter" is NOT inside a dir=rtl element
    const reporterLabel = screen.getAllByText('Reporter')[0];
    const closestRtl = reporterLabel.closest('[dir="rtl"]');
    expect(closestRtl).toBeNull();
  });

  it('mixed Spanish-Arabic: each record value block takes its own direction, chrome stays LTR', () => {
    const { container } = render(
      <TransliterationMatch
        phase="split"
        onBack={() => {}}
        recordA={ES_RECORD}
        recordB={AR_RECORD_B}
      />,
    );
    // Arabic card has at least one dir=rtl value block
    const rtlBlocks = container.querySelectorAll('[dir="rtl"]');
    expect(rtlBlocks.length).toBeGreaterThan(0);

    // Spanish name "Carlos" is NOT inside a dir=rtl block
    const carlosEl = screen.getByText('Carlos');
    expect(carlosEl.closest('[dir="rtl"]')).toBeNull();
  });

  it('Arabic speakerLanguage: source-script primary renders, Latin secondary renders for all fields', () => {
    render(
      <TransliterationMatch
        phase="split"
        onBack={() => {}}
        recordA={AR_RECORD_A}
        recordB={AR_RECORD_A}
      />,
    );
    // Primary Arabic name
    expect(screen.getAllByText('محمد').length).toBeGreaterThan(0);
    // Latin secondary for name
    expect(screen.getAllByText('Mohammed').length).toBeGreaterThan(0);
    // lastSeen Arabic primary
    expect(screen.getAllByText('منطقة الحدود · منذ أسبوعين').length).toBeGreaterThan(0);
    // lastSeen Latin secondary
    expect(screen.getAllByText('Border zone · ~2 weeks ago').length).toBeGreaterThan(0);
  });

  it('Spanish speakerLanguage: no Latin secondary lines rendered beneath values', () => {
    const { container } = render(
      <TransliterationMatch
        phase="split"
        onBack={() => {}}
        recordA={ES_RECORD}
        recordB={ES_RECORD}
      />,
    );
    // "Carlos" appears exactly twice (one per card), no secondary duplicate
    const carlosEls = screen.getAllByText('Carlos');
    expect(carlosEls.length).toBe(2);

    // No text nodes that are Latin translations of the Spanish values
    // (ES_RECORD has no *Latin fields so no secondary divs rendered)
    const secondaryDivs = container.querySelectorAll('[dir="ltr"].text-muted');
    expect(secondaryDivs.length).toBe(0);
  });

  it('merged phase: Confirm/Reject/Escalate buttons visible', () => {
    render(
      <TransliterationMatch phase="merged" onBack={() => {}} />,
    );
    expect(screen.getByRole('button', { name: /Confirm match/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reject/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Escalate/ })).toBeInTheDocument();
  });

  it('split and linking phases render no Confirm/Reject/Escalate buttons (regression)', () => {
    const { rerender } = render(
      <TransliterationMatch phase="split" onBack={() => {}} />,
    );
    expect(screen.queryByRole('button', { name: /Confirm match/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Reject/ })).toBeNull();

    rerender(<TransliterationMatch phase="linking" onBack={() => {}} />);
    expect(screen.queryByRole('button', { name: /Confirm match/ })).toBeNull();
  });
});
