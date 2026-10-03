import type { StreamEvent } from '../api/types';

export function sseBody(events: StreamEvent[], chunkSize = 7): ReadableStream<Uint8Array> {
  const text = events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('');
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new ReadableStream({
    pull(controller) {
      if (offset >= bytes.length) {
        controller.close();
        return;
      }
      controller.enqueue(bytes.slice(offset, offset + chunkSize));
      offset += chunkSize;
    },
  });
}

export const startEvent = (capability: 'fast' | 'reasoning' | 'vision' = 'fast'): StreamEvent => ({
  event: 'start',
  data: {
    request_id: 'req-1',
    message_id: 'msg_server_1',
    routing: { mode: 'auto', capability, model: 'test-model', reason: 'general request' },
  },
});

export const doneEvent = (finish: 'stop' | 'error' | 'blocked' | 'length' = 'stop'): StreamEvent => ({
  event: 'done',
  data: {
    finish_reason: finish,
    usage: { prompt_tokens: 10, completion_tokens: 5 },
    ttft_ms: 120,
    duration_ms: 900,
  },
});

export const delta = (text: string): StreamEvent => ({ event: 'delta', data: { text } });

export function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
