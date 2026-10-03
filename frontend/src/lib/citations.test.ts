import { citationIdFromHref, linkifyCitations } from './citations';

const ids = new Set([1, 2, 3]);

describe('linkifyCitations', () => {
  it('links single and grouped citations that exist', () => {
    expect(linkifyCitations('Fact [1]. Others [2, 3].', ids)).toBe(
      'Fact [1](#cite-1). Others [2](#cite-2)[3](#cite-3).',
    );
  });

  it('leaves unknown ids, real links and code untouched', () => {
    const text = 'Bad [9]. Link [1](https://x.dev). Code `arr[1]` and\n```\nx = a[2]\n```\nend [2]';
    expect(linkifyCitations(text, ids)).toBe(
      'Bad [9]. Link [1](https://x.dev). Code `arr[1]` and\n```\nx = a[2]\n```\nend [2](#cite-2)',
    );
  });

  it('is a no-op without sources', () => {
    expect(linkifyCitations('see [1]', new Set())).toBe('see [1]');
  });
});

describe('citationIdFromHref', () => {
  it('parses citation anchors only', () => {
    expect(citationIdFromHref('#cite-4')).toBe(4);
    expect(citationIdFromHref('https://example.com')).toBeNull();
    expect(citationIdFromHref(undefined)).toBeNull();
  });
});
