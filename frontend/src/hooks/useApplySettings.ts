import { useEffect, useState } from 'react';

import { resolveTheme, useSettings } from '../state/settingsStore';

function usePrefersDark(): boolean {
  const query =
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null;
  const [dark, setDark] = useState(query?.matches ?? false);
  useEffect(() => {
    if (!query) return;
    const listener = (event: MediaQueryListEvent) => setDark(event.matches);
    query.addEventListener('change', listener);
    return () => query.removeEventListener('change', listener);
  }, [query]);
  return dark;
}

/** Reflect interface settings as data-attributes on <html>; CSS does the rest. */
export function useApplySettings(): 'light' | 'dark' {
  const settings = useSettings((s) => s);
  const theme = resolveTheme(settings.theme, usePrefersDark());
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.dataset.accent = settings.accent;
    root.dataset.font = settings.fontSize;
    root.dataset.density = settings.density;
    root.dataset.width = settings.width;
    root.style.colorScheme = theme;
  }, [theme, settings.accent, settings.fontSize, settings.density, settings.width]);
  return theme;
}
