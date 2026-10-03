import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

import { ACCENTS, useSettings, type Settings } from '../state/settingsStore';

function Choice<K extends keyof Settings>({
  label,
  field,
  options,
}: {
  label: string;
  field: K;
  options: { value: Settings[K]; label: string }[];
}) {
  const value = useSettings((s) => s[field]);
  const update = useSettings((s) => s.update);
  return (
    <fieldset className="setting">
      <legend>{label}</legend>
      <div className="segmented">
        {options.map((option) => (
          <button
            key={String(option.value)}
            type="button"
            className={value === option.value ? 'segmented__item segmented__item--active' : 'segmented__item'}
            aria-pressed={value === option.value}
            onClick={() => update({ [field]: option.value } as Partial<Settings>)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const settings = useSettings((s) => s);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal?.();
    if (!open && el.open) el.close?.();
  }, [open]);

  return (
    <dialog ref={dialog} className="settings-dialog" onClose={onClose} aria-label="Settings">
      {open && (
        <div className="settings-dialog__body">
          <header>
            <h2>Settings</h2>
            <button type="button" className="icon-button" aria-label="Close settings" onClick={onClose}>
              <X size={16} />
            </button>
          </header>
          <Choice
            label="Theme"
            field="theme"
            options={[
              { value: 'system', label: 'System' },
              { value: 'light', label: 'Light' },
              { value: 'dark', label: 'Dark' },
            ]}
          />
          <fieldset className="setting">
            <legend>Accent colour</legend>
            <div className="swatches">
              {ACCENTS.map((accent) => (
                <button
                  key={accent}
                  type="button"
                  className={`swatch swatch--${accent} ${settings.accent === accent ? 'swatch--active' : ''}`}
                  aria-label={accent}
                  aria-pressed={settings.accent === accent}
                  onClick={() => settings.update({ accent })}
                />
              ))}
            </div>
          </fieldset>
          <Choice
            label="Text size"
            field="fontSize"
            options={[
              { value: 'sm', label: 'Small' },
              { value: 'md', label: 'Medium' },
              { value: 'lg', label: 'Large' },
            ]}
          />
          <Choice
            label="Density"
            field="density"
            options={[
              { value: 'comfortable', label: 'Comfortable' },
              { value: 'compact', label: 'Compact' },
            ]}
          />
          <Choice
            label="Chat width"
            field="width"
            options={[
              { value: 'normal', label: 'Normal' },
              { value: 'wide', label: 'Wide' },
            ]}
          />
          <label className="setting setting--toggle">
            <input
              type="checkbox"
              checked={settings.showToolActivity}
              onChange={(e) => settings.update({ showToolActivity: e.target.checked })}
            />
            Show tool activity (searches, calculations)
          </label>
          <label className="setting setting--toggle">
            <input
              type="checkbox"
              checked={settings.enterToSend}
              onChange={(e) => settings.update({ enterToSend: e.target.checked })}
            />
            Press Enter to send (Shift+Enter for a new line)
          </label>
          <footer>
            <button type="button" className="button button--ghost" onClick={settings.reset}>
              Reset to defaults
            </button>
            <p className="settings-dialog__privacy">
              Conversations are stored only in this browser. Uploaded files are deleted from the server after
              24 hours.
            </p>
          </footer>
        </div>
      )}
    </dialog>
  );
}
