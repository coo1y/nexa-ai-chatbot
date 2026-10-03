import { ApiError } from '../api/client';
import type { ChatRequest, StreamEvent } from '../api/types';
import { LocalConversationRepository } from '../storage/conversationRepository';
import { createChatStore, type ChatStoreDeps } from './chatStore';
import { deferred, delta, doneEvent, startEvent } from '../test/helpers';

type StreamImpl = (
  payload: ChatRequest,
  opts: { signal?: AbortSignal; onEvent: (e: StreamEvent) => void },
) => Promise<void>;

function setup(streamImpl?: StreamImpl) {
  const requests: ChatRequest[] = [];
  const api = {
    streamChat: vi.fn<StreamImpl>(async (payload, opts) => {
      requests.push(structuredClone(payload));
      if (streamImpl) return streamImpl(payload, opts);
      [startEvent(), delta('Hello'), delta(' world'), doneEvent()].forEach(opts.onEvent);
    }),
    submitFeedback: vi.fn().mockResolvedValue({}),
    deleteFile: vi.fn().mockResolvedValue(undefined),
    getCapabilities: vi.fn().mockResolvedValue(null),
  } satisfies ChatStoreDeps['api'];
  const repository = new LocalConversationRepository(localStorage);
  const store = createChatStore({ api, repository });
  const active = () => store.getState().conversations[store.getState().activeId!];
  return { store, api, requests, repository, active };
}

