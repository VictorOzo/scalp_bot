'use client';

import { useQuery } from '@tanstack/react-query';

import { Shell } from '@/components/shell';
import { Card } from '@/components/ui';
import { useRole } from '@/hooks/useRole';
import { ApiError, apiFetch } from '@/lib/api';

export default function AuditPage() {
  const role = useRole();
  const audit = useQuery({
    queryKey: ['audit'],
    queryFn: async () => {
      try {
        return await apiFetch<any[]>('/audit');
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    }
  });

  if (!role.data) return <div className="p-6">Loading...</div>;

  return (
    <Shell role={role.data}>
      <Card data-testid="audit-page">
        <h2 className="mb-2 text-lg">Audit</h2>
        {audit.data === null ? <p>Audit endpoint not available</p> : <pre>{JSON.stringify(audit.data, null, 2)}</pre>}
      </Card>
    </Shell>
  );
}
