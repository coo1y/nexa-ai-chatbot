import { memo, useMemo, useState, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import { Check, Copy } from 'lucide-react';

import { citationIdFromHref, linkifyCitations } from '../lib/citations';

interface MarkdownProps {
  content: string;
  sourceIds?: ReadonlySet<number>;
  onCitation?: (id: number) => void;
}

function CodeBlock({ children, className }: { children?: ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const language = /language-(\w+)/.exec(className ?? '')?.[1];
  const copy = () => {
    const text = extractText(children);
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div className="code-block">
      <div className="code-block__bar">
        <span>{language ?? 'code'}</span>
        <button
          type="button"
          className="icon-button icon-button--small"
          onClick={copy}
          aria-label="Copy code"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

function extractText(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractText).join('');
  if (node && typeof node === 'object' && 'props' in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return '';
}

export const Markdown = memo(function Markdown({ content, sourceIds, onCitation }: MarkdownProps) {
  const text = useMemo(() => linkifyCitations(content, sourceIds ?? new Set()), [content, sourceIds]);
  const components = useMemo<Components>(
    () => ({
      a({ href, children }) {
        const citation = citationIdFromHref(href);
        if (citation !== null) {
          return (
            <button
              type="button"
              className="citation"
              onClick={() => onCitation?.(citation)}
              aria-label={`Show source ${citation}`}
            >
              {citation}
            </button>
          );
        }
        return (
          <a href={href} target="_blank" rel="noopener noreferrer nofollow">
            {children}
          </a>
        );
      },
      pre({ children }) {
        return <>{children}</>;
      },
      code({ className, children, node }) {
        const isBlock = node?.position && node.position.start.line !== node.position.end.line;
        if (isBlock || /language-/.test(className ?? '')) {
          return <CodeBlock className={className}>{children}</CodeBlock>;
        }
        return <code className="inline-code">{children}</code>;
      },
      table({ children }) {
        return (
          <div className="table-wrap">
            <table>{children}</table>
          </div>
        );
      },
    }),
    [onCitation],
  );
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
});
