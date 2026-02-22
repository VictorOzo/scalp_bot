'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { ApiError, apiFetch } from '@/lib/api';

export function useRole() {
  const router = useRouter();
  const query = useQuery({
    queryKey: ['role'],
    queryFn: async () => {
      try {
        await apiFetch<Record<string, unknown>>('/settings');
        return 'admin' as const;
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) return 'viewer' as const;
        throw err;
      }
    },
    retry: false
  });

  useEffect(() => {
    if (query.error instanceof ApiError && query.error.status === 401) router.push('/login');
  }, [query.error, router]);

  return query;
}
