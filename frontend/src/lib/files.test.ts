import { DEFAULT_LIMITS, extensionOf, formatBytes, isImageName, validateFile } from './files';
import { dateGroup, relativeTime } from './format';

describe('file helpers', () => {
  it('validates type and size', () => {
    expect(validateFile(new File(['x'], 'ok.pdf'))).toBeNull();
    expect(validateFile(new File(['x'], 'bad.exe'))).toMatch(/unsupported file type \(\.exe\)/);
    expect(validateFile(new File([], 'empty.txt'))).toMatch(/empty/);
    const big = new File(['x'], 'big.txt');
    Object.defineProperty(big, 'size', { value: DEFAULT_LIMITS.max_bytes + 1 });
    expect(validateFile(big)).toMatch(/larger than 10.0 MB/);
  });

  it('detects images and formats sizes', () => {
    expect(isImageName('Photo.JPG')).toBe(true);
    expect(isImageName('doc.pdf')).toBe(false);
    expect(extensionOf('archive')).toBe('');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});

describe('format helpers', () => {
  const now = new Date(2026, 9, 3, 12, 0).getTime();
  it('formats relative times', () => {
    expect(relativeTime(now - 10_000, now)).toBe('just now');
    expect(relativeTime(now - 5 * 60_000, now)).toBe('5m ago');
    expect(relativeTime(now - 3 * 3_600_000, now)).toBe('3h ago');
    expect(relativeTime(now - 2 * 86_400_000, now)).toBe('2d ago');
  });
  it('groups dates for the sidebar', () => {
    const today = new Date(now);
    expect(dateGroup(now - 60_000, today)).toBe('Today');
    expect(dateGroup(now - 86_400_000, today)).toBe('Yesterday');
    expect(dateGroup(now - 4 * 86_400_000, today)).toBe('Previous 7 days');
    expect(dateGroup(now - 30 * 86_400_000, today)).toBe('Older');
  });
});
