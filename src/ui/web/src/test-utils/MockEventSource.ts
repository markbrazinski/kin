/* Minimal EventSource test double.

   jsdom 25 does not ship EventSource. Production code uses the real
   browser EventSource; tests inject this mock via the hook's
   `eventSourceFactory` option. The mock implements only the surface
   the hook actually uses:
     - constructor(url)
     - addEventListener(eventName, listener)
     - close()
     - readyState

   The static `instances` array lets tests grab the most-recent
   instance and `emit` synthetic events into it.
*/

export type MockEventListener = (event: { data?: string }) => void;

export class MockEventSource {
  static instances: MockEventSource[] = [];
  static reset(): void {
    MockEventSource.instances.forEach((i) => i.close());
    MockEventSource.instances = [];
  }
  static last(): MockEventSource | undefined {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }

  url: string;
  readyState: 0 | 1 | 2 = 0; // 0=connecting, 1=open, 2=closed
  closed = false;

  private listeners: Map<string, MockEventListener[]> = new Map();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: MockEventListener): void {
    const arr = this.listeners.get(name) ?? [];
    arr.push(listener);
    this.listeners.set(name, arr);
  }

  removeEventListener(name: string, listener: MockEventListener): void {
    const arr = this.listeners.get(name);
    if (!arr) return;
    const idx = arr.indexOf(listener);
    if (idx >= 0) arr.splice(idx, 1);
  }

  close(): void {
    this.readyState = 2;
    this.closed = true;
  }

  /* Test-side helpers. */
  emit(name: string, data?: string): void {
    const arr = this.listeners.get(name);
    if (!arr) return;
    for (const fn of arr) fn({ data });
  }

  emitOpen(): void {
    this.readyState = 1;
    this.emit('open');
  }
}
