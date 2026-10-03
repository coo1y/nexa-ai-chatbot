import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type FormEvent } from 'react';
import { ArrowUp, Brain, Eye, Globe, Loader2, Paperclip, Sparkles, Square, X, Zap } from 'lucide-react';

import { api, ApiError } from '../api';
import type { CapabilityChoice } from '../api/types';
import {
  acceptAttribute,
  DEFAULT_LIMITS,
  formatBytes,
  isImageName,
  makeThumbnail,
  validateFile,
} from '../lib/files';
import { randomId } from '../lib/clientId';
import { forgetImage, rememberImage } from '../lib/imageCache';
import { chatStore, useChat } from '../state/chatStore';
import { useSettings } from '../state/settingsStore';
import type { Attachment } from '../state/types';

interface PendingUpload {
  localId: string;
  name: string;
  size: number;
  isImage: boolean;
  objectUrl?: string;
  status: 'uploading' | 'ready' | 'error';
  error?: string;
  attachment?: Attachment;
}

const CAPABILITY_OPTIONS: { id: CapabilityChoice; label: string; hint: string; Icon: typeof Zap }[] = [
  { id: 'auto', label: 'Auto', hint: 'Picks the best model for each message', Icon: Sparkles },
  { id: 'fast', label: 'Fast', hint: 'Quick everyday answers', Icon: Zap },
  { id: 'reasoning', label: 'Reasoning', hint: 'Deeper thinking for hard problems', Icon: Brain },
  { id: 'vision', label: 'Vision', hint: 'Best for images', Icon: Eye },
];

