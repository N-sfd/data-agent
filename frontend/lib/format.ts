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