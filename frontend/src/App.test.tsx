/**
 * UI-level tests: render the real App with the real store; only the API module is mocked.
 */
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import App from './App';
import type { ChatRequest, StreamEvent } from './api/types';
import { chatStore } from './state/chatStore';
import { settingsStore } from './state/settingsStore';
import { deferred, delta, doneEvent, startEvent } from './test/helpers';

type StreamOpts = { signal?: AbortSignal; onEvent: (e: StreamEvent) => void };

const mockApi = vi.hoisted(() => ({
  streamChat: vi.fn(),
  uploadFile: vi.fn(),
  deleteFile: vi.fn(),
  submitFeedback: vi.fn(),
  getCapabilities: vi.fn(),
  getHealth: vi.fn(),
}));

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>();
  return { ...actual, api: mockApi };
});

function replyWith(...events: StreamEvent[]) {
  mockApi.streamChat.mockImplementation(async (_payload: ChatRequest, { onEvent }: StreamOpts) => {
    events.forEach(onEvent);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getCapabilities.mockRejectedValue(new Error('offline'));
  mockApi.deleteFile.mockResolvedValue(undefined);
  mockApi.submitFeedback.mockResolvedValue({});
  chatStore.setState({
    conversations: {},
    activeId: null,
    streaming: null,
    sourcesFor: null,
    capability: 'auto',
    webSearch: false,
    notice: null,
  });
  settingsStore.getState().reset();
  replyWith(startEvent(), delta('Hello '), delta('from **Nexa**'), doneEvent());
});

async function send(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: 'Message' }), text);
  await user.click(screen.getByRole('button', { name: 'Send message' }));
  return user;
}

