import { memo, useCallback, useMemo, useState } from 'react';
import {
  BookOpen,
  Brain,
  Check,
  Copy,
  Eye,
  FileText,
  HeartHandshake,
  Pencil,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  Zap,
} from 'lucide-react';

import { chatStore } from '../state/chatStore';
import { useSettings } from '../state/settingsStore';
import type { Attachment, Message } from '../state/types';
import { formatBytes } from '../lib/files';
import { Markdown } from './Markdown';
import { ToolActivityList } from './ToolActivityList';

const CAPABILITY_ICON = { fast: Zap, reasoning: Brain, vision: Eye } as const;
const CAPABILITY_LABEL = { fast: 'Fast', reasoning: 'Reasoning', vision: 'Vision' } as const;

export function AttachmentPreview({ attachment }: { attachment: Attachment }) {
  if (attachment.kind === 'image' && attachment.previewUrl) {
    return (
      <img
        className="attachment-thumb"
        src={attachment.previewUrl}
        alt={attachment.name}
        title={attachment.name}
      />
    );
  }
  return (
    <span className="attachment-chip" title={attachment.name}>
      <FileText size={14} aria-hidden />
      <span className="attachment-chip__name">{attachment.name}</span>
      <span className="attachment-chip__meta">{formatBytes(attachment.sizeBytes)}</span>
    </span>
  );
}

interface MessageItemProps {
  message: Message;
  isLatest: boolean;
  isLatestUser: boolean;
  busy: boolean;
}

export const MessageItem = memo(function MessageItem({
  message,
  isLatest,
  isLatestUser,
  busy,
}: MessageItemProps) {
  return message.role === 'user' ? (
    <UserMessage message={message} canEdit={isLatestUser && !busy} />
  ) : (
    <AssistantMessage message={message} isLatest={isLatest} busy={busy} />
  );
});

function UserMessage({ message, canEdit }: { message: Message; canEdit: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

  const save = () => {
    setEditing(false);
    if (draft.trim() !== message.content.trim()) void chatStore.getState().editLastUserMessage(draft);
  };

  return (
    <article className="message message--user" aria-label="Your message">
      {message.attachments.length > 0 && (
        <div className="message__attachments">
          {message.attachments.map((a) => (
            <AttachmentPreview key={a.fileId} attachment={a} />
          ))}
        </div>
      )}
      {editing ? (
        <div className="edit-box">
          <textarea
            aria-label="Edit message"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                save();
              } else if (e.key === 'Escape') setEditing(false);
            }}
          />
          <div className="edit-box__actions">
            <button type="button" className="button button--ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button type="button" className="button button--primary" onClick={save}>
              Save &amp; submit
            </button>
          </div>
        </div>
      ) : (
        <div className="message__row">
          {canEdit && (
            <div className="message__actions message__actions--user">
              <button
                type="button"
                className="icon-button"
                aria-label="Edit message"
                title="Edit message"
                onClick={() => {
                  setDraft(message.content);
                  setEditing(true);
                }}
              >
                <Pencil size={15} />
              </button>
            </div>
          )}
          {message.content && <div className="message__bubble">{message.content}</div>}
        </div>
      )}
    </article>
  );
}

function AssistantMessage({
  message,
  isLatest,
  busy,
}: {
  message: Message;
  isLatest: boolean;
  busy: boolean;
}) {
  const showTools = useSettings((s) => s.showToolActivity);
  const [copied, setCopied] = useState(false);
  const sourceIds = useMemo(() => new Set((message.sources ?? []).map((s) => s.id)), [message.sources]);
  const onCitation = useCallback(
    (id: number) => chatStore.getState().openSources(message.id, id),
    [message.id],
  );
  const streaming = message.status === 'streaming';
  const finished = !streaming;
  const routing = message.routing;
  const RouteIcon = routing ? CAPABILITY_ICON[routing.capability] : null;

  const copy = () =>
    void navigator.clipboard?.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });

  return (
    <article className="message message--assistant" aria-label="Assistant message" aria-busy={streaming}>
      {routing && RouteIcon && (
        <div className="route-badge" title={`${routing.reason} · ${routing.model}`}>
          <RouteIcon size={13} aria-hidden />
          <span>{CAPABILITY_LABEL[routing.capability]}</span>
          <span className="route-badge__mode">{routing.mode === 'auto' ? 'auto' : 'selected'}</span>
        </div>
      )}

      {message.safety && (
        <div
          className={`notice notice--${message.safety.action === 'block' ? 'warning' : 'support'}`}
          role="note"
        >
          {message.safety.action === 'block' ? <ShieldAlert size={16} /> : <HeartHandshake size={16} />}
          <span>
            {message.safety.action === 'block'
              ? 'This request was declined by our safety policy.'
              : message.safety.message}
          </span>
        </div>
      )}

      {showTools && <ToolActivityList tools={message.tools ?? []} />}

      {message.content ? (
        <div className={streaming ? 'streaming' : undefined}>
          <Markdown content={message.content} sourceIds={sourceIds} onCitation={onCitation} />
        </div>
      ) : (
        streaming && (
          <div className="typing" aria-label="Generating response">
            <span />
            <span />
            <span />
          </div>
        )
      )}

      {message.status === 'stopped' && <p className="message__status">Generation stopped.</p>}

      {message.status === 'error' && message.error && (
        <div className="notice notice--error" role="alert">
          <span>{message.error.message}</span>
          {message.error.retryable && isLatest && (
            <button
              type="button"
              className="button button--small"
              onClick={() => void chatStore.getState().retry()}
              disabled={busy}
            >
              <RotateCcw size={14} /> Retry
            </button>
          )}
        </div>
      )}

      {finished && (
        <div className="message__actions">
          {message.content && (
            <button
              type="button"
              className="icon-button"
              aria-label="Copy response"
              title="Copy"
              onClick={copy}
            >
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </button>
          )}
          {isLatest && message.status !== 'error' && (
            <button
              type="button"
              className="icon-button"
              aria-label="Regenerate response"
              title="Regenerate"
              disabled={busy}
              onClick={() => void chatStore.getState().regenerate()}
            >
              <RefreshCw size={15} />
            </button>
          )}
          {message.status !== 'error' && (
            <>
              <button
                type="button"
                className={`icon-button ${message.feedback === 'up' ? 'icon-button--active' : ''}`}
                aria-label="Good response"
                aria-pressed={message.feedback === 'up'}
                title="Good response"
                onClick={() => void chatStore.getState().setFeedback(message.id, 'up')}
              >
                <ThumbsUp size={15} />
              </button>
              <button
                type="button"
                className={`icon-button ${message.feedback === 'down' ? 'icon-button--active' : ''}`}
                aria-label="Bad response"
                aria-pressed={message.feedback === 'down'}
                title="Bad response"
                onClick={() => void chatStore.getState().setFeedback(message.id, 'down')}
              >
                <ThumbsDown size={15} />
              </button>
            </>
          )}
          {(message.sources?.length ?? 0) > 0 && (
            <button
              type="button"
              className="sources-button"
              onClick={() => chatStore.getState().openSources(message.id)}
            >
              <BookOpen size={14} /> {message.sources!.length} sources
            </button>
          )}
        </div>
      )}
    </article>
  );
}
