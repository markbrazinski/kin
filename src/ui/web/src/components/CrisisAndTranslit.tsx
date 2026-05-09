/* Crisis referral card + Transliteration-match view. */
import React from 'react';
import type { ReactNode } from 'react';
import { IconAlert, IconPause, IconPlay, IconInfo, IconLock, IconArrowRight, IconLink, IconCheck } from './icons';
import { Button, Chip, Waveform } from './primitives';
import type { Language, MatchPhase } from '../lib/types';
import { dirFor, t } from '../lib/i18n';

type CrisisCopyEntry = {
  dir: 'ltr' | 'rtl';
  title: string;
  body: string;
  hotline: string;
  play: string;
};

export type CrisisReferralCardProps = {
  /* Bundle 1.5 S6 split: chrome (small red header + dismiss buttons)
     reads workerLanguage; the displaced-person-facing surface (BIG
     title, body, hotline, play button) reads speakerLanguage. The
     speaker surface also gets dir attribute from speakerLanguage so
     RTL applies only to that section, not the operator chrome. */
  workerLanguage: Language;
  speakerLanguage: Language;
  /* Gemma escalate_crisis tool's locale_aware_message (per ADR-004
     REV 3). When absent or whitespace-only, falls back to
     CRISIS_COPY[speakerLanguage].body — covers the demo button,
     Gemma tool_call failure, and any non-POST-driven open path. */
  message?: string | null;
  onResolved: () => void;
  onDeEscalated: () => void;
};

/* S8: per-record data shape for match view cards. Internal to this
   file — not a Core schema mirror. Each field carries the source-
   language value first; *Latin fields are the worker-language gloss
   rendered beneath when speakerLanguage is non-Latin (ar/fa). */
type MiniRecordData = {
  title: string;
  tone: 'warm' | 'cool';
  reporter: string;
  reporterLatin?: string;
  speakerLanguage: Language;
  missingName: string;
  missingNameLatin?: string;
  missingNameTranslit?: string;
  age: string;
  lastSeen: string;
  lastSeenLatin?: string;
  circumstance: string;
  circumstanceLatin?: string;
};

export type TransliterationMatchProps = {
  phase: MatchPhase;
  onBack: () => void;
  workerLanguage?: Language;
  recordA?: MiniRecordData;
  recordB?: MiniRecordData;
};

/* Returns true when speaker_language uses a non-Latin script that
   needs a Latin secondary line for worker readability. */
function needsTranslit(lang: Language): boolean {
  return lang === 'ar' || lang === 'fa';
}

/* Localized crisis copy. Drives the displaced-person-facing surface
   (title, body fallback when Gemma's locale_aware_message is absent,
   hotline label, play-button label). Dir attribute on the body
   element comes from dirFor(speakerLanguage) — see component below. */
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
  fr: { dir: "ltr", title: "De l'aide est disponible",
        body: "Vous êtes en sécurité ici. Un soutien formé est disponible dès maintenant, dans votre langue. Souhaitez-vous écouter un court message ?",
        hotline: "Ligne d'appui régional FICR",
        play: "Écouter en français" },
  uk: { dir: "ltr", title: "Допомога доступна",
        body: "Ви тут у безпеці. Кваліфікована підтримка доступна прямо зараз, вашою мовою. Бажаєте прослухати коротке повідомлення?",
        hotline: "Регіональна лінія підтримки МФЧХ",
        play: "Прослухати українською" },
};

