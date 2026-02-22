const CANDIDATE_KEYS = ['pairs', 'watchlist', 'symbols', 'instruments'] as const;

export function getPairsFromSettings(settings: Record<string, unknown>): string[] {
  for (const key of CANDIDATE_KEYS) {
    const value = settings[key];
    if (Array.isArray(value)) {
      const pairs = value.filter((item): item is string => typeof item === 'string' && item.length > 0);
      if (pairs.length) return pairs;
    }
  }
  return [];
}
