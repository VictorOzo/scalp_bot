export function formatPips(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${value.toFixed(1)} pips`;
}

export function formatUtc(value: string | null | undefined): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString();
}

export function statusToBadgeVariant(status: string): 'green' | 'yellow' | 'red' | 'slate' {
  const s = status.toUpperCase();
  if (['SUCCEEDED', 'OPEN', 'BUY', 'PASS'].includes(s)) return 'green';
  if (['PENDING', 'RUNNING', 'HOLD', 'SKIPPED'].includes(s)) return 'yellow';
  if (['FAILED', 'BLOCK'].includes(s)) return 'red';
  return 'slate';
}