export function CapabilitySelector() {
  const capability = useChat((s) => s.capability);
  return (
    <div className="segmented" role="radiogroup" aria-label="Model capability">
      {CAPABILITY_OPTIONS.map(({ id, label, hint, Icon }) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={capability === id}
          title={hint}
          className={capability === id ? 'segmented__item segmented__item--active' : 'segmented__item'}
          onClick={() => chatStore.getState().setCapability(id)}
        >
          <Icon size={14} aria-hidden />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}

export function Composer({ prefill, onPrefillUsed }: { prefill?: string; onPrefillUsed?: () => void }) {
  const [text, setText] = useState('');
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const streaming = useChat((s) => s.streaming !== null);
  const webSearch = useChat((s) => s.webSearch);
  const limits = useChat((s) => s.capabilities?.uploads) ?? DEFAULT_LIMITS;
  const maxChars = useChat((s) => s.capabilities?.chat.max_message_chars) ?? 100_000;
  const enterToSend = useSettings((s) => s.enterToSend);

  useEffect(() => {
    if (prefill) {
      setText(prefill);
      textarea.current?.focus();
      onPrefillUsed?.();
    }
  }, [prefill, onPrefillUsed]);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [text]);

  const uploading = uploads.some((u) => u.status === 'uploading');
  const ready = uploads.filter((u) => u.status === 'ready' && u.attachment);
  const tooLong = text.length > maxChars;
  const canSend = !streaming && !uploading && !tooLong && (text.trim().length > 0 || ready.length > 0);

  async function addFiles(files: File[]) {
    setError(null);
    const room = limits.max_files_per_message - uploads.length;
    if (files.length > room)
      setError(`You can attach up to ${limits.max_files_per_message} files per message.`);
    for (const file of files.slice(0, Math.max(room, 0))) {
      const problem = validateFile(file, limits);
      if (problem) {
        setError(problem);
        continue;
      }
      const isImage = isImageName(file.name, limits);
      const pending: PendingUpload = {
        localId: randomId(8),
        name: file.name,
        size: file.size,
        isImage,
        objectUrl:
          isImage && typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : undefined,
        status: 'uploading',
      };
      setUploads((current) => [...current, pending]);
      try {
        const [meta, previewUrl] = await Promise.all([
          api.uploadFile(file),
          isImage ? makeThumbnail(file) : undefined,
        ]);
        const attachment: Attachment = {
          fileId: meta.id,
          name: meta.filename,
          kind: meta.kind,
          sizeBytes: meta.size_bytes,
          pageCount: meta.page_count,
          previewUrl,
        };
        // The sent message's image viewer shows this original; the thumbnail is only 160px.
        if (pending.objectUrl) rememberImage(meta.id, pending.objectUrl);
        setUploads((current) =>
          current.map((u) => (u.localId === pending.localId ? { ...u, status: 'ready', attachment } : u)),
        );
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Upload failed.';
        setUploads((current) =>
          current.map((u) => (u.localId === pending.localId ? { ...u, status: 'error', error: message } : u)),
        );
      }
    }
  }

  function removeUpload(localId: string) {
    setUploads((current) => {
      const target = current.find((u) => u.localId === localId);
      if (target?.attachment) {
        forgetImage(target.attachment.fileId);
        api.deleteFile(target.attachment.fileId).catch(() => undefined);
      } else if (target?.objectUrl) URL.revokeObjectURL(target.objectUrl);
      return current.filter((u) => u.localId !== localId);
    });
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    const attachments = ready.map((u) => u.attachment!);
    // Sent images keep their object URL (owned by imageCache) for the full-size viewer.
    uploads.forEach((u) => !u.attachment && u.objectUrl && URL.revokeObjectURL(u.objectUrl));
    setText('');
    setUploads([]);
    setError(null);
    void chatStore.getState().sendMessage(text, attachments);
  }

  const onPaste = (event: ClipboardEvent) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length) {
      event.preventDefault();
      void addFiles(files);
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    void addFiles(Array.from(event.dataTransfer.files));
  };

  return (
    <form
      className={`composer ${dragging ? 'composer--dragging' : ''}`}
      onSubmit={submit}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      aria-label="Message composer"
    >
      {uploads.length > 0 && (
        <ul className="composer__uploads" aria-label="Attachments">
          {uploads.map((u) => (
            <li key={u.localId} className={`upload upload--${u.status}`} title={u.error ?? u.name}>
              {u.objectUrl ? <img src={u.objectUrl} alt="" className="upload__thumb" /> : null}
              <span className="upload__name">{u.name}</span>
              <span className="upload__meta">
                {u.status === 'uploading' && <Loader2 size={12} className="spin" aria-label="Uploading" />}
                {u.status === 'error' ? u.error : formatBytes(u.size)}
              </span>
              <button
                type="button"
                className="icon-button icon-button--small"
                aria-label={`Remove ${u.name}`}
                onClick={() => removeUpload(u.localId)}
              >
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <textarea
        ref={textarea}
        className="composer__input"
        placeholder="Message Nexa… (attach files, paste images, or ask anything)"
        aria-label="Message"
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onPaste={onPaste}
        onKeyDown={(e) => {
          if (
            e.key === 'Enter' &&
            !e.nativeEvent.isComposing &&
            (enterToSend ? !e.shiftKey : e.metaKey || e.ctrlKey)
          ) {
            e.preventDefault();
            submit();
          }
        }}
      />

      <div className="composer__toolbar">
        <div className="composer__tools">
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            accept={acceptAttribute(limits)}
            data-testid="file-input"
            onChange={(e) => {
              void addFiles(Array.from(e.target.files ?? []));
              e.target.value = '';
            }}
          />
          <button
            type="button"
            className="icon-button"
            aria-label="Attach files"
            title="Attach documents or images"
            onClick={() => fileInput.current?.click()}
          >
            <Paperclip size={17} />
          </button>
          <button
            type="button"
            className={`chip-toggle ${webSearch ? 'chip-toggle--on' : ''}`}
            aria-pressed={webSearch}
            title="Search the web for this message"
            onClick={() => chatStore.getState().setWebSearch(!webSearch)}
          >
            <Globe size={14} /> Search
          </button>
          <CapabilitySelector />
        </div>
        {streaming ? (
          <button
            type="button"
            className="send-button send-button--stop"
            aria-label="Stop generating"
            onClick={() => chatStore.getState().stopGeneration()}
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button type="submit" className="send-button" aria-label="Send message" disabled={!canSend}>
            <ArrowUp size={18} />
          </button>
        )}
      </div>
      {(error || tooLong) && (
        <p className="composer__error" role="alert">
          {tooLong
            ? `Message is too long (${text.length.toLocaleString()} / ${maxChars.toLocaleString()} characters).`
            : error}
        </p>
      )}
    </form>
  );
}
