/**
 * Local conversation history. The repository interface is the extension point for
 * cloud sync: an account-backed implementation can replace LocalConversationRepository
 * without touching the UI or the store.
 */
import type { Conversation } from '../state/types';

export interface ConversationRepository {
  loadAll(): Conversation[];
  save(conversation: Conversation): void;
  remove(id: string): void;
}

const INDEX_KEY = 'nexa.conversations.index.v1';
const ITEM_PREFIX = 'nexa.conversation.v1.';

export class LocalConversationRepository implements ConversationRepository {
  constructor(private readonly storage: Storage | undefined) {}

  loadAll(): Conversation[] {
    if (!this.storage) return [];
    const ids = this.readIndex();
    const conversations: Conversation[] = [];
    for (const id of ids) {
      const raw = this.storage.getItem(ITEM_PREFIX + id);
      if (!raw) continue;
      try {
        const parsed = JSON.parse(raw) as Conversation;
        if (parsed && parsed.id === id && Array.isArray(parsed.messages))
          conversations.push(sanitize(parsed));
      } catch {
        /* skip corrupted entries */
      }
    }
    return conversations;
  }

  save(conversation: Conversation): void {
    if (!this.storage) return;
    const payload = JSON.stringify(conversation);
    try {
      this.storage.setItem(ITEM_PREFIX + conversation.id, payload);
    } catch {
      // Quota exceeded: drop image thumbnails (the largest items) and try once more.
      try {
        this.storage.setItem(ITEM_PREFIX + conversation.id, JSON.stringify(stripPreviews(conversation)));
      } catch {
        console.warn('Nexa: local storage is full; this conversation could not be saved.');
        return;
      }
    }
    const ids = this.readIndex();
    if (!ids.includes(conversation.id)) this.writeIndex([...ids, conversation.id]);
  }

  remove(id: string): void {
    if (!this.storage) return;
    this.storage.removeItem(ITEM_PREFIX + id);
    this.writeIndex(this.readIndex().filter((existing) => existing !== id));
  }

  private readIndex(): string[] {
    try {
      const ids = JSON.parse(this.storage?.getItem(INDEX_KEY) ?? '[]');
      return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === 'string') : [];
    } catch {
      return [];
    }
  }

  private writeIndex(ids: string[]): void {
    try {
      this.storage?.setItem(INDEX_KEY, JSON.stringify(ids));
    } catch {
      /* ignore */
    }
  }
}

/** A conversation saved mid-stream (tab closed) must not stay "streaming" forever. */
function sanitize(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((m) =>
      m.status === 'streaming'
        ? {
            ...m,
            status: 'stopped',
            tools: m.tools?.map((t) => (t.status === 'running' ? { ...t, status: 'error' } : t)),
          }
        : m,
    ),
  };
}

function stripPreviews(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((m) => ({
      ...m,
      attachments: m.attachments.map(({ previewUrl: _drop, ...rest }) => rest),
    })),
  };
}
