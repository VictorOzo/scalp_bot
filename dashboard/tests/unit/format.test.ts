import { describe, expect, it } from 'vitest';

import { formatPips, formatUtc, statusToBadgeVariant } from '@/lib/format';

describe('format utils', () => {
  it('formatPips', () => {
    expect(formatPips(12.345)).toBe('12.3 pips');
    expect(formatPips(null)).toBe('-');
  });

  it('formatUtc', () => {
    expect(formatUtc('2025-01-01T00:00:00+00:00')).toContain('2025-01-01T00:00:00.000Z');
    expect(formatUtc('')).toBe('-');
  });

  it('statusToBadgeVariant', () => {
    expect(statusToBadgeVariant('SUCCEEDED')).toBe('green');
    expect(statusToBadgeVariant('PENDING')).toBe('yellow');
    expect(statusToBadgeVariant('FAILED')).toBe('red');
  });
});
