/* Crisis referral card + Transliteration-match view. */
import React from 'react';
import type { ReactNode } from 'react';
import { IconAlert, IconPause, IconPlay, IconInfo, IconLock, IconArrowRight, IconLink, IconCheck } from './icons';
import { Button, Chip, Waveform } from './primitives';
import type { Language, MatchPhase } from '../lib/types';

type CrisisCopyEntry = {
  dir: 'ltr' | 'rtl';
  title: string;
  body: string;
  hotline: string;
  play: string;
};

export type CrisisReferralCardProps = {
  lang: Language;
  onResolved: () => void;
  onDeEscalated: () => void;
};

type MiniRecordTone = 'warm' | 'cool';

type MiniRecordProps = {
  title: ReactNode;
  tone: MiniRecordTone;
  reporter: ReactNode;
  missingName: ReactNode;
  missingScript: ReactNode;
  age: ReactNode;
  lastSeen: ReactNode;
  circumstance: ReactNode;
};

export type TransliterationMatchProps = {
  phase: MatchPhase;
  onBack: () => void;
};

// Localized crisis copy. English stays as reference; the other three are the displaced-person UI.
const CRISIS_COPY: Record<Language, CrisisCopyEntry> = {
  en: { dir: "ltr", title: "Help is available",
        body: "You are safe here. Trained support is available right now, in your language. Would you like to listen to a short message?",
        hotline: "IFRC Regional Support Line",
        play: "Play in English" },
  es: { dir: "ltr", title: "Ayuda disponible",
        body: "Está a salvo aquí. Hay apoyo disponible ahora mismo, en su idioma. ¿Quiere escuchar un mensaje corto?",
        hotline: "Línea de Apoyo Regional FICR",
        play: "Reproducir en español" },
  ar: { dir: "rtl", title: "المساعدة متاحة",
        body: "أنتَ في أمان هنا. الدعم متاح الآن، بلغتك. هل ترغب في الاستماع إلى رسالة قصيرة؟",
        hotline: "خط الدعم الإقليمي للاتحاد الدولي لجمعيات الصليب الأحمر والهلال الأحمر",
        play: "تشغيل بالعربية" },
  fa: { dir: "rtl", title: "کمک در دسترس است",
        body: "شما اینجا در امان هستید. همین حالا، به زبان شما، پشتیبانی در دسترس است. آیا می‌خواهید یک پیام کوتاه بشنوید؟",
        hotline: "خط پشتیبانی منطقه‌ای IFRC",
        play: "پخش به فارسی" },
};

function CrisisReferralCard({ lang, onResolved, onDeEscalated }: CrisisReferralCardProps) {
  const copy = CRISIS_COPY[lang] || CRISIS_COPY.en;
  const [playing, setPlaying] = React.useState(false);
  const rtl = copy.dir === "rtl";

  React.useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setPlaying(false), 3200);
    return () => clearTimeout(t);
  }, [playing]);

  return (
    <div
      role="dialog"
      aria-label="Crisis referral"
      className="kin-rise fixed left-1/2 top-[140px] z-30 w-[min(640px,calc(100%-48px))] bg-card border border-line rounded-kin-lg shadow-elevated"
      style={{ transform: "translateX(-50%)" }}
    >
      {/* Header: red used sparingly (icon + thin accent rule), not as a background */}
      <div className="border-b border-hair px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-kin border border-red/30 bg-red-soft text-red flex items-center justify-center">
          <IconAlert size={18} />
        </div>
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-red">Crisis signal detected</div>
          <div className="text-[14px] text-muted">Primary record paused. Surface this card to the person in front of you.</div>
        </div>
      </div>

      {/* Displaced-person-facing surface */}
      <div className={`px-6 py-5 ${rtl ? "rtl" : ""}`}>
        <div className="text-[26px] font-semibold text-ink leading-tight">{copy.title}</div>
        <p className="mt-2 text-[17px] text-ink/90 leading-relaxed" style={{ textWrap: "pretty" }}>
          {copy.body}
        </p>

        <div className="mt-4 border border-line rounded-kin p-4 bg-subtle/60">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setPlaying(true)}
              className="shrink-0 w-12 h-12 rounded-full bg-primary text-white border border-primary hover:bg-primary-2 transition-colors flex items-center justify-center"
              aria-label={copy.play}
            >
              {playing ? <IconPause size={20} /> : <IconPlay size={20} />}
            </button>
            <div className="flex-1 min-w-0">
              <div className="text-[15px] font-medium text-ink">{copy.play}</div>
              <div className="mt-1"><Waveform state={playing ? "playback" : "idle"} bars={28} /></div>
            </div>
          </div>
        </div>

        <div className={`mt-4 flex items-center gap-2 text-[14px] text-muted ${rtl ? "flex-row-reverse" : ""}`}>
          <IconInfo size={14} />
          <span>{copy.hotline} · +00 000 000 0000</span>
        </div>
      </div>

      {/* Dismissal: two explicit logged actions, no generic Close. */}
      <div className="border-t border-hair bg-subtle/60 px-6 py-3 flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button variant="secondary" onClick={onDeEscalated}>De-escalated — continue intake</Button>
        <Button variant="confirm" icon={<IconCheck size={16} />} onClick={onResolved}>Referral provided</Button>
      </div>
    </div>
  );
}

