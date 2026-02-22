import { describe, expect, it } from 'vitest';

import { loginSchema, settingsSchema } from '@/lib/schemas';

describe('schema validation', () => {
  it('login schema rejects empty', () => {
    expect(loginSchema.safeParse({ username: '', password: '' }).success).toBe(false);
  });

  it('settings schema rejects invalid ranges', () => {
    expect(settingsSchema.safeParse({ risk_pct: -1 }).success).toBe(false);
    expect(settingsSchema.safeParse({ command_poll_interval_sec: 999 }).success).toBe(false);
    expect(settingsSchema.safeParse({ risk_pct: 0.01, default_units: 1000 }).success).toBe(true);
  });
});
