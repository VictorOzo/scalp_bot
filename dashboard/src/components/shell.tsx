'use client';

import { useRouter } from 'next/navigation';
import { ReactNode } from 'react';

import { apiFetch } from '@/lib/api';
import { SidebarLink } from './ui';

export function Shell({ children, role }: { children: ReactNode; role: 'admin' | 'viewer' }) {
  const router = useRouter();

  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr]" data-testid="app-shell">
      <aside className="border-r border-slate-800 p-3">
        <h1 className="mb-4 text-lg font-semibold">Scalp Dashboard</h1>
        <SidebarLink href="/overview" label="Overview" />
        <SidebarLink href="/trades" label="Trades" />
        <SidebarLink href="/positions" label="Positions" />
        <SidebarLink href="/audit" label="Audit" />
        {role === 'admin' && <SidebarLink href="/settings" label="Settings" />}
      </aside>
      <main className="p-4">
        <div className="mb-4 flex justify-end">
          <button
            data-testid="logout-btn"
            className="rounded bg-slate-700 px-3 py-2"
            onClick={async () => {
              await apiFetch('/auth/logout', { method: 'POST' });
              router.push('/login');
            }}
          >
            Logout
          </button>
        </div>
        {children}
      </main>
    </div>
  );
}
