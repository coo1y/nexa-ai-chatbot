/**
 * Pure conversation logic (no React, no I/O) so it is easy to unit test.
 */
import type { ChatMessagePayload, StreamEvent } from '../api/types';
import { randomId } from './clientId';
import type { Attachment, Conversation, Message } from '../state/types';

export const DEFAULT_TITLE = 'New chat';
const TITLE_MAX = 48;

export const newId = (prefix: string) => `${prefix}_${randomId(16)}`;

export function createConversation(now = Date.now()): Conversation {
  return { id: newId('conv'), title: DEFAULT_TITLE, createdAt: now, updatedAt: now, messages: [] };
}

export function createUserMessage(content: string, attachments: Attachment[], now = Date.now()): Message {
  return { id: newId('u'), role: 'user', content, attachments, createdAt: now };
}

export function createAssistantPlaceholder(now = Date.now()): Message {
  return {
    id: newId('a'),
    role: 'assistant',
    content: '',
    attachments: [],
    createdAt: now,
    status: 'streaming',
    tools: [],
    sources: [],
  };
}

export function deriveTitle(text: string, attachments: Attachment[] = []): string {
  const firstLine = text.trim().split('\n')[0]?.replace(/\s+/g, ' ').trim() ?? '';
  const base = firstLine || (attachments[0] ? attachments[0].name : DEFAULT_TITLE);
  return base.length > TITLE_MAX ? `${base.slice(0, TITLE_MAX - 1).trimEnd()}…` : base;
}

/**
 * Messages sent to the backend. Failed/empty assistant turns are left out so a retry does
 * not feed the model its own error state.
 */
export function toRequestMessages(messages: Message[]): ChatMessagePayload[] {
  return messages
    .filter((m) => m.role === 'user' || (m.content.trim() !== '' && m.status !== 'error'))
    .map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      attachments: m.attachments.map((a) => ({ file_id: a.fileId })),
    }));
}

export function lastIndexOfRole(messages: Message[], role: Message['role']): number {
  for (let i = messages.length - 1; i >= 0; i -= 1) if (messages[i].role === role) return i;
  return -1;
}

export function isLatestAssistant(conversation: Conversation, messageId: string): boolean {
  const last = conversation.messages[conversation.messages.length - 1];
  return last?.role === 'assistant' && last.id === messageId;
}

export function isLatestUser(conversation: Conversation, messageId: string): boolean {
  const index = lastIndexOfRole(conversation.messages, 'user');
  return index !== -1 && conversation.messages[index].id === messageId;
}

/** Regenerate: drop the latest assistant response, keep everything before it. */
export function prepareRegenerate(messages: Message[]): Message[] | null {
  const last = messages[messages.length - 1];
  if (!last || last.role !== 'assistant' || last.status === 'streaming') return null;
  return messages.slice(0, -1);
}

/** Edit: replace the latest user message's text and discard everything after it. */
export function prepareEdit(messages: Message[], content: string): Message[] | null {
  const index = lastIndexOfRole(messages, 'user');
  if (index === -1) return null;
  const original = messages[index];
  if (!content.trim() && original.attachments.length === 0) return null;
  return [...messages.slice(0, index), { ...original, content }];
}

/** Reduce one stream event into the assistant message (immutable). */
export function applyStreamEvent(message: Message, { event, data }: StreamEvent): Message {
  switch (event) {
    case 'start':
      return { ...message, serverMessageId: data.message_id, routing: data.routing };
    case 'delta':
      return { ...message, content: message.content + data.text };
    case 'tool_call':
      return {
        ...message,
        tools: [
          ...(message.tools ?? []),
          { id: data.id, name: data.name, label: data.label, input: data.input, status: 'running' },
        ],
      };
    case 'tool_result':
      return {
        ...message,
        tools: (message.tools ?? []).map((t) =>
          t.id === data.id && t.status === 'running'
            ? { ...t, status: data.status, summary: data.summary, durationMs: data.duration_ms }
            : t,
        ),
      };
    case 'sources':
      return { ...message, sources: data.sources };
    case 'safety':
      return { ...message, safety: data };
    case 'error':
      return { ...message, status: 'error', error: data };
    case 'done': {
      const status =
        data.finish_reason === 'blocked' ? 'blocked' : data.finish_reason === 'error' ? 'error' : 'complete';
      return {
        ...message,
        status: message.status === 'error' ? 'error' : status,
        metrics: { ttftMs: data.ttft_ms, durationMs: data.duration_ms },
        // Any tool still "running" when the stream ends did not finish.
        tools: (message.tools ?? []).map((t) => (t.status === 'running' ? { ...t, status: 'error' } : t)),
      };
    }
    default:
      return message;
  }
}

export function finalizeStopped(message: Message): Message {
  if (message.status !== 'streaming') return message;
  return {
    ...message,
    status: 'stopped',
    tools: (message.tools ?? []).map((t) =>
      t.status === 'running' ? { ...t, status: 'error', summary: 'Stopped' } : t,
    ),
  };
}

export function sortConversations(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
}
