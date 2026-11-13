export function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** idx;
  return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
    return '0s';
  }
  const total = Math.round(Number(seconds));
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

export function formatPercent(ratio) {
  if (ratio === null || ratio === undefined || Number.isNaN(Number(ratio))) {
    return '0%';
  }
  return `${(Number(ratio) * 100).toFixed(1)}%`;
}

export function formatNumber(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) {
    return '0';
  }
  return Number(val).toLocaleString();
}
