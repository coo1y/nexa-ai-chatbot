import { parseBlock, parseSse } from './sse';

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const out = [];
  for await (const event of parseSse(stream)) out.push(event);
  return out;
}

describe('parseSse', () => {
  it('parses events split across arbitrary chunk boundaries', async () => {
    const events = await collect(
      streamOf('event: del', 'ta\ndata: {"text":"Hel', 'lo"}\n', '\nevent: done\ndata: {}\n\n'),
    );
    expect(events).toEqual([
      { event: 'delta', data: '{"text":"Hello"}' },
      { event: 'done', data: '{}' },
    ]);
  });

  it('handles CRLF line endings, comments and a final event without trailing blank line', async () => {
    const events = await collect(
      streamOf(': keep-alive\r\n\r\nevent: a\r\ndata: 1\r\n\r\nevent: b\ndata: 2'),
    );
    expect(events).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
    ]);
  });

  it('joins multi-line data and handles multibyte characters split across chunks', async () => {
    const bytes = new TextEncoder().encode('data: héllo 👋\ndata: line2\n\n');
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 9));
        controller.enqueue(bytes.slice(9));
        controller.close();
      },
    });
    expect(await collect(stream)).toEqual([{ event: 'message', data: 'héllo 👋\nline2' }]);
  });

  it('ignores blocks without data', () => {
    expect(parseBlock('event: ping')).toBeNull();
  });
});
