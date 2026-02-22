'use client';

import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { Shell } from '@/components/shell';
import { Card } from '@/components/ui';
import { useRole } from '@/hooks/useRole';
import { apiFetch, downloadTradesXlsx } from '@/lib/api';
import { formatUtc } from '@/lib/format';
import { getPairsFromSettings } from '@/lib/pairs';

export default function TradesPage() {
  const role = useRole();
  const [cursor, setCursor] = useState<number | null>(null);
  const [filters, setFilters] = useState({ pair: '', from_ts: '', to_ts: '', side: '', mode: '', command_id: '', limit: '50' });

  const settingsQuery = useQuery({ queryKey: ['settings-trades'], queryFn: () => apiFetch<Record<string, unknown>>('/settings'), retry: false });
  const pairs = settingsQuery.data ? getPairsFromSettings(settingsQuery.data) : [];

  const searchParams = useMemo(() => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) if (v) p.set(k, v);
    if (cursor) p.set('cursor', String(cursor));
    return p;
  }, [filters, cursor]);

  const tradesQuery = useQuery({
    queryKey: ['trades', searchParams.toString()],
    queryFn: () => apiFetch<{ items: any[]; next_cursor: number | null }>(`/trades?${searchParams.toString()}`)
  });

  if (!role.data) return <div className="p-6">Loading...</div>;

  return (
    <Shell role={role.data}>
      <div data-testid="trades-page" className="space-y-4">
        <Card>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <select value={filters.pair} onChange={(e) => setFilters((f) => ({ ...f, pair: e.target.value }))} className="rounded bg-slate-800 p-2">
              <option value="">All pairs</option>
              {pairs.map((pair) => <option key={pair} value={pair}>{pair}</option>)}
            </select>
            <input placeholder="from_ts" className="rounded bg-slate-800 p-2" value={filters.from_ts} onChange={(e) => setFilters((f) => ({ ...f, from_ts: e.target.value }))} />
            <input placeholder="to_ts" className="rounded bg-slate-800 p-2" value={filters.to_ts} onChange={(e) => setFilters((f) => ({ ...f, to_ts: e.target.value }))} />
            <input placeholder="command_id" className="rounded bg-slate-800 p-2" value={filters.command_id} onChange={(e) => setFilters((f) => ({ ...f, command_id: e.target.value }))} />
          </div>
          <button
            data-testid="export-trades"
            className="mt-3 rounded bg-blue-700 px-3 py-2"
            onClick={async () => {
              const blob = await downloadTradesXlsx(searchParams);
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'trades.xlsx';
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Export XLSX
          </button>
        </Card>

        <Card>
          <table className="w-full text-left text-sm" data-testid="trades-table">
            <thead><tr><th>ID</th><th>Pair</th><th>Side</th><th>Opened</th></tr></thead>
            <tbody>
              {(tradesQuery.data?.items || []).map((trade) => (
                <tr key={trade.id}><td>{trade.id}</td><td>{trade.pair}</td><td>{trade.side}</td><td>{formatUtc(trade.opened_ts_utc)}</td></tr>
              ))}
            </tbody>
          </table>
          <button className="mt-3 rounded bg-slate-700 px-3 py-1" onClick={() => setCursor(tradesQuery.data?.next_cursor ?? null)}>Next</button>
        </Card>
      </div>
    </Shell>
  );
}
