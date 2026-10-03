/**
 * The single place where the frontend talks to the backend.
 * Components and stores call these typed functions; nothing else uses fetch().
 */
import { parseSse } from './sse';
import {
  STREAM_EVENT_NAMES,
  type CapabilitiesResponse,
  type ChatRequest,
  type ErrorResponse,
  type FeedbackRequest,
  type FeedbackResponse,
  type FileMeta,
  type HealthResponse,
  type StreamEvent,
  type StreamEventName,
} from './types';

export const FRIENDLY_NETWORK_ERROR = "Can't reach Nexa right now. Check your connection and try again.";
export const FRIENDLY_SERVER_ERROR = 'Something went wrong. Please try again.';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(message: string, status: number, code: string, requestId: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }

  /** Network failures, rate limits and 5xx responses are worth a retry. */
  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  getClientId: () => string;
  fetchImpl?: typeof fetch;
}

export interface StreamChatOptions {
  signal?: AbortSignal;
  onEvent: (event: StreamEvent) => void;
}

export type ApiClient = ReturnType<typeof createApiClient>;

export function createApiClient({ baseUrl, getClientId, fetchImpl }: ApiClientOptions) {
  const doFetch: typeof fetch = (...args) => (fetchImpl ?? globalThis.fetch)(...args);
  const url = (path: string) => `${baseUrl.replace(/\/$/, '')}${path}`;

  async function send(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    headers.set('X-Client-Id', getClientId());
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    let response: Response;
    try {
      response = await doFetch(url(path), { ...init, headers });
    } catch (error) {
      if (isAbortError(error)) throw error;
      throw new ApiError(FRIENDLY_NETWORK_ERROR, 0, 'network_error');
    }
    if (!response.ok) throw await toApiError(response);
    return response;
  }

  async function json<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await send(path, init);
    return (await response.json()) as T;
  }

  return {
    getHealth: () => json<HealthResponse>('/health'),

    getCapabilities: () => json<CapabilitiesResponse>('/capabilities'),

    uploadFile(file: File, signal?: AbortSignal): Promise<FileMeta> {
      const form = new FormData();
      form.append('file', file, file.name);
      return json<FileMeta>('/files', { method: 'POST', body: form, signal });
    },

    async deleteFile(fileId: string): Promise<void> {
      await send(`/files/${encodeURIComponent(fileId)}`, { method: 'DELETE' });
    },

    submitFeedback: (payload: FeedbackRequest) =>
      json<FeedbackResponse>('/feedback', { method: 'POST', body: JSON.stringify(payload) }),

    /** POST /chat/stream and dispatch each typed SSE event. Resolves when the stream ends. */
    async streamChat(payload: ChatRequest, { signal, onEvent }: StreamChatOptions): Promise<void> {
      const response = await send('/chat/stream', {
        method: 'POST',
        body: JSON.stringify(payload),
        headers: { Accept: 'text/event-stream' },
        signal,
      });
      if (!response.body) throw new ApiError(FRIENDLY_SERVER_ERROR, 500, 'empty_stream');
      try {
        for await (const raw of parseSse(response.body)) {
          if (!(STREAM_EVENT_NAMES as readonly string[]).includes(raw.event)) continue;
          onEvent({ event: raw.event as StreamEventName, data: JSON.parse(raw.data) } as StreamEvent);
        }
      } catch (error) {
        if (isAbortError(error)) throw error;
        throw new ApiError(FRIENDLY_NETWORK_ERROR, 0, 'stream_interrupted');
      }
    },
  };
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorResponse;
    if (body?.error?.message) {
      // 5xx messages are generic by design; 4xx messages are user-safe explanations.
      const message = response.status >= 500 ? FRIENDLY_SERVER_ERROR : body.error.message;
      return new ApiError(message, response.status, body.error.code, body.error.request_id ?? null);
    }
  } catch {
    /* non-JSON error body (e.g. proxy error page) */
  }
  return new ApiError(FRIENDLY_SERVER_ERROR, response.status, 'http_error');
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : (error as { name?: string })?.name === 'AbortError';
}