// --- Transliteration match view ------------------------------------------
function MiniRecord({ title, tone, reporter, missingName, missingScript, age, lastSeen, circumstance }: MiniRecordProps) {
  const toneBg = tone === "warm" ? "bg-[oklch(0.985_0.012_75)]" : "bg-[oklch(0.985_0.006_220)]";
  return (
    <div className={`flex-1 border border-line rounded-kin-lg ${toneBg}`}>
      <div className="px-5 py-3 border-b border-hair flex items-center justify-between">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">{title}</div>
        <Chip icon={<IconLock size={12} />} tone="neutral" className="!bg-white">Local only</Chip>
      </div>
      <div className="px-5 py-4">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Reporter</div>
        <div className="text-[15px] text-ink mt-0.5">{reporter}</div>

        <div className="mt-4 text-[12px] font-medium uppercase tracking-wider text-muted">Missing child</div>
        <div className="mt-1 flex items-baseline gap-3">
          <div className="text-[20px] font-semibold text-ink">{missingName}</div>
          <div className="rtl text-[20px] text-ink/80">{missingScript}</div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Age</div>
            <div className="text-[16px] text-ink">{age}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last seen</div>
            <div className="text-[16px] text-ink">{lastSeen}</div>
          </div>
          <div className="col-span-2">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Circumstance</div>
            <div className="text-[16px] text-ink">{circumstance}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TransliterationMatch({ phase, onBack }: TransliterationMatchProps) {
  // 'split'   → two MiniRecord cards side by side, no link drawn
  // 'linking' → Y-shape link animates toward the match card
  // 'merged'  → MATCH CONFIRMED card with unified identity
  const showLink = phase === "linking" || phase === "merged";
  const merged   = phase === "merged";

  return (
    <div className="max-w-[960px] mx-auto w-full">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Reunification candidate</div>
          <div className="text-[22px] font-semibold text-ink mt-0.5">Cross-session match under review</div>
        </div>
        <Button variant="ghost" size="sm" icon={<IconArrowRight className="rotate-180" size={16} />} onClick={onBack}>
          Back to intake
        </Button>
      </div>

      <div className={`grid grid-cols-1 md:grid-cols-2 gap-5 transition-opacity duration-300 ${merged ? "opacity-30" : ""}`}>
        <MiniRecord
          title="Intake A · Session #089"
          tone="warm"
          reporter="Layla Al-Saleh · Mother"
          missingName="Omar Al-Saleh"
          missingScript="عمر الصالح"
          age="9"
          lastSeen="Ar-Raqqa outskirts · ~6 days ago"
          circumstance="Separated during crowd surge leaving the neighbourhood"
        />
        <MiniRecord
          title="Intake B · Session #147"
          tone="cool"
          reporter="Yousef Al-Saleh · Father"
          missingName="Umar Alsaleh"
          missingScript="عمر الصالح"
          age="9"
          lastSeen="Ar-Raqqa outskirts · ~6 days ago"
          circumstance="Lost sight of him near the transit checkpoint"
        />
      </div>

      {/* Animated Y-shape connector: two streams from the intake panel
          bottoms converging to the top edge of the Match Confirmed card. */}
      <div className="relative h-20 mt-2 mb-0">
        {showLink && (
          <svg viewBox="0 0 400 80" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
            <path
              d="M 80 0 C 80 40, 200 40, 200 80"
              fill="none"
              stroke="oklch(0.55 0.11 155)"
              strokeWidth="1.5"
              strokeLinecap="round"
              pathLength={60}
              className="kin-link-draw"
            />
            <path
              d="M 320 0 C 320 40, 200 40, 200 80"
              fill="none"
              stroke="oklch(0.55 0.11 155)"
              strokeWidth="1.5"
              strokeLinecap="round"
              pathLength={60}
              className="kin-link-draw"
            />
          </svg>
        )}
      </div>

      {/* Merged card */}
      {merged && (
        <div className="kin-rise relative bg-card border border-green/40 rounded-kin-lg" style={{ transform: "none" }}>
          <div className="px-6 py-4 border-b border-hair bg-green-soft/60 flex items-center gap-3">
            <div className="w-8 h-8 rounded-kin bg-white border border-green/40 text-green flex items-center justify-center">
              <IconLink size={16} />
            </div>
            <div>
              <div className="text-[12px] font-medium uppercase tracking-wider text-[oklch(0.38_0.1_155)]">Match confirmed</div>
              <div className="text-[15px] text-ink mt-0.5">2 intake sessions matched via transliteration comparison.</div>
            </div>
            <div className="ml-auto"><Chip icon={<IconCheck size={12} />} tone="green">Pending caseworker review</Chip></div>
          </div>
          <div className="px-6 py-5">
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Unified identity · missing child</div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div className="rtl text-[28px] font-semibold text-ink">عمر الصالح</div>
              <div className="text-[22px] text-ink">Omar Al-Saleh</div>
              <div className="text-[16px] text-muted">· also: Umar Alsaleh</div>
            </div>

            <div className="mt-5 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Source script</div>
                <div className="rtl text-[17px] text-ink mt-0.5">عمر الصالح</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Phonetic variants</div>
                <div className="text-[15px] text-ink mt-0.5">Omar · Umar</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Age</div>
                <div className="text-[15px] text-ink mt-0.5">9</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Linked sessions</div>
                <div className="text-[15px] text-ink mt-0.5">#089 (Mother) · #147 (Father)</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last-seen overlap</div>
                <div className="text-[15px] text-ink mt-0.5">Ar-Raqqa outskirts · ~6 days ago</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Next step</div>
                <div className="text-[15px] text-ink mt-0.5">Route to caseworker for reunification review</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { CrisisReferralCard, TransliterationMatch, CRISIS_COPY };
