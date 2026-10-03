/**
 * Turn "[1]" / "[1, 3]" citation markers into Markdown links (#cite-n) that the renderer
 * displays as clickable source chips. Code spans/blocks and real links are left untouched.
 */
const CITATION_RX = /\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\](?!\(|:)/g;
const CODE_RX = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;

export const CITE_PREFIX = '#cite-';

export function linkifyCitations(markdown: string, validIds: ReadonlySet<number>): string {
  if (validIds.size === 0 || !markdown.includes('[')) return markdown;
  return markdown
    .split(CODE_RX)
    .map((segment, index) => (index % 2 === 1 ? segment : replaceCitations(segment, validIds)))
    .join('');
}

function replaceCitations(text: string, validIds: ReadonlySet<number>): string {
  return text.replace(CITATION_RX, (match, group: string) => {
    const ids = group.split(',').map((n) => Number(n.trim()));
    if (!ids.every((id) => validIds.has(id))) return match;
    return ids.map((id) => `[${id}](${CITE_PREFIX}${id})`).join('');
  });
}

export function citationIdFromHref(href: string | undefined): number | null {
  if (!href?.startsWith(CITE_PREFIX)) return null;
  const id = Number(href.slice(CITE_PREFIX.length));
  return Number.isInteger(id) ? id : null;
}
