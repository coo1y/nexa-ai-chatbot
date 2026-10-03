import { DEFAULT_SETTINGS, loadSettings, resolveTheme, settingsStore } from './settingsStore';

describe('settings', () => {
  it('resolves the system theme', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
  });

  it('persists updates and validates stored values', () => {
    settingsStore.getState().update({ theme: 'dark', accent: 'rose' });
    expect(loadSettings(localStorage)).toMatchObject({ theme: 'dark', accent: 'rose' });
    localStorage.setItem('nexa.settings.v1', JSON.stringify({ accent: 'neon', fontSize: 'lg' }));
    expect(loadSettings(localStorage)).toMatchObject({ accent: 'indigo', fontSize: 'lg' });
    localStorage.setItem('nexa.settings.v1', '{broken');
    expect(loadSettings(localStorage)).toEqual(DEFAULT_SETTINGS);
    settingsStore.getState().reset();
    expect(settingsStore.getState().theme).toBe('system');
  });
});
