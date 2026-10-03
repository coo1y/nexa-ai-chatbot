import type { StreamEvent } from '../api/types';
import type { Message } from '../state/types';
import {
  applyStreamEvent,
  createAssistantPlaceholder,
  deriveTitle,
  finalizeStopped,
  prepareEdit,
  prepareRegenerate,
  toRequestMessages,
} from './conversation';
import { delta, doneEvent, startEvent } from '../test/helpers';

const user = (content: string, id = `u-${content}`): Message => ({
  id,
  role: 'user',
  content,
  attachments: [],
  createdAt: 0,
});
const assistant = (content: string, extra: Partial<Message> = {}): Message => ({
  id: `a-${content}`,
  role: 'assistant',
  content,
  attachments: [],
  createdAt: 0,
  status: 'complete',
  ...extra,
});

describe('deriveTitle', () => {
  it('uses the first line, collapsed and truncated', () => {
    expect(deriveTitle('  Hello   world \nsecond line')).toBe('Hello world');
    expect(deriveTitle('x'.repeat(100))).toHaveLength(48);
    expect(deriveTitle('', [{ fileId: 'f', name: 'report.pdf', kind: 'document', sizeBytes: 1 }])).toBe(
      'report.pdf',
    );
  });
});

describe('toRequestMessages', () => {
  it('maps attachments and drops failed or empty assistant turns', () => {
    const messages: Message[] = [
      { ...user('look'), attachments: [{ fileId: 'f1', name: 'a.png', kind: 'image', sizeBytes: 1 }] },
      assistant('', { status: 'error' }),
      assistant('partial', { status: 'error' }),
      assistant('stopped answer', { status: 'stopped' }),
      user('again'),
    ];
    expect(toRequestMessages(messages)).toEqual([
      { id: 'u-look', role: 'user', content: 'look', attachments: [{ file_id: 'f1' }] },
      { id: 'a-stopped answer', role: 'assistant', content: 'stopped answer', attachments: [] },
      { id: 'u-again', role: 'user', content: 'again', attachments: [] },
    ]);
  });
});

describe('regenerate and edit', () => {
  const history = [user('q1'), assistant('a1'), user('q2'), assistant('a2')];

  it('regenerate removes only the latest assistant message', () => {
    expect(prepareRegenerate(history)?.map((m) => m.content)).toEqual(['q1', 'a1', 'q2']);
    expect(prepareRegenerate([user('q')])).toBeNull();
    expect(prepareRegenerate([user('q'), assistant('a', { status: 'streaming' })])).toBeNull();
  });

  it('edit replaces the latest user message and discards what follows', () => {
    const edited = prepareEdit(history, 'q2 fixed');
    expect(edited?.map((m) => m.content)).toEqual(['q1', 'a1', 'q2 fixed']);
    expect(edited?.[2].id).toBe('u-q2');
    expect(prepareEdit(history, '   ')).toBeNull();
  });
});

describe('applyStreamEvent', () => {
  const run = (events: StreamEvent[]) => events.reduce(applyStreamEvent, createAssistantPlaceholder());

  it('builds a complete message from a stream', () => {
    const message = run([
      startEvent('reasoning'),
      {
        event: 'tool_call',
        data: { id: 't1', name: 'web_search', label: 'Web search', input: { query: 'x' } },
      },
      {
        event: 'tool_result',
        data: { id: 't1', name: 'web_search', status: 'success', summary: 'Found 2', duration_ms: 40 },
      },
      {
        event: 'sources',
        data: {
          sources: [{ id: 1, title: 'T', url: 'https://a.example', domain: 'a.example', snippet: '' }],
        },
      },
      delta('Answer '),
      delta('[1]'),
      doneEvent(),
    ]);
    expect(message).toMatchObject({
      status: 'complete',
      content: 'Answer [1]',
      serverMessageId: 'msg_server_1',
      routing: { capability: 'reasoning' },
      metrics: { ttftMs: 120, durationMs: 900 },
    });
    expect(message.tools).toEqual([
      {
        id: 't1',
        name: 'web_search',
        label: 'Web search',
        input: { query: 'x' },
        status: 'success',
        summary: 'Found 2',
        durationMs: 40,
      },
    ]);
    expect(message.sources).toHaveLength(1);
  });

  it('keeps the error state when done follows an error', () => {
    const message = run([
      startEvent(),
      { event: 'error', data: { code: 'upstream_unavailable', message: 'Try again', retryable: true } },
      doneEvent('error'),
    ]);
    expect(message.status).toBe('error');
    expect(message.error?.retryable).toBe(true);
  });

  it('marks blocked responses and records the safety notice', () => {
    const message = run([
      startEvent(),
      { event: 'safety', data: { action: 'block', category: 'malware', message: "I can't help with that." } },
      delta("I can't help with that."),
      doneEvent('blocked'),
    ]);
    expect(message.status).toBe('blocked');
    expect(message.safety?.category).toBe('malware');
  });

  it('closes unfinished tools when stopped or done', () => {
    const running = run([
      startEvent(),
      { event: 'tool_call', data: { id: 't', name: 'calculator', label: 'Calc', input: {} } },
    ]);
    expect(finalizeStopped(running)).toMatchObject({
      status: 'stopped',
      tools: [{ status: 'error', summary: 'Stopped' }],
    });
    expect(applyStreamEvent(running, doneEvent()).tools?.[0].status).toBe('error');
  });
});
