import { ApiError, createApiClient, FRIENDLY_NETWORK_ERROR, FRIENDLY_SERVER_ERROR } from './client';
import type { StreamEvent } from './types';
import { delta, doneEvent, sseBody, startEvent } from '../test/helpers';

function setup(fetchImpl: typeof fetch) {
  return createApiClient({ baseUrl: '/api/v1/', getClientId: () => 'client-123456', fetchImpl });
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('api client', () => {
  it('sends the client id header and parses JSON', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json({ status: 'ok' }));
    const client = setup(fetchImpl);
    await expect(client.getHealth()).resolves.toEqual({ status: 'ok' });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('/api/v1/health');
    expect(new Headers(init.headers).get('X-Client-Id')).toBe('client-123456');
  });

  it('streams typed chat events and skips unknown ones', async () => {
    const events: StreamEvent[] = [startEvent(), delta('Hi'), delta(' there'), doneEvent()];
    const body = sseBody(events);
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }));
    const received: StreamEvent[] = [];
    await setup(fetchImpl).streamChat(
      { conversation_id: 'c', messages: [{ id: 'u1', role: 'user', content: 'hi' }] },
      { onEvent: (e) => received.push(e) },
    );
    expect(received).toEqual(events);
    const init = fetchImpl.mock.calls[0][1];
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init.body).messages[0].content).toBe('hi');
  });

  it('surfaces 4xx error messages from the error envelope', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        json(
          { error: { code: 'unsupported_file', message: 'Unsupported file type .exe', request_id: 'r1' } },
          415,
        ),
      );
    const error = await setup(fetchImpl)
      .uploadFile(new File(['x'], 'a.exe'))
      .catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 415,
      code: 'unsupported_file',
      message: 'Unsupported file type .exe',
      requestId: 'r1',
    });
    expect(error.retryable).toBe(false);
  });

  it('hides server error details behind a friendly message', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        json({ error: { code: 'internal_error', message: 'db exploded at 10.0.0.3' } }, 500),
      );
    const error = await setup(fetchImpl)
      .getCapabilities()
      .catch((e) => e);
    expect(error.message).toBe(FRIENDLY_SERVER_ERROR);
    expect(error.retryable).toBe(true);
  });

  it('maps network failures to a friendly retryable error', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await setup(fetchImpl)
      .getHealth()
      .catch((e) => e);
    expect(error).toMatchObject({ status: 0, code: 'network_error', message: FRIENDLY_NETWORK_ERROR });
    expect(error.retryable).toBe(true);
  });

  it('propagates aborts untouched (stop generation)', async () => {
    const abort = new DOMException('Aborted', 'AbortError');
    const fetchImpl = vi.fn().mockRejectedValue(abort);
    await expect(
      setup(fetchImpl).streamChat({ conversation_id: 'c', messages: [] }, { onEvent: () => undefined }),
    ).rejects.toBe(abort);
  });

  it('uses multipart for uploads without forcing a JSON content type', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json({ id: 'f1' }, 201));
    await setup(fetchImpl).uploadFile(new File(['hello'], 'notes.txt'));
    const init = fetchImpl.mock.calls[0][1];
    expect(init.body).toBeInstanceOf(FormData);
    expect(new Headers(init.headers).has('Content-Type')).toBe(false);
  });
});
