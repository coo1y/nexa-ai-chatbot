/**
 * Chat state and actions. The API client and the repository are injected, so the whole
 * send / stream / stop / regenerate / edit / retry flow is unit-testable without a server.
 */
import { createStore, type StoreApi } from 'zustand/vanilla';
import { useStore } from 'zustand';

import { api as defaultApi, ApiError, isAbortError, type ApiClient } from '../api';
import type { CapabilitiesResponse, CapabilityChoice, StreamEvent } from '../api/types';
import { safeLocalStorage } from '../lib/clientId';
import {
  applyStreamEvent,
  createAssistantPlaceholder,
  createConversation,
  createUserMessage,
  DEFAULT_TITLE,
  deriveTitle,
  finalizeStopped,
  prepareEdit,
  prepareRegenerate,
  toRequestMessages,
} from '../lib/conversation';
import { LocalConversationRepository, type ConversationRepository } from '../storage/conversationRepository';
import type { Attachment, Conversation, Message } from './types';

const DELTA_FLUSH_MS = 32;

export interface ChatState {
  conversations: Record<string, Conversation>;
  activeId: string | null;
  capability: CapabilityChoice;
  webSearch: boolean;
  streaming: { conversationId: string; messageId: string } | null;
  sourcesFor: { messageId: string; highlight: number | null } | null;
  capabilities: CapabilitiesResponse | null;
  notice: string | null;
}

export interface ChatActions {
  loadCapabilities(): Promise<void>;
  newConversation(): string;
  selectConversation(id: string): void;
  renameConversation(id: string, title: string): void;
  deleteConversation(id: string): void;
  sendMessage(text: string, attachments?: Attachment[]): Promise<void>;
  stopGeneration(): void;
  regenerate(): Promise<void>;
  editLastUserMessage(text: string): Promise<void>;
  retry(): Promise<void>;
  setFeedback(messageId: string, rating: 'up' | 'down'): Promise<void>;
  setCapability(capability: CapabilityChoice): void;
  setWebSearch(enabled: boolean): void;
  openSources(messageId: string, highlight?: number | null): void;
  closeSources(): void;
  dismissNotice(): void;
}

export type ChatStore = StoreApi<ChatState & ChatActions>;

export interface ChatStoreDeps {
  api: Pick<ApiClient, 'streamChat' | 'submitFeedback' | 'deleteFile' | 'getCapabilities'>;
  repository: ConversationRepository;
}

