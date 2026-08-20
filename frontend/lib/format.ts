export function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 Bytes";
  
    const units = ["Bytes", "KB", "MB", "GB"];
    const index = Math.floor(Math.log(bytes) / Math.log(1024));
  
    const value = bytes / Math.pow(1024, index);
  
    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }
  
export function formatDate(date: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(date));
}

export function formatRelativeTime(date: string): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const diffMs = now - then;
  const diffMinutes = Math.floor(diffMs / 60_000);

  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(date),
  );
}