function CrisisReferralCard({
  workerLanguage,
  speakerLanguage,
  message,
  onResolved,
  onDeEscalated,
}: CrisisReferralCardProps) {
  const copy = CRISIS_COPY[speakerLanguage] || CRISIS_COPY.en;
  const body = message && message.trim() ? message : copy.body;
  const [playing, setPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const speakerDir = dirFor(speakerLanguage);
  const rtl = speakerDir === "rtl";

  React.useEffect(() => {
    const audio = new Audio(`/audio/crisis-calm-${speakerLanguage}.mp3`);
    audio.onended = () => setPlaying(false);
    audioRef.current = audio;
    return () => {
      audio.pause();
      audioRef.current = null;
    };
  }, [speakerLanguage]);

  const handlePlayToggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play().catch(() => {
        // Audio file missing or blocked — fall back to visual-only animation
        setPlaying(true);
        const handle = setTimeout(() => setPlaying(false), 3200);
        return () => clearTimeout(handle);
      });
      setPlaying(true);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Crisis referral"
      dir={dirFor(workerLanguage)}
      className="kin-rise fixed left-1/2 top-[140px] z-30 w-[min(640px,calc(100%-48px))] bg-card border border-line rounded-kin-lg shadow-elevated"
      style={{ transform: "translateX(-50%)" }}
    >
      {/* Operator-facing chrome: red header + subtitle. Stays in
          workerLanguage so the aid worker reads instructions in
          their own UI language regardless of speakerLanguage. */}
      <div className="border-b border-hair px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-kin border border-red/30 bg-red-soft text-red flex items-center justify-center">
          <IconAlert size={18} />
        </div>
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-red">{t('crisis.title', workerLanguage)}</div>
          <div className="text-[14px] text-muted">{t('crisis.subtitle', workerLanguage)}</div>
        </div>
      </div>

      {/* Displaced-person-facing surface — speakerLanguage drives
          BIG title, body (Gemma's locale_aware_message or fallback),
          hotline, play button. dir attribute on this section only. */}
      <div dir={speakerDir} className={`px-6 py-5 ${rtl ? "rtl" : ""}`}>
        <div className="text-[26px] font-semibold text-ink leading-tight">{copy.title}</div>
        <p className="mt-2 text-[17px] text-ink/90 leading-relaxed" style={{ textWrap: "pretty" }}>
          {body}
        </p>

        <div className="mt-4 border border-line rounded-kin p-4 bg-subtle/60">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handlePlayToggle}
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
          <span>{copy.hotline} · +41 22 730 20 51</span>
        </div>
      </div>

      {/* Operator chrome: dismissal buttons. Two explicit logged
          actions, no generic Close (QA-3 lock). Routed through
          t(workerLanguage) so v1.1 worker_language toggle can
          localize without touching this code. */}
      <div className="border-t border-hair bg-subtle/60 px-6 py-3 flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button variant="secondary" onClick={onDeEscalated}>{t('crisis.deescalated', workerLanguage)}</Button>
        <Button variant="confirm" icon={<IconCheck size={16} />} onClick={onResolved}>{t('crisis.referralProvided', workerLanguage)}</Button>
      </div>
    </div>
  );
}

// --- Transliteration match view ------------------------------------------

/* Renders one MiniRecord card. All field VALUES render in
   speaker_language source script (dir-scoped). Field LABELS are
   English LTR worker chrome. Latin secondary lines appear beneath
   non-Latin values when needsTranslit(speakerLanguage) is true. */
