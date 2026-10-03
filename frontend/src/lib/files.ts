import type { CapabilitiesResponse } from '../api/types';

export const DEFAULT_LIMITS: CapabilitiesResponse['uploads'] = {
  max_bytes: 10 * 1024 * 1024,
  max_files_per_message: 10,
  document_extensions: [
    '.pdf',
    '.docx',
    '.xlsx',
    '.txt',
    '.md',
    '.csv',
    '.json',
    '.html',
    '.py',
    '.js',
    '.ts',
  ],
  image_extensions: ['.png', '.jpg', '.jpeg', '.webp', '.gif'],
  retention_hours: 24,
};

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot).toLowerCase();
}

export function isImageName(name: string, limits = DEFAULT_LIMITS): boolean {
  return limits.image_extensions.includes(extensionOf(name));
}

/** Client-side pre-validation (the server validates again). Returns an error message or null. */
export function validateFile(file: File, limits = DEFAULT_LIMITS): string | null {
  const ext = extensionOf(file.name);
  if (![...limits.document_extensions, ...limits.image_extensions].includes(ext)) {
    return `${file.name}: unsupported file type${ext ? ` (${ext})` : ''}.`;
  }
  if (file.size === 0) return `${file.name} is empty.`;
  if (file.size > limits.max_bytes) {
    return `${file.name} is larger than ${formatBytes(limits.max_bytes)}.`;
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function acceptAttribute(limits = DEFAULT_LIMITS): string {
  return [...limits.document_extensions, ...limits.image_extensions].join(',');
}

/** Small JPEG thumbnail (data URL) so image attachments still render in local history. */
export async function makeThumbnail(file: File, maxSize = 160): Promise<string | undefined> {
  if (typeof createImageBitmap !== 'function' || typeof document === 'undefined') return undefined;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return canvas.toDataURL('image/jpeg', 0.7);
  } catch {
    return undefined;
  }
}
