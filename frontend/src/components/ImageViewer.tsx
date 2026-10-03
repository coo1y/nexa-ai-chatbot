import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { X } from 'lucide-react';

import { originalImageUrl } from '../lib/imageCache';
import type { Attachment } from '../state/types';

/** Full-size popup for an image attachment. Esc, the close button or a backdrop click closes it. */
export function ImageViewer({
  attachment,
  open,
  onClose,
}: {
  attachment: Attachment;
  open: boolean;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [originalFailed, setOriginalFailed] = useState(false);
  const original = originalFailed ? undefined : originalImageUrl(attachment.fileId);
  const src = original ?? attachment.previewUrl;

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal?.();
    if (!open && el.open) el.close?.();
  }, [open]);

  // The dialog itself only receives clicks on its backdrop; its content covers the rest.
  const onBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) onClose();
  };

  return (
    <dialog
      ref={dialog}
      className="image-viewer"
      aria-label={`Image: ${attachment.name}`}
      onClose={onClose}
      onClick={onBackdrop}
    >
      {open && (
        <figure className="image-viewer__body">
          <header className="image-viewer__header">
            <figcaption className="image-viewer__name" title={attachment.name}>
              {attachment.name}
            </figcaption>
            <button type="button" className="icon-button" aria-label="Close image" onClick={onClose}>
              <X size={16} />
            </button>
          </header>
          {src && (
            <img
              className="image-viewer__image"
              src={src}
              alt={attachment.name}
              onError={() => original && setOriginalFailed(true)}
            />
          )}
          {!original && (
            <p className="image-viewer__note">
              Showing a preview. The original image is only kept until the page is reloaded.
            </p>
          )}
        </figure>
      )}
    </dialog>
  );
}
