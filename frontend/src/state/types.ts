import type { RoutingInfo, Source } from '../api/types';

export interface Attachment {
  fileId: string;
  name: string;
  kind: 'document' | 'image';
  sizeBytes: number;
  pageCount?: number | null;
  /** Small data-URL thumbnail kept in local history for images. */
  previewUrl?: string;
}

export type ToolStatus = 'running' | 'success' | 'error' | 'blocked';

export interface ToolActivity {
  id: string;
  name: string;
  label: string;
  input: Record<string, unknown>;
  status: ToolStatus;
  summary?: string;
  durationMs?: number;
}

export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'error' | 'blocked';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: number;
  attachments: Attachment[];
  // Assistant-only fields
  status?: MessageStatus;
  serverMessageId?: string;
  routing?: RoutingInfo;
  tools?: ToolActivity[];
  sources?: Source[];
  safety?: { action: 'allow_with_guidance' | 'block'; category: string; message: string };
  error?: { code: string; message: string; retryable: boolean };
  feedback?: 'up' | 'down';
  metrics?: { ttftMs: number | null; durationMs: number };
}

export interface Conversation {
  id: string;
  title: string;
  titleEdited?: boolean;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}
