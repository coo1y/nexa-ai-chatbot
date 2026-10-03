/**
 * Full-resolution originals of images uploaded in this tab, keyed by file id.
 *
 * Local history only has room for small thumbnails (localStorage quota), and the server
 * never hands uploads back, so originals live in memory as object URLs. After a reload
 * the image viewer falls back to the thumbnail.
 */
const originals = new Map<string, string>();

export function rememberImage(fileId: string, objectUrl: string): void {
  originals.set(fileId, objectUrl);
}

export function originalImageUrl(fileId: string): string | undefined {
  return originals.get(fileId);
}

export function forgetImage(fileId: string): void {
  const url = originals.get(fileId);
  if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url);
  originals.delete(fileId);
}
