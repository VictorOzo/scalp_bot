'use client';

import { useQuery } from '@tanstack/react-query';

import { Shell } from '@/components/shell';
import { Card } from '@/components/ui';
import { useRole } from '@/hooks/useRole';
import { apiFetch } from '@/lib/api';

export default function PositionsPage() {
  const role = useRole();
  const positions = useQuery({ queryKey: ['positions'], queryFn: () => apiFetch<any[]>('/positions') });
  const status = useQuery({ queryKey: ['status-pos'], queryFn: () => apiFetch<any>('/status') });

  if (!role.data) return <div className="p-6">Loading...</div>;

  return (
    <Shell role={role.data}>
      <div className="space-y-4" data-testid="positions-page">
        {(positions.data || []).map((p) => (
          <Card key={p.id}>
            <div className="flex items-center justify-between">
              <div>{p.pair} {p.side} {p.units}</div>
              <button
                className="rounded bg-rose-700 px-3 py-1"
                onClick={async () => {
                  await apiFetch('/commands', { method: 'POST', body: JSON.stringify({ type: 'CLOSE_PAIR', payload: { pair: p.pair, mode: 'PAPER' } }) });
                  alert('Close command queued');
                }}
              >Close</button>
            </div>
          </Card>
        ))}

        {role.data === 'admin' && (
          <button
            data-testid="close-all"
            className="rounded bg-rose-800 px-3 py-2"
            disabled={status.data?.live_trading_enabled === false && (positions.data || []).length === 0}
            onClick={async () => {
              if (!confirm('Close all positions?')) return;
              await apiFetch('/commands', { method: 'POST', body: JSON.stringify({ type: 'CLOSE_ALL', payload: {} }) });
              alert('CLOSE_ALL queued');
            }}
          >
            CLOSE ALL
          </button>
        )}
      </div>
    </Shell>
  );
}
