export function relativeTime(timestamp: number, now = Date.now()): string {
  const seconds = Math.round((now - timestamp) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

/** Group label for the sidebar ("Today", "Yesterday", "Previous 7 days", "Older"). */
export function dateGroup(timestamp: number, now = new Date()): string {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 24 * 60 * 60 * 1000;
  if (timestamp >= startOfToday) return 'Today';
  if (timestamp >= startOfToday - day) return 'Yesterday';
  if (timestamp >= startOfToday - 7 * day) return 'Previous 7 days';
  return 'Older';
}
