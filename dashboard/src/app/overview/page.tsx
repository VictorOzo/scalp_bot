'use client';

import { useQuery } from '@tanstack/react-query';

import { Shell } from '@/components/shell';
import { Badge, Card } from '@/components/ui';
import { apiFetch } from '@/lib/api';
import { getPairsFromSettings } from '@/lib/pairs';
import { statusToBadgeVariant } from '@/lib/format';
import { useRole } from '@/hooks/useRole';

const pollMs = Number(process.env.NEXT_PUBLIC_POLL_MS || '3000');

export default function OverviewPage() {
  const roleQuery = useRole();
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: () => apiFetch<any>('/status'), refetchInterval: pollMs });
  const settingsQuery = useQuery({ queryKey: ['settings-overview'], queryFn: () => apiFetch<Record<string, unknown>>('/settings'), retry: false });

  const pairs = settingsQuery.data ? getPairsFromSettings(settingsQuery.data) : [];
  const gatesQuery = useQuery({
    queryKey: ['gates', pairs.join(',')],
    queryFn: async () => Promise.all(pairs.map(async (pair) => ({ pair, data: await apiFetch<any[]>(`/gates?pair=${pair}&limit=1`) }))),
    enabled: pairs.length > 0,
    refetchInterval: pollMs
  });

  if (!roleQuery.data) return <div className="p-6">Loading...</div>;

  return (
    <Shell role={roleQuery.data}>
      <div className="space-y-4" data-testid="overview-page">
        <Card>
          <h2 className="mb-2 text-lg">Status</h2>
          <p data-testid="status-mode">Mode: {statusQuery.data?.mode ?? '-'}</p>
          <p>Last cycle: {statusQuery.data?.last_cycle_ts_utc ?? '-'}</p>
        </Card>

        {pairs.length === 0 ? (
          <Card><p>No pairs configured in settings.</p></Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {pairs.map((pair) => {
              const gate = gatesQuery.data?.find((x) => x.pair === pair)?.data?.[0];
              const reason = gate?.reasons?.[0] || 'n/a';
              const status = gate?.allowed ? 'PASS' : 'HOLD';
              return (
                <Card key={pair}>
                  <div className="flex items-center justify-between">
                    <h3 data-testid={`pair-card-${pair}`} className="font-semibold">{pair}</h3>
                    <Badge text={status} variant={statusToBadgeVariant(status)} />
                  </div>
                  <p className="mt-2 text-sm text-slate-300">Reason: {reason}</p>
                  {roleQuery.data === 'admin' && (
                    <button
                      data-testid={`pause-${pair}`}
                      className="mt-3 rounded bg-amber-700 px-3 py-1 text-sm"
                      onClick={async () => {
                        await apiFetch('/commands', {
                          method: 'POST',
                          body: JSON.stringify({ type: 'PAUSE_PAIR', payload: { pair } })
                        });
                        alert('Command queued');
                      }}
                    >
                      Pause Pair
                    </button>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </Shell>
  );
}
