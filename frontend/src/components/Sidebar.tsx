import { useMemo, useState } from 'react';
import { Check, MessageSquarePlus, Moon, Pencil, Settings, Sun, Trash2, X } from 'lucide-react';

import { dateGroup } from '../lib/format';
import { sortConversations } from '../lib/conversation';
import { chatStore, useChat } from '../state/chatStore';
import { settingsStore } from '../state/settingsStore';
import type { Conversation } from '../state/types';

function ConversationRow({
  conversation,
  active,
  onNavigate,
}: {
  conversation: Conversation;
  active: boolean;
  onNavigate?: () => void;
}) {
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm-delete'>('view');
  const [title, setTitle] = useState(conversation.title);
  const { selectConversation, renameConversation, deleteConversation } = chatStore.getState();

  if (mode === 'rename') {
    return (
      <form
        className="conversation conversation--editing"
        onSubmit={(e) => {
          e.preventDefault();
          renameConversation(conversation.id, title);
          setMode('view');
        }}
      >
        <input
          aria-label="Conversation title"
          value={title}
          autoFocus
          maxLength={120}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && setMode('view')}
        />
        <button type="submit" className="icon-button icon-button--small" aria-label="Save title">
          <Check size={14} />
        </button>
        <button
          type="button"
          className="icon-button icon-button--small"
          aria-label="Cancel rename"
          onClick={() => setMode('view')}
        >
          <X size={14} />
        </button>
      </form>
    );
  }

  return (
    <div className={`conversation ${active ? 'conversation--active' : ''}`}>
      <button
        type="button"
        className="conversation__title"
        onClick={() => {
          selectConversation(conversation.id);
          onNavigate?.();
        }}
        aria-current={active ? 'page' : undefined}
      >
        {conversation.title}
      </button>
      {mode === 'confirm-delete' ? (
        <span className="conversation__confirm">
          <button
            type="button"
            className="button button--danger button--tiny"
            onClick={() => deleteConversation(conversation.id)}
          >
            Delete
          </button>
          <button
            type="button"
            className="icon-button icon-button--small"
            aria-label="Cancel delete"
            onClick={() => setMode('view')}
          >
            <X size={14} />
          </button>
        </span>
      ) : (
        <span className="conversation__actions">
          <button
            type="button"
            className="icon-button icon-button--small"
            aria-label={`Rename ${conversation.title}`}
            onClick={() => {
              setTitle(conversation.title);
              setMode('rename');
            }}
          >
            <Pencil size={13} />
          </button>
          <button
            type="button"
            className="icon-button icon-button--small"
            aria-label={`Delete ${conversation.title}`}
            onClick={() => setMode('confirm-delete')}
          >
            <Trash2 size={13} />
          </button>
        </span>
      )}
    </div>
  );
}

export function Sidebar({
  theme,
  onOpenSettings,
  onNavigate,
}: {
  theme: 'light' | 'dark';
  onOpenSettings: () => void;
  onNavigate?: () => void;
}) {
  const conversations = useChat((s) => s.conversations);
  const activeId = useChat((s) => s.activeId);

  const groups = useMemo(() => {
    const result = new Map<string, Conversation[]>();
    for (const c of sortConversations(Object.values(conversations))) {
      if (c.messages.length === 0 && c.id !== activeId) continue;
      const group = dateGroup(c.updatedAt);
      result.set(group, [...(result.get(group) ?? []), c]);
    }
    return result;
  }, [conversations, activeId]);

  return (
    <nav className="sidebar" aria-label="Conversations">
      <div className="sidebar__header">
        <span className="brand">
          <span className="brand__mark" aria-hidden>
            N
          </span>
          Nexa
        </span>
        <button
          type="button"
          className="button button--primary new-chat"
          onClick={() => {
            chatStore.getState().newConversation();
            onNavigate?.();
          }}
        >
          <MessageSquarePlus size={16} /> New chat
        </button>
      </div>
      <div className="sidebar__list">
        {groups.size === 0 && (
          <p className="sidebar__empty">Your conversations are stored only in this browser.</p>
        )}
        {[...groups.entries()].map(([group, items]) => (
          <section key={group}>
            <h2 className="sidebar__group">{group}</h2>
            {items.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                active={c.id === activeId}
                onNavigate={onNavigate}
              />
            ))}
          </section>
        ))}
      </div>
      <div className="sidebar__footer">
        <button
          type="button"
          className="icon-button"
          aria-label="Toggle theme"
          title="Toggle light/dark"
          onClick={() => settingsStore.getState().update({ theme: theme === 'dark' ? 'light' : 'dark' })}
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button type="button" className="button button--ghost" onClick={onOpenSettings}>
          <Settings size={16} /> Settings
        </button>
      </div>
    </nav>
  );
}
