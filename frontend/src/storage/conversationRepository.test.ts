import type { Conversation } from '../state/types';
import { LocalConversationRepository } from './conversationRepository';

const conversation = (id: string, extra: Partial<Conversation> = {}): Conversation => ({
  id,
  title: `Chat ${id}`,
  createdAt: 1,
  updatedAt: 1,
  messages: [],
  ...extra,
});

describe('LocalConversationRepository', () => {
  it('saves, loads and removes conversations', () => {
    const repo = new LocalConversationRepository(localStorage);
    repo.save(conversation('a'));
    repo.save(conversation('b'));
    repo.save(conversation('a', { title: 'Renamed' }));
    expect(repo.loadAll().map((c) => c.title)).toEqual(['Renamed', 'Chat b']);
    repo.remove('a');
    expect(repo.loadAll().map((c) => c.id)).toEqual(['b']);
  });

  it('recovers conversations saved mid-stream as stopped', () => {
    const repo = new LocalConversationRepository(localStorage);
    repo.save(
      conversation('s', {
        messages: [
          {
            id: 'm',
            role: 'assistant',
            content: 'partial',
            attachments: [],
            createdAt: 1,
            status: 'streaming',
            tools: [{ id: 't', name: 'x', label: 'X', input: {}, status: 'running' }],
          },
        ],
      }),
    );
    const [loaded] = repo.loadAll();
    expect(loaded.messages[0].status).toBe('stopped');
    expect(loaded.messages[0].tools?.[0].status).toBe('error');
  });

  it('skips corrupted entries', () => {
    const repo = new LocalConversationRepository(localStorage);
    repo.save(conversation('ok'));
    localStorage.setItem('nexa.conversations.index.v1', JSON.stringify(['ok', 'broken']));
    localStorage.setItem('nexa.conversation.v1.broken', '{not json');
    expect(repo.loadAll().map((c) => c.id)).toEqual(['ok']);
  });

  it('drops image previews when storage is full', () => {
    const store = new Map<string, string>();
    const storage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        if (v.includes('data:image')) throw new DOMException('full', 'QuotaExceededError');
        store.set(k, v);
      },
      removeItem: (k: string) => store.delete(k),
    } as unknown as Storage;
    const repo = new LocalConversationRepository(storage);
    repo.save(
      conversation('img', {
        messages: [
          {
            id: 'u',
            role: 'user',
            content: 'x',
            createdAt: 1,
            attachments: [
              {
                fileId: 'f',
                name: 'a.png',
                kind: 'image',
                sizeBytes: 1,
                previewUrl: 'data:image/jpeg;base64,AAA',
              },
            ],
          },
        ],
      }),
    );
    const [loaded] = repo.loadAll();
    expect(loaded.messages[0].attachments[0].previewUrl).toBeUndefined();
  });

  it('works without storage (private mode)', () => {
    const repo = new LocalConversationRepository(undefined);
    repo.save(conversation('x'));
    expect(repo.loadAll()).toEqual([]);
  });
});