describe('chat store', () => {
  it('sends a message, streams the reply and persists locally', async () => {
    const { store, requests, repository, active } = setup();
    await store.getState().sendMessage('  Hi there  ');
    const conversation = active();
    expect(conversation.title).toBe('Hi there');
    expect(conversation.messages.map((m) => [m.role, m.content, m.status])).toEqual([
      ['user', 'Hi there', undefined],
      ['assistant', 'Hello world', 'complete'],
    ]);
    expect(conversation.messages[1].serverMessageId).toBe('msg_server_1');
    expect(requests[0]).toMatchObject({
      capability: 'auto',
      web_search: false,
      messages: [{ role: 'user', content: 'Hi there' }],
    });
    expect(store.getState().streaming).toBeNull();
    expect(repository.loadAll()[0].messages).toHaveLength(2);
  });

  it('passes capability and web search choices to the API', async () => {
    const { store, requests } = setup();
    store.getState().setCapability('reasoning');
    store.getState().setWebSearch(true);
    await store.getState().sendMessage('deep question');
    expect(requests[0]).toMatchObject({ capability: 'reasoning', web_search: true });
    // Search is per message; the capability choice persists.
    expect(store.getState()).toMatchObject({ webSearch: false, capability: 'reasoning' });
    await store.getState().sendMessage('follow-up');
    expect(requests[1]).toMatchObject({ capability: 'reasoning', web_search: false });
  });

  it('ignores empty messages and concurrent sends', async () => {
    const gate = deferred();
    const { store, api } = setup(async (_p, { onEvent }) => {
      onEvent(startEvent());
      await gate.promise;
      onEvent(doneEvent());
    });
    await store.getState().sendMessage('   ');
    expect(api.streamChat).not.toHaveBeenCalled();
    const first = store.getState().sendMessage('one');
    await store.getState().sendMessage('two');
    gate.resolve();
    await first;
    expect(api.streamChat).toHaveBeenCalledTimes(1);
  });

  it('stops generation and keeps the partial answer', async () => {
    const { store, active } = setup(
      (_payload, { signal, onEvent }) =>
        new Promise((_resolve, reject) => {
          onEvent(startEvent());
          onEvent(delta('Partial'));
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        }),
    );
    const pending = store.getState().sendMessage('long story');
    await vi.waitFor(() => expect(store.getState().streaming).not.toBeNull());
    store.getState().stopGeneration();
    await pending;
    const reply = active().messages[1];
    expect(reply.status).toBe('stopped');
    expect(reply.content).toBe('Partial');
    expect(store.getState().streaming).toBeNull();
  });

  it('shows a friendly retryable error and retries', async () => {
    let attempt = 0;
    const { store, requests, active } = setup(async (_p, { onEvent }) => {
      attempt += 1;
      if (attempt === 1) throw new ApiError("Can't reach Nexa right now.", 0, 'network_error');
      [startEvent(), delta('Recovered'), doneEvent()].forEach(onEvent);
    });
    await store.getState().sendMessage('hello');
    expect(active().messages[1]).toMatchObject({
      status: 'error',
      error: { message: "Can't reach Nexa right now.", retryable: true },
    });

    await store.getState().retry();
    expect(active().messages.map((m) => m.content)).toEqual(['hello', 'Recovered']);
    // The failed attempt is not sent back to the model.
    expect(requests[1].messages).toEqual(requests[0].messages);
  });

  it('marks a stream that ends without "done" as interrupted', async () => {
    const { store, active } = setup(async (_p, { onEvent }) => {
      onEvent(startEvent());
      onEvent(delta('cut'));
    });
    await store.getState().sendMessage('x');
    expect(active().messages[1]).toMatchObject({ status: 'error', error: { code: 'stream_interrupted' } });
  });

  it('regenerates the latest response from the same context', async () => {
    const { store, requests, active } = setup();
    await store.getState().sendMessage('first');
    const firstReplyId = active().messages[1].id;
    await store.getState().regenerate();
    expect(active().messages).toHaveLength(2);
    expect(active().messages[1].id).not.toBe(firstReplyId);
    expect(requests[1].messages).toEqual(requests[0].messages);
  });

  it('edits the latest user message and regenerates from there', async () => {
    const { store, requests, active } = setup();
    await store.getState().sendMessage('q1');
    await store.getState().sendMessage('q2 with typo');
    await store.getState().editLastUserMessage('q2 fixed');
    expect(active().messages.map((m) => m.content)).toEqual(['q1', 'Hello world', 'q2 fixed', 'Hello world']);
    expect(requests[2].messages.map((m) => m.content)).toEqual(['q1', 'Hello world', 'q2 fixed']);
  });

  it('records feedback and reverts quietly on failure', async () => {
    const { store, api, active } = setup();
    await store.getState().sendMessage('hi');
    const reply = active().messages[1];
    await store.getState().setFeedback(reply.id, 'up');
    expect(api.submitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        message_id: 'msg_server_1',
        rating: 'up',
        capability: 'fast',
        model: 'test-model',
      }),
    );
    expect(active().messages[1].feedback).toBe('up');

    api.submitFeedback.mockRejectedValueOnce(new Error('offline'));
    await store.getState().setFeedback(reply.id, 'down');
    expect(active().messages[1].feedback).toBe('up');
    expect(store.getState().notice).toMatch(/Couldn't send feedback/);
  });

  it('manages conversations: new, rename, select, delete (with file cleanup)', async () => {
    const { store, api, repository } = setup();
    await store
      .getState()
      .sendMessage('first chat', [{ fileId: 'file-1', name: 'a.pdf', kind: 'document', sizeBytes: 3 }]);
    const firstId = store.getState().activeId!;

    const secondId = store.getState().newConversation();
    expect(secondId).not.toBe(firstId);
    expect(store.getState().newConversation()).toBe(secondId); // empty chat is reused
    await store.getState().sendMessage('second chat');

    store.getState().renameConversation(firstId, '  Project notes  ');
    expect(store.getState().conversations[firstId]).toMatchObject({
      title: 'Project notes',
      titleEdited: true,
    });
    store.getState().renameConversation(firstId, '   ');
    expect(store.getState().conversations[firstId].title).toBe('Project notes');

    store.getState().selectConversation(firstId);
    expect(store.getState().activeId).toBe(firstId);

    store.getState().deleteConversation(firstId);
    expect(store.getState().conversations[firstId]).toBeUndefined();
    expect(store.getState().activeId).toBe(secondId);
    expect(api.deleteFile).toHaveBeenCalledWith('file-1');
    expect(repository.loadAll().map((c) => c.id)).toEqual([secondId]);
  });

  it('restores the most recent conversation from local storage', async () => {
    const { store } = setup();
    await store.getState().sendMessage('remember me');
    const again = setup();
    expect(again.active().messages[0].content).toBe('remember me');
    expect(store.getState().activeId).toBe(again.store.getState().activeId);
  });

  it('keeps long conversations entirely in context (server trims)', async () => {
    const { store, requests } = setup();
    for (let i = 0; i < 30; i += 1) await store.getState().sendMessage(`message ${i}`);
    expect(requests.at(-1)!.messages).toHaveLength(59);
  });
});