describe('App', () => {
  it('opens straight into a chat with suggestions (no login)', () => {
    render(<App />);
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New chat' })).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'Model capability' })).toBeInTheDocument();
  });

  it('sends a message and renders the streamed markdown response', async () => {
    render(<App />);
    await send('Hi Nexa');
    expect(await screen.findByText('Nexa', { selector: 'strong' })).toBeInTheDocument();
    const log = screen.getByRole('log', { name: 'Conversation' });
    expect(within(log).getByText('Hi Nexa')).toBeInTheDocument();
    expect(within(log).getByText('Fast')).toBeInTheDocument(); // routing badge
    expect(within(screen.getByRole('navigation')).getByText('Hi Nexa')).toBeInTheDocument(); // auto title
  });

  it('shows tool activity, clickable citations and the sources panel', async () => {
    replyWith(
      startEvent(),
      {
        event: 'tool_call',
        data: { id: 's', name: 'web_search', label: 'Web search', input: { query: 'ai news' } },
      },
      {
        event: 'tool_result',
        data: {
          id: 's',
          name: 'web_search',
          status: 'success',
          summary: 'Found 2 results for "ai news"',
          duration_ms: 30,
        },
      },
      {
        event: 'sources',
        data: {
          sources: [
            {
              id: 1,
              title: 'AI Weekly',
              url: 'https://ai.example/news',
              domain: 'ai.example',
              snippet: 'Big news',
            },
            {
              id: 2,
              title: 'Tech Daily',
              url: 'https://tech.example/a',
              domain: 'tech.example',
              snippet: '',
            },
          ],
        },
      },
      delta('Models got faster [1]. Chips too [2].'),
      doneEvent(),
    );
    render(<App />);
    const user = await send('latest AI news');
    expect(await screen.findByText('Found 2 results for "ai news"')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show source 2' }));
    const panel = screen.getByRole('complementary', { name: 'Sources' });
    expect(within(panel).getByRole('link', { name: /AI Weekly/ })).toHaveAttribute(
      'href',
      'https://ai.example/news',
    );
    expect(within(panel).getByText('Tech Daily').closest('li')).toHaveClass('source--highlight');
    await user.click(within(panel).getByRole('button', { name: 'Close sources' }));
    expect(screen.queryByRole('complementary', { name: 'Sources' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /2 sources/ }));
    expect(screen.getByRole('complementary', { name: 'Sources' })).toBeInTheDocument();
  });

  it('lets the user stop an active generation', async () => {
    mockApi.streamChat.mockImplementation(
      (_p: ChatRequest, { signal, onEvent }: StreamOpts) =>
        new Promise((_resolve, reject) => {
          onEvent(startEvent());
          onEvent(delta('Once upon a time'));
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        }),
    );
    render(<App />);
    const user = await send('tell me a story');
    const stop = await screen.findByRole('button', { name: 'Stop generating' });
    await user.click(stop);
    expect(await screen.findByText('Generation stopped.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeInTheDocument();
  });

  it('regenerates the latest response and submits feedback', async () => {
    render(<App />);
    const user = await send('hello');
    await screen.findByText('Nexa', { selector: 'strong' });
    replyWith(startEvent(), delta('A different answer'), doneEvent());
    await user.click(screen.getByRole('button', { name: 'Regenerate response' }));
    expect(await screen.findByText('A different answer')).toBeInTheDocument();
    expect(mockApi.streamChat).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole('button', { name: 'Good response' }));
    expect(screen.getByRole('button', { name: 'Good response' })).toHaveAttribute('aria-pressed', 'true');
    expect(mockApi.submitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ rating: 'up', message_id: 'msg_server_1' }),
    );
  });

  it('edits the latest user message', async () => {
    render(<App />);
    const user = await send('wrong question');
    await screen.findByText('Nexa', { selector: 'strong' });
    await user.click(screen.getByRole('button', { name: 'Edit message' }));
    const editor = screen.getByRole('textbox', { name: 'Edit message' });
    await user.clear(editor);
    await user.type(editor, 'right question');
    await user.click(screen.getByRole('button', { name: /Save/ }));
    await waitFor(() => expect(mockApi.streamChat).toHaveBeenCalledTimes(2));
    const payload = mockApi.streamChat.mock.calls[1][0] as ChatRequest;
    expect(payload.messages.map((m) => m.content)).toEqual(['right question']);
    expect(await screen.findByText('right question')).toBeInTheDocument();
  });

  it('shows a friendly error with a working Retry button', async () => {
    replyWith(
      startEvent(),
      {
        event: 'error',
        data: {
          code: 'upstream_unavailable',
          message: 'The AI service is temporarily unavailable.',
          retryable: true,
        },
      },
      doneEvent('error'),
    );
    render(<App />);
    const user = await send('hello');
    expect(await screen.findByRole('alert')).toHaveTextContent('The AI service is temporarily unavailable.');
    replyWith(startEvent(), delta('Back online'), doneEvent());
    await user.click(screen.getByRole('button', { name: /Retry/ }));
    expect(await screen.findByText('Back online')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('uploads a file and sends it as an attachment', async () => {
    mockApi.uploadFile.mockResolvedValue({
      id: '11111111-1111-1111-1111-111111111111',
      filename: 'report.pdf',
      kind: 'document',
      content_type: 'application/pdf',
      size_bytes: 2048,
      char_count: 100,
      page_count: 2,
      truncated: false,
      width: null,
      height: null,
      created_at: '2026-10-03T00:00:00Z',
      expires_at: '2026-10-04T00:00:00Z',
    });
    render(<App />);
    const user = userEvent.setup();
    await user.upload(
      screen.getByTestId('file-input'),
      new File(['%PDF'], 'report.pdf', { type: 'application/pdf' }),
    );
    expect(await screen.findByText('report.pdf')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled());
    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'Summarize it');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    const payload = mockApi.streamChat.mock.calls[0][0] as ChatRequest;
    expect(payload.messages[0].attachments).toEqual([{ file_id: '11111111-1111-1111-1111-111111111111' }]);
  });

  it('rejects unsupported files before uploading', async () => {
    render(<App />);
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(screen.getByTestId('file-input'), new File(['MZ'], 'setup.exe'));
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported file type');
    expect(mockApi.uploadFile).not.toHaveBeenCalled();
  });

  it('switches capability and toggles web search', async () => {
    render(<App />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: /Vision/ }));
    await user.click(screen.getByRole('button', { name: /Search/ }));
    await send('describe');
    const payload = mockApi.streamChat.mock.calls[0][0] as ChatRequest;
    expect(payload).toMatchObject({ capability: 'vision', web_search: true });
  });

  it('renames and deletes conversations from the sidebar', async () => {
    render(<App />);
    const user = await send('First topic');
    await screen.findByText('Nexa', { selector: 'strong' });
    const sidebar = screen.getByRole('navigation', { name: 'Conversations' });
    await user.click(within(sidebar).getByRole('button', { name: 'Rename First topic' }));
    const input = within(sidebar).getByRole('textbox', { name: 'Conversation title' });
    await user.clear(input);
    await user.type(input, 'Renamed chat{Enter}');
    expect(within(sidebar).getByText('Renamed chat')).toBeInTheDocument();

    await user.click(within(sidebar).getByRole('button', { name: 'Delete Renamed chat' }));
    await user.click(within(sidebar).getByRole('button', { name: 'Delete' }));
    expect(within(sidebar).queryByText('Renamed chat')).not.toBeInTheDocument();
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();
  });

  it('starts a new chat while keeping the previous one', async () => {
    render(<App />);
    const user = await send('Keep me');
    await screen.findByText('Nexa', { selector: 'strong' });
    await user.click(screen.getByRole('button', { name: 'New chat' }));
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();
    expect(within(screen.getByRole('navigation')).getByText('Keep me')).toBeInTheDocument();
  });

  it('toggles light/dark theme and applies customisation settings', async () => {
    render(<App />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Toggle theme' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    await user.click(screen.getByRole('button', { name: 'Toggle theme' }));
    expect(document.documentElement.dataset.theme).toBe('light');

    await user.click(screen.getByRole('button', { name: 'Settings' }));
    await user.click(screen.getByRole('button', { name: 'emerald' }));
    await user.click(screen.getByRole('button', { name: 'Large' }));
    expect(document.documentElement.dataset.accent).toBe('emerald');
    expect(document.documentElement.dataset.font).toBe('lg');
  });

  it('shows the safety notice for supportive guidance', async () => {
    replyWith(
      startEvent(),
      {
        event: 'safety',
        data: {
          action: 'allow_with_guidance',
          category: 'self_harm',
          message: "You don't have to face it alone.",
        },
      },
      delta("I'm sorry you're feeling this way."),
      doneEvent(),
    );
    render(<App />);
    await send('I feel hopeless');
    expect(await screen.findByRole('note')).toHaveTextContent("You don't have to face it alone.");
  });

  it('disables sending while a response is streaming', async () => {
    const gate = deferred();
    mockApi.streamChat.mockImplementation(async (_p: ChatRequest, { onEvent }: StreamOpts) => {
      onEvent(startEvent());
      await gate.promise;
      onEvent(doneEvent());
    });
    render(<App />);
    await send('first');
    expect(await screen.findByRole('button', { name: 'Stop generating' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send message' })).not.toBeInTheDocument();
    await act(async () => gate.resolve());
    expect(await screen.findByRole('button', { name: 'Send message' })).toBeInTheDocument();
  });
});