export function createChatStore({ api, repository }: ChatStoreDeps): ChatStore {
  let controller: AbortController | null = null;

  const initial = repository.loadAll();
  const conversations = Object.fromEntries(initial.map((c) => [c.id, c]));
  const mostRecent = [...initial].sort((a, b) => b.updatedAt - a.updatedAt)[0];

  return createStore<ChatState & ChatActions>()((set, get) => {
    const update = (id: string, fn: (c: Conversation) => Conversation, persist = false) => {
      const current = get().conversations[id];
      if (!current) return;
      const next = fn(current);
      set({ conversations: { ...get().conversations, [id]: next } });
      if (persist) repository.save(next);
    };

    const updateMessage = (
      conversationId: string,
      messageId: string,
      fn: (m: Message) => Message,
      persist = false,
    ) =>
      update(
        conversationId,
        (c) => ({ ...c, messages: c.messages.map((m) => (m.id === messageId ? fn(m) : m)) }),
        persist,
      );

    /** Stream a response for the conversation's current messages into a new placeholder. */
    async function generate(conversationId: string): Promise<void> {
      const conversation = get().conversations[conversationId];
      if (!conversation || get().streaming) return;
      const placeholder = createAssistantPlaceholder();
      const requestMessages = toRequestMessages(conversation.messages);
      update(
        conversationId,
        (c) => ({ ...c, messages: [...c.messages, placeholder], updatedAt: Date.now() }),
        true,
      );
      set({ streaming: { conversationId, messageId: placeholder.id } });

      controller = new AbortController();
      let pendingText = '';
      let flushTimer: ReturnType<typeof setTimeout> | null = null;
      const flush = () => {
        if (flushTimer) clearTimeout(flushTimer);
        flushTimer = null;
        if (!pendingText) return;
        const text = pendingText;
        pendingText = '';
        updateMessage(conversationId, placeholder.id, (m) => ({ ...m, content: m.content + text }));
      };
      const onEvent = (event: StreamEvent) => {
        if (event.event === 'delta') {
          // Batch token deltas so long answers don't re-render on every token.
          pendingText += event.data.text;
          flushTimer ??= setTimeout(flush, DELTA_FLUSH_MS);
          return;
        }
        flush();
        updateMessage(conversationId, placeholder.id, (m) => applyStreamEvent(m, event));
      };

      const webSearch = get().webSearch;
      if (webSearch) set({ webSearch: false }); // an explicit search applies to this message only
      try {
        await api.streamChat(
          {
            conversation_id: conversationId,
            messages: requestMessages,
            capability: get().capability,
            web_search: webSearch,
          },
          { signal: controller.signal, onEvent },
        );
        flush();
        updateMessage(conversationId, placeholder.id, (m) =>
          // Stream ended without a "done" event (connection dropped).
          m.status === 'streaming'
            ? {
                ...m,
                status: 'error',
                error: {
                  code: 'stream_interrupted',
                  message: 'The response was interrupted.',
                  retryable: true,
                },
              }
            : m,
        );
      } catch (error) {
        flush();
        if (isAbortError(error)) {
          updateMessage(conversationId, placeholder.id, finalizeStopped);
        } else {
          const message =
            error instanceof ApiError ? error.message : 'Something went wrong. Please try again.';
          const code = error instanceof ApiError ? error.code : 'unknown_error';
          updateMessage(conversationId, placeholder.id, (m) => ({
            ...m,
            status: 'error',
            error: { code, message, retryable: true },
          }));
        }
      } finally {
        if (flushTimer) clearTimeout(flushTimer);
        controller = null;
        set({ streaming: null });
        update(conversationId, (c) => ({ ...c, updatedAt: Date.now() }), true);
      }
    }

    return {
      conversations,
      activeId: mostRecent?.id ?? null,
      capability: 'auto',
      webSearch: false,
      streaming: null,
      sourcesFor: null,
      capabilities: null,
      notice: null,

      async loadCapabilities() {
        try {
          set({ capabilities: await api.getCapabilities() });
        } catch {
          /* defaults are used; chat requests will surface connectivity problems */
        }
      },

      newConversation() {
        const active = get().activeId ? get().conversations[get().activeId!] : undefined;
        if (active && active.messages.length === 0) return active.id; // reuse the empty chat
        const conversation = createConversation();
        set({
          conversations: { ...get().conversations, [conversation.id]: conversation },
          activeId: conversation.id,
          sourcesFor: null,
        });
        return conversation.id;
      },

      selectConversation(id) {
        if (get().conversations[id]) set({ activeId: id, sourcesFor: null });
      },

      renameConversation(id, title) {
        const trimmed = title.trim().slice(0, 120);
        if (!trimmed) return;
        update(id, (c) => ({ ...c, title: trimmed, titleEdited: true }), true);
      },

      deleteConversation(id) {
        const conversation = get().conversations[id];
        if (!conversation) return;
        if (get().streaming?.conversationId === id) controller?.abort();
        const rest = { ...get().conversations };
        delete rest[id];
        const nextActive =
          get().activeId === id
            ? (Object.values(rest).sort((a, b) => b.updatedAt - a.updatedAt)[0]?.id ?? null)
            : get().activeId;
        set({ conversations: rest, activeId: nextActive, sourcesFor: null });
        repository.remove(id);
        // Best effort: remove this conversation's uploads from the server too.
        for (const message of conversation.messages) {
          for (const attachment of message.attachments)
            api.deleteFile(attachment.fileId).catch(() => undefined);
        }
      },

      async sendMessage(text, attachments = []) {
        if (get().streaming) return;
        const content = text.trim();
        if (!content && attachments.length === 0) return;
        let id = get().activeId;
        if (!id || !get().conversations[id]) id = get().newConversation();
        const message = createUserMessage(content, attachments);
        update(
          id,
          (c) => ({
            ...c,
            title:
              c.messages.length === 0 && !c.titleEdited
                ? deriveTitle(content, attachments)
                : c.title || DEFAULT_TITLE,
            messages: [...c.messages, message],
            updatedAt: Date.now(),
          }),
          true,
        );
        await generate(id);
      },

      stopGeneration() {
        controller?.abort();
      },

      async regenerate() {
        const id = get().activeId;
        const conversation = id ? get().conversations[id] : undefined;
        if (!id || !conversation || get().streaming) return;
        const messages = prepareRegenerate(conversation.messages);
        if (!messages) return;
        update(id, (c) => ({ ...c, messages }), true);
        await generate(id);
      },

      async editLastUserMessage(text) {
        const id = get().activeId;
        const conversation = id ? get().conversations[id] : undefined;
        if (!id || !conversation || get().streaming) return;
        const messages = prepareEdit(conversation.messages, text.trim());
        if (!messages) return;
        update(id, (c) => ({ ...c, messages }), true);
        await generate(id);
      },

      async retry() {
        await get().regenerate();
      },

      async setFeedback(messageId, rating) {
        const id = get().activeId;
        const message = id ? get().conversations[id]?.messages.find((m) => m.id === messageId) : undefined;
        if (!id || !message || message.role !== 'assistant') return;
        const previous = message.feedback;
        updateMessage(id, messageId, (m) => ({ ...m, feedback: rating }), true);
        try {
          await api.submitFeedback({
            conversation_id: id,
            message_id: message.serverMessageId ?? message.id,
            rating,
            capability: message.routing?.capability ?? null,
            model: message.routing?.model ?? null,
          });
        } catch {
          // Feedback must never interrupt the conversation: revert quietly and show a hint.
          updateMessage(id, messageId, (m) => ({ ...m, feedback: previous }), true);
          set({ notice: "Couldn't send feedback. Please try again later." });
        }
      },

      setCapability(capability) {
        set({ capability });
      },
      setWebSearch(enabled) {
        set({ webSearch: enabled });
      },
      openSources(messageId, highlight = null) {
        set({ sourcesFor: { messageId, highlight } });
      },
      closeSources() {
        set({ sourcesFor: null });
      },
      dismissNotice() {
        set({ notice: null });
      },
    };
  });
}

export const chatStore = createChatStore({
  api: defaultApi,
  repository: new LocalConversationRepository(safeLocalStorage()),
});

export function useChat<T>(selector: (state: ChatState & ChatActions) => T): T {
  return useStore(chatStore, selector);
}

export function useActiveConversation(): Conversation | null {
  return useChat((s) => (s.activeId ? (s.conversations[s.activeId] ?? null) : null));
}
