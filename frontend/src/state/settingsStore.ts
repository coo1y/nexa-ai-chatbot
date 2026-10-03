/** Interface customisation (theme, accent, density...). Stored per browser. */
import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';

import { safeLocalStorage } from '../lib/clientId';

export type ThemePreference = 'system' | 'light' | 'dark';
export type Accent = 'indigo' | 'emerald' | 'rose' | 'amber' | 'sky' | 'violet';
export type FontSize = 'sm' | 'md' | 'lg';
export type Density = 'comfortable' | 'compact';
export type ContentWidth = 'normal' | 'wide';

export interface Settings {
  theme: ThemePreference;
  accent: Accent;
  fontSize: FontSize;
  density: Density;
  width: ContentWidth;
  showToolActivity: boolean;
  enterToSend: boolean;
  sidebarOpen: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  theme: 'system',
  accent: 'indigo',
  fontSize: 'md',
  density: 'comfortable',
  width: 'normal',
  showToolActivity: true,
  enterToSend: true,
  sidebarOpen: true,
};

export const ACCENTS: Accent[] = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet'];

const KEY = 'nexa.settings.v1';

export function loadSettings(storage = safeLocalStorage()): Settings {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      accent: ACCENTS.includes(parsed.accent as Accent) ? (parsed.accent as Accent) : DEFAULT_SETTINGS.accent,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): 'light' | 'dark' {
  return preference === 'system' ? (prefersDark ? 'dark' : 'light') : preference;
}

export const settingsStore = createStore<
  Settings & { update(patch: Partial<Settings>): void; reset(): void }
>()((set, get) => ({
  ...loadSettings(),
  update(patch) {
    set(patch);
    const { update: _u, reset: _r, ...values } = get();
    try {
      safeLocalStorage()?.setItem(KEY, JSON.stringify(values));
    } catch {
      /* ignore */
    }
  },
  reset() {
    get().update(DEFAULT_SETTINGS);
  },
}));

export function useSettings<T>(
  selector: (s: Settings & { update(patch: Partial<Settings>): void; reset(): void }) => T,
): T {
  return useStore(settingsStore, selector);
}
