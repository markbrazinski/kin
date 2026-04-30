/* React hook that opens an EventSource against /intake/stream and
   dispatches events into the eventReducer. */
import { useEffect, useReducer, useRef, useCallback } from 'react';
import {
  eventReducer,
  INITIAL_STATE,
  type ConnectionState,
  type EventStreamState,
} from '../state/eventReducer';
import type {
  AuditEnvelope,
  StructlogEnvelope,
} from '../lib/sseEnvelope';

export type EventSourceLike = {
  url: string;
  readyState: number;
  addEventListener(name: string, listener: (e: { data?: string }) => void): void;
  removeEventListener?(name: string, listener: (e: { data?: string }) => void): void;
  close(): void;
};

export type EventSourceFactory = (url: string) => EventSourceLike;

const defaultFactory: EventSourceFactory = (url) =>
  new EventSource(url) as unknown as EventSourceLike;

export type UseEventStreamOptions = {
  sourceDeviceId?: string;
  basePath?: string;
  eventSourceFactory?: EventSourceFactory;
  /* When false, no EventSource is opened. Used by App.tsx to suppress the
     unfiltered App-level subscription while in split view, where each
     IntakePanel owns its own filtered stream. Default true preserves the
     existing single-view behavior. */
  enabled?: boolean;
};

export type UseEventStreamResult = {
  state: EventStreamState;
  connection: ConnectionState;
  reset: () => void;
  clearIntakeId: () => void;
};

function buildUrl(basePath: string, sourceDeviceId?: string): string {
  if (!sourceDeviceId) return basePath;
  const sep = basePath.includes('?') ? '&' : '?';
  return `${basePath}${sep}source_device_id=${encodeURIComponent(sourceDeviceId)}`;
}

export function useEventStream(
  opts: UseEventStreamOptions = {},
): UseEventStreamResult {
  const {
    sourceDeviceId,
    basePath = '/intake/stream',
    eventSourceFactory = defaultFactory,
    enabled = true,
  } = opts;

  const [state, dispatch] = useReducer(eventReducer, INITIAL_STATE);

  /* Stable refs for the listener closures so we can safely reopen the
     EventSource on prop change without stale handlers. */
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  useEffect(() => {
    if (!enabled) return;
    const url = buildUrl(basePath, sourceDeviceId);
    dispatchRef.current({ type: 'connection', value: 'connecting' });
    const es = eventSourceFactory(url);

    const onOpen = () => {
      dispatchRef.current({ type: 'connection', value: 'open' });
    };
    const onError = () => {
      dispatchRef.current({ type: 'connection', value: 'error' });
    };
    const onAudit = (e: { data?: string }) => {
      if (!e.data) return;
      try {
        const env = JSON.parse(e.data) as AuditEnvelope;
        dispatchRef.current({ type: 'envelope', envelope: env });
      } catch {
        /* Drop malformed; sse-starlette frames are line-oriented JSON. */
      }
    };
    const onStructlog = (e: { data?: string }) => {
      if (!e.data) return;
      try {
        const env = JSON.parse(e.data) as StructlogEnvelope;
        dispatchRef.current({ type: 'envelope', envelope: env });
      } catch {
        /* Drop malformed. */
      }
    };

    es.addEventListener('open', onOpen);
    es.addEventListener('error', onError);
    es.addEventListener('audit_event', onAudit);
    es.addEventListener('structlog_event', onStructlog);

    return () => {
      es.removeEventListener?.('open', onOpen);
      es.removeEventListener?.('error', onError);
      es.removeEventListener?.('audit_event', onAudit);
      es.removeEventListener?.('structlog_event', onStructlog);
      es.close();
      dispatchRef.current({ type: 'connection', value: 'closed' });
    };
  }, [sourceDeviceId, basePath, eventSourceFactory, enabled]);

  const reset = useCallback(() => {
    dispatchRef.current({ type: 'reset' });
  }, []);

  const clearIntakeId = useCallback(() => {
    dispatchRef.current({ type: 'clear_intake_id' });
  }, []);

  return {
    state,
    connection: state.connection,
    reset,
    clearIntakeId,
  };
}
