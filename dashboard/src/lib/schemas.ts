import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required')
});

export const settingsSchema = z.object({
  risk_pct: z.number().min(0).max(0.1).optional(),
  default_units: z.number().int().min(1).max(1_000_000).optional(),
  command_poll_interval_sec: z.number().min(0.1).max(60).optional()
}).passthrough();