function MiniRecord({ record }: { record: MiniRecordData }) {
  const toneBg = record.tone === "warm" ? "bg-[oklch(0.985_0.012_75)]" : "bg-[oklch(0.985_0.006_220)]";
  const valueDir = dirFor(record.speakerLanguage);
  const rtlClass = needsTranslit(record.speakerLanguage) ? "rtl" : "";
  const showSecondary = needsTranslit(record.speakerLanguage);

  return (
    <div className={`flex-1 border border-line rounded-kin-lg ${toneBg}`}>
      <div className="px-5 py-3 border-b border-hair flex items-center justify-between">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">{record.title}</div>
        <Chip icon={<IconLock size={12} />} tone="neutral" className="!bg-white">Local only</Chip>
      </div>
      <div className="px-5 py-4">

        {/* Reporter — LTR label, dir-scoped value */}
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Reporter</div>
        <div className="mt-0.5">
          <div dir={valueDir} className={`text-[15px] text-ink ${rtlClass}`}>{record.reporter}</div>
          {showSecondary && record.reporterLatin && (
            <div dir="ltr" className="text-[12px] text-muted mt-0.5">{record.reporterLatin}</div>
          )}
        </div>

        {/* Missing child — large name in source script, Latin gloss beneath */}
        <div className="mt-4 text-[12px] font-medium uppercase tracking-wider text-muted">Missing child</div>
        <div className="mt-1">
          <div dir={valueDir} className={`text-[20px] font-semibold text-ink ${rtlClass}`}>{record.missingName}</div>
          {showSecondary && record.missingNameLatin && (
            <div dir="ltr" className="text-[13px] text-muted mt-0.5">{record.missingNameLatin}</div>
          )}
          {showSecondary && record.missingNameTranslit && (
            <div dir="ltr" className="text-[12px] text-muted/70">also: {record.missingNameTranslit}</div>
          )}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Age</div>
            {/* Age is a number — no direction needed */}
            <div className="text-[16px] text-ink">{record.age}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last seen</div>
            <div dir={valueDir} className={`text-[16px] text-ink ${rtlClass}`}>{record.lastSeen}</div>
            {showSecondary && record.lastSeenLatin && (
              <div dir="ltr" className="text-[12px] text-muted mt-0.5">{record.lastSeenLatin}</div>
            )}
          </div>
          <div className="col-span-2">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Circumstance</div>
            <div dir={valueDir} className={`text-[16px] text-ink ${rtlClass}`}>{record.circumstance}</div>
            {showSecondary && record.circumstanceLatin && (
              <div dir="ltr" className="text-[12px] text-muted mt-0.5">{record.circumstanceLatin}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* Beat 6 demo data — hand-curated for Mohammed (Tent A) / Mohamad
   (Tent B) match. Source-language fields first; Latin secondary lines
   beneath for worker readability. Matches demo script v3. */
const DEFAULT_RECORD_A: MiniRecordData = {
  title: "Intake A · Session #089",
  tone: "warm",
  reporter: "محمد الأحمد · الأب",
  reporterLatin: "Mohammed Al-Ahmad · Father",
  speakerLanguage: "ar",
  missingName: "محمد",
  missingNameLatin: "Mohammed",
  missingNameTranslit: undefined,
  age: "8",
  lastSeen: "منطقة الحدود · منذ أسبوعين",
  lastSeenLatin: "Border zone · ~2 weeks ago",
  circumstance: "انفصل عن عائلته أثناء الفوضى عند نقطة التفتيش",
  circumstanceLatin: "Separated from family during chaos at the checkpoint",
};

const DEFAULT_RECORD_B: MiniRecordData = {
  title: "Intake B · Session #147",
  tone: "cool",
  reporter: "أمل الأحمد · الأم",
  reporterLatin: "Amal Al-Ahmad · Mother",
  speakerLanguage: "ar",
  missingName: "محمد",
  missingNameLatin: "Mohamad",
  missingNameTranslit: undefined,
  age: "8",
  lastSeen: "منطقة الحدود · منذ أسبوعين تقريباً",
  lastSeenLatin: "Border crossing area · ~2 weeks ago",
  circumstance: "فُقد أثناء حشود اللاجئين عند نقطة العبور",
  circumstanceLatin: "Lost during refugee crowd at the crossing",
};

function TransliterationMatch({ phase, onBack, workerLanguage, recordA, recordB }: TransliterationMatchProps) {
  // 'split'   → two MiniRecord cards side by side, no link drawn
  // 'linking' → Y-shape link animates toward the match card
  // 'merged'  → MATCH CONFIRMED card with unified identity
  const showLink = phase === "linking" || phase === "merged";
  const merged   = phase === "merged";
  const wl: Language = workerLanguage ?? "en";
  const rA = recordA ?? DEFAULT_RECORD_A;
  const rB = recordB ?? DEFAULT_RECORD_B;

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
        <MiniRecord record={rA} />
        <MiniRecord record={rB} />
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

      {/* Merged card — worker_language chrome, Arabic source script at
          top with Mohammed · Mohamad transliterations beneath. No
          kin-rise here (that keyframe is for the absolute-positioned
          crisis modal); kin-merge-pulse provides the entry beat. */}
      {merged && (
        <div className="kin-merge-pulse relative bg-card border border-green/40 rounded-kin-lg">
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
            {/* Arabic source script first — architectural commitment */}
            <div className="mt-2">
              <div dir="rtl" className="rtl text-[28px] font-semibold text-ink">محمد</div>
              <div dir="ltr" className="text-[18px] text-ink mt-1">Mohammed · Mohamad</div>
            </div>

            <div className="mt-5 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Source script</div>
                <div dir="rtl" className="rtl text-[17px] text-ink mt-0.5">محمد</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Phonetic variants</div>
                <div className="text-[15px] text-ink mt-0.5">Mohammed · Mohamad</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Age</div>
                <div className="text-[15px] text-ink mt-0.5">8</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Linked sessions</div>
                <div className="text-[15px] text-ink mt-0.5">#089 (Father) · #147 (Mother)</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last-seen overlap</div>
                <div className="text-[15px] text-ink mt-0.5">Border zone · ~2 weeks ago</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Next step</div>
                <div className="text-[15px] text-ink mt-0.5">Route to caseworker for reunification review</div>
              </div>
            </div>
          </div>
          {/* Cosmetic CTA buttons — wired in Item 11. Rendered in
              worker_language (English). onClick intentionally absent. */}
          <div dir={dirFor(wl)} className="border-t border-hair bg-subtle/40 px-6 py-3 flex flex-col sm:flex-row gap-2 sm:justify-end">
            <Button variant="ghost">Escalate to supervisor</Button>
            <Button variant="secondary">Reject</Button>
            <Button variant="confirm" icon={<IconCheck size={16} />}>Confirm match</Button>
          </div>
        </div>
      )}
    </div>
  );
}

export { CrisisReferralCard, TransliterationMatch, CRISIS_COPY };
