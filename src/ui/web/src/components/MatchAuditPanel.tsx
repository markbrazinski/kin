/* S15: Match Audit Panel — slides in from the right at 40% viewport.
   Surfaces source utterances, Whisper translations, and Gemma
   extractions per NodeMatch, plus a streaming Gemma reasoning query.

   Tab "Reasoning" is fully implemented. "Source utterances" and
   "Audit trail" tabs show a coming-soon message — affordances only
   for v1 demo; build-out deferred to polish week.

   Endpoint indicator: localhost:11434 (Ollama native, not /v1 compat).
   Source utterances render dir="rtl" when speaker_language is ar/fa.
*/
import React, { useState, useRef, useEffect } from 'react';
import type { AuditPanelTab, NetworkMatchResult } from '../lib/types';
import { IconX } from './icons';

type Props = {
  intakeIdA: string;
  intakeIdB: string;
  networkResult: NetworkMatchResult;
  speakerLanguage?: string;
  onClose: () => void;
};

const TABS: { id: AuditPanelTab; label: string }[] = [
  { id: 'reasoning', label: 'Reasoning' },
  { id: 'source_utterances', label: 'Source utterances' },
  { id: 'audit_trail', label: 'Audit trail' },
];

const OLLAMA_ENDPOINT = 'localhost:11434';

// Sub-block label constants — exact strings verified by tests.
const LABEL_SOURCE = 'Source Arabic';
const LABEL_WHISPER = 'Whisper translation';
const LABEL_GEMMA = 'Gemma extraction';

type SubBlock = {
  pair_label: string;
  source_utterance_a?: string;
  translation_a?: string;
  extracted_a?: string;
  source_utterance_b?: string;
  translation_b?: string;
  extracted_b?: string;
  match_reasoning?: string;
};

function parseSubBlocks(raw: string): SubBlock[] {
  try {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start === -1 || end === -1) return [];
    const parsed = JSON.parse(raw.slice(start, end + 1));
    return Array.isArray(parsed.node_matches) ? parsed.node_matches : [];
  } catch {
    return [];
  }
}

