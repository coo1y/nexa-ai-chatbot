/**
 * Anonymous per-browser identifier sent as X-Client-Id. It scopes uploads and feedback
 * on the server and is the hook for optional accounts later (an account can claim it).
 */
const KEY = 'nexa.clientId';
let cached: string | null = null;

export function getClientId(storage: Storage | undefined = safeLocalStorage()): string {
  if (cached) return cached;
  let id = storage?.getItem(KEY) ?? null;
  if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
    id = `c_${randomId(24)}`;
    try {
      storage?.setItem(KEY, id);
    } catch {
      /* storage full or disabled: keep the in-memory id for this session */
    }
  }
  cached = id;
  return id;
}

export function resetClientIdCache(): void {
  cached = null;
}

export function randomId(length = 16): string {
  const alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('');
}

export function safeLocalStorage(): Storage | undefined {
  try {
    return typeof window !== 'undefined' ? window.localStorage : undefined;
  } catch {
    return undefined;
  }
}
