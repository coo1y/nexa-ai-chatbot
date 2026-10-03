import { useEffect, useRef } from 'react';
import { ExternalLink, X } from 'lucide-react';

import { chatStore, useActiveConversation, useChat } from '../state/chatStore';

export function SourcesPanel() {
  const sourcesFor = useChat((s) => s.sourcesFor);
  const conversation = useActiveConversation();
  const list = useRef<HTMLOListElement>(null);
  const message = conversation?.messages.find((m) => m.id === sourcesFor?.messageId);
  const sources = message?.sources ?? [];

  useEffect(() => {
    if (sourcesFor?.highlight == null) return;
    list.current
      ?.querySelector(`[data-source="${sourcesFor.highlight}"]`)
      ?.scrollIntoView?.({ block: 'nearest' });
  }, [sourcesFor]);

  if (!sourcesFor || !message) return null;
  return (
    <aside className="sources-panel" aria-label="Sources">
      <header className="sources-panel__header">
        <h2>Sources</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Close sources"
          onClick={() => chatStore.getState().closeSources()}
        >
          <X size={16} />
        </button>
      </header>
      {sources.length === 0 ? (
        <p className="sources-panel__empty">No web sources were used for this response.</p>
      ) : (
        <ol ref={list} className="sources-panel__list">
          {sources.map((source) => (
            <li
              key={source.id}
              data-source={source.id}
              className={source.id === sourcesFor.highlight ? 'source source--highlight' : 'source'}
            >
              <span className="source__id">{source.id}</span>
              <div>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="source__title"
                >
                  {source.title} <ExternalLink size={12} aria-hidden />
                </a>
                <div className="source__domain">{source.domain}</div>
                {source.snippet && <p className="source__snippet">{source.snippet}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
