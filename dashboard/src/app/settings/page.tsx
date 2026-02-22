'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Shell } from '@/components/shell';
import { Card } from '@/components/ui';
import { useRole } from '@/hooks/useRole';
import { ApiError, apiFetch } from '@/lib/api';
import { settingsSchema } from '@/lib/schemas';

export default function SettingsPage() {
  const router = useRouter();
  const role = useRole();
  const [message, setMessage] = useState('');
  const settingsQuery = useQuery({ queryKey: ['settings-page'], queryFn: () => apiFetch<Record<string, unknown>>('/settings'), retry: false });

  if (role.data === 'viewer') {
    router.push('/overview');
    return null;
  }
  if (!role.data) return <div className="p-6">Loading...</div>;

  return (
    <Shell role={role.data}>
      <Card>
        <h2 className="mb-3 text-lg">Settings (JSON)</h2>
        <textarea data-testid="settings-json" className="h-80 w-full rounded bg-slate-800 p-2" defaultValue={JSON.stringify(settingsQuery.data || {}, null, 2)} />
        <button
          className="mt-3 rounded bg-blue-700 px-3 py-2"
          onClick={async () => {
            const text = (document.querySelector('[data-testid=settings-json]') as HTMLTextAreaElement).value;
            try {
              const parsed = settingsSchema.parse(JSON.parse(text));
              await apiFetch('/settings', { method: 'PUT', body: JSON.stringify(parsed) });
              setMessage('Saved');
            } catch (err) {
              setMessage(err instanceof ApiError ? `Save failed (${err.status})` : 'Validation failed');
            }
          }}
        >Save</button>
        {message && <p className="mt-2">{message}</p>}
      </Card>
    </Shell>
  );
}
