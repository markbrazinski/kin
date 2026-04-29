/* Hook tests — drive real React renders with a MockEventSource factory. */
import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { MockEventSource } from '../test-utils/MockEventSource';
import { useEventStream, type EventSourceFactory } from './useEventStream';
import type { AuditEnvelope } from '../lib/sseEnvelope';

function makeAuditPayload(): AuditEnvelope {
  return {
    type: 'audit_event',
    at: '2026-04-28T12:00:00Z',
    source_device_id: 'tent_a',
    payload: {
      id: '00000000-0000-0000-0000-000000000001',
      at: '2026-04-28T12:00:00Z',
      event_type: 'field_extracted',
      record_ids: ['00000000-0000-0000-0000-000000000099'],
      match_id: null,
      actor: 'kin_system',
      details: {
        field_name: 'full_name_source_script',
        value: 'Carlos',
      },
    },
  };
}

const factory: EventSourceFactory = (url: string) =>
  new MockEventSource(url) as unknown as ReturnType<EventSourceFactory>;

beforeEach(() => {
  MockEventSource.reset();
});

describe('useEventStream', () => {
  it('opens an EventSource on mount and closes on unmount', () => {
    const { unmount } = renderHook(() =>
      useEventStream({ eventSourceFactory: factory }),
    );
    const es = MockEventSource.last();
    expect(es).toBeDefined();
    expect(es!.url).toBe('/intake/stream');
    expect(es!.closed).toBe(false);
    unmount();
    expect(es!.closed).toBe(true);
  });

  it('dispatches an audit_event into state.record', () => {
    const { result } = renderHook(() =>
      useEventStream({ eventSourceFactory: factory }),
    );
    const es = MockEventSource.last()!;
    act(() => {
      es.emit('audit_event', JSON.stringify(makeAuditPayload()));
    });
    expect(result.current.state.record.name).toBe('Carlos');
    expect(result.current.state.auditEvents).toHaveLength(1);
  });

  it('appends a structlog_event into state.structlogEvents', () => {
    const { result } = renderHook(() =>
      useEventStream({ eventSourceFactory: factory }),
    );
    const es = MockEventSource.last()!;
    act(() => {
      es.emit(
        'structlog_event',
        JSON.stringify({
          type: 'structlog_event',
          at: '2026-04-28T12:00:00Z',
          source_device_id: 'tent_a',
          payload: { event: 'tool_call_invoked', tool_name: 'extract_intake_fields' },
        }),
      );
    });
    expect(result.current.state.structlogEvents).toHaveLength(1);
    expect(result.current.state.structlogEvents[0].payload.event).toBe(
      'tool_call_invoked',
    );
  });

  it('reconnects when sourceDeviceId prop changes', () => {
    const { rerender } = renderHook(
      ({ sourceDeviceId }: { sourceDeviceId: string | undefined }) =>
        useEventStream({
          sourceDeviceId,
          eventSourceFactory: factory,
        }),
      { initialProps: { sourceDeviceId: 'tent_a' as string | undefined } },
    );
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe(
      '/intake/stream?source_device_id=tent_a',
    );
    expect(MockEventSource.instances[0].closed).toBe(false);

    rerender({ sourceDeviceId: 'tent_b' });

    expect(MockEventSource.instances).toHaveLength(2);
    /* Old EventSource closed, new one open with new URL. */
    expect(MockEventSource.instances[0].closed).toBe(true);
    expect(MockEventSource.instances[1].url).toBe(
      '/intake/stream?source_device_id=tent_b',
    );
  });

  it('connection lifecycle reflects open and error events', () => {
    const { result } = renderHook(() =>
      useEventStream({ eventSourceFactory: factory }),
    );
    expect(result.current.connection).toBe('connecting');

    const es = MockEventSource.last()!;
    act(() => {
      es.emitOpen();
    });
    expect(result.current.connection).toBe('open');

    act(() => {
      es.emit('error');
    });
    expect(result.current.connection).toBe('error');
  });

});