export function MatchAuditPanel({
  intakeIdA,
  intakeIdB,
  networkResult,
  speakerLanguage,
  onClose,
}: Props) {
  const [activeTab, setActiveTab] = useState<AuditPanelTab>('reasoning');
  const [query, setQuery] = useState('Why did these records match?');
  const [streaming, setStreaming] = useState(false);
  const [rawResponse, setRawResponse] = useState('');
  const subBlocks = parseSubBlocks(rawResponse);
  const inputRef = useRef<HTMLInputElement>(null);
  const responseRef = useRef<HTMLDivElement>(null);

  const isRtl = speakerLanguage === 'ar' || speakerLanguage === 'fa';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (streaming) return;
    setStreaming(true);
    setRawResponse('');

    try {
      const res = await fetch('/demo/audit-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intake_id_a: intakeIdA,
          intake_id_b: intakeIdB,
          query,
        }),
      });
      if (!res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') break;
          try {
            const obj = JSON.parse(payload);
            if (obj.token) setRawResponse(prev => prev + obj.token);
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  // Scroll response area to bottom as tokens arrive.
  useEffect(() => {
    if (responseRef.current) {
      responseRef.current.scrollTop = responseRef.current.scrollHeight;
    }
  }, [rawResponse]);

  return (
    <div
      className="kin-panel-slide-in flex flex-col h-full bg-card border-l border-line"
      data-testid="match-audit-panel"
    >
      {/* Panel header */}
      <div className="px-5 py-3 border-b border-hair flex items-start justify-between gap-3 flex-shrink-0">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted">
            Match audit
          </div>
          <div className="text-[13px] text-ink mt-0.5 font-mono truncate">
            {intakeIdA.slice(0, 8)}… ↔ {intakeIdB.slice(0, 8)}…
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close audit panel"
          className="w-7 h-7 flex items-center justify-center rounded-kin text-muted hover:text-ink hover:bg-subtle transition-colors flex-shrink-0 mt-0.5"
        >
          <IconX size={14} />
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-hair flex-shrink-0">
        <div className="flex px-4 gap-0.5">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={[
                'px-3 py-2.5 text-[13px] font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-green text-ink'
                  : 'border-transparent text-muted hover:text-ink',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeTab === 'reasoning' ? (
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Query input */}
            <form onSubmit={handleSubmit} className="px-4 py-3 border-b border-hair flex gap-2 flex-shrink-0">
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Why did these records match?"
                className="flex-1 text-[13px] border border-line rounded-kin px-3 py-1.5 bg-paper text-ink focus:outline-none focus:ring-1 focus:ring-green/40"
              />
              <button
                type="submit"
                disabled={streaming || !query.trim()}
                className="px-3 py-1.5 text-[13px] font-medium rounded-kin bg-green text-white disabled:opacity-50 hover:bg-green/90 transition-colors"
              >
                {streaming ? '…' : 'Ask'}
              </button>
            </form>

            {/* Streaming response / sub-blocks */}
            <div ref={responseRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
              {subBlocks.length > 0
                ? subBlocks.map((block, i) => (
                    <SubBlockPanel
                      key={i}
                      block={block}
                      isRtl={isRtl}
                    />
                  ))
                : rawResponse && (
                    <pre className="text-[12px] text-ink whitespace-pre-wrap font-mono leading-relaxed">
                      {rawResponse}
                    </pre>
                  )}

              {/* Placeholder when no query has been submitted yet */}
              {!rawResponse && !streaming && (
                <div className="text-[13px] text-muted">
                  Submit a query to see Gemma's reasoning about this match.
                  {networkResult.node_matches.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {networkResult.node_matches.map((nm, i) => (
                        <div key={i} className="text-[12px] font-mono text-muted/80">
                          {nm.name_a} ({nm.role_a}) ↔ {nm.name_b} ({nm.role_b}) — {Math.round(nm.composite_score * 100)}%
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {streaming && !rawResponse && (
                <div className="text-[12px] text-muted animate-pulse">
                  Waiting for response…
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-muted">
              <div className="text-[14px] font-medium mb-1">Coming in v1.1</div>
              <div className="text-[12px]">
                {activeTab === 'source_utterances'
                  ? 'Source utterance replay with timestamp scrubbing.'
                  : 'Full audit event log with structlog replay.'}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Endpoint indicator */}
      <div className="flex-shrink-0 border-t border-hair px-4 py-2 flex items-center justify-end">
        <span className="text-[11px] font-mono text-muted/60" data-testid="endpoint-indicator">
          {OLLAMA_ENDPOINT}
        </span>
      </div>
    </div>
  );
}

// ─── SubBlockPanel ───────────────────────────────────────────────────────────

function SubBlockPanel({ block, isRtl }: { block: SubBlock; isRtl: boolean }) {
  const sourceDir = isRtl ? 'rtl' : undefined;

  return (
    <div className="border border-line rounded-kin-lg overflow-hidden text-[13px]">
      <div className="px-4 py-2.5 bg-subtle/40 border-b border-hair">
        <span className="font-medium text-ink">{block.pair_label}</span>
      </div>

      <div className="divide-y divide-hair">
        {/* Source Arabic */}
        {block.source_utterance_a && (
          <div className="px-4 py-2.5">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-1">
              {LABEL_SOURCE}
            </div>
            <div dir={sourceDir} className={`text-ink ${isRtl ? 'rtl' : ''}`}>
              {block.source_utterance_a}
            </div>
          </div>
        )}

        {/* Whisper translation */}
        {block.translation_a && (
          <div className="px-4 py-2.5">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-1">
              {LABEL_WHISPER}
            </div>
            <div className="text-ink">{block.translation_a}</div>
          </div>
        )}

        {/* Gemma extraction */}
        {block.extracted_a && (
          <div className="px-4 py-2.5">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-1">
              {LABEL_GEMMA}
            </div>
            <div className="text-ink font-mono text-[12px]">{block.extracted_a}</div>
          </div>
        )}

        {/* Match reasoning */}
        {block.match_reasoning && (
          <div className="px-4 py-2.5 bg-subtle/20">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-1">
              Match
            </div>
            <div className="text-ink">{block.match_reasoning}</div>
          </div>
        )}
      </div>
    </div>
  );
}
