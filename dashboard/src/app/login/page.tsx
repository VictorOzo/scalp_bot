'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { apiFetch, ApiError } from '@/lib/api';
import { loginSchema } from '@/lib/schemas';

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState('');

  return (
    <div className="mx-auto mt-20 max-w-md rounded border border-slate-800 bg-slate-900 p-6" data-testid="login-page">
      <h1 className="mb-4 text-xl font-semibold">Login</h1>
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setError('');
          const form = new FormData(e.currentTarget);
          const payload = {
            username: String(form.get('username') || ''),
            password: String(form.get('password') || '')
          };
          const parsed = loginSchema.safeParse(payload);
          if (!parsed.success) {
            setError(parsed.error.issues[0]?.message || 'Invalid input');
            return;
          }
          try {
            await apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(parsed.data) });
            router.push('/overview');
          } catch (err) {
            setError(err instanceof ApiError ? `Login failed (${err.status})` : 'Login failed');
          }
        }}
      >
        <input data-testid="username" className="w-full rounded bg-slate-800 p-2" name="username" placeholder="Username" />
        <input data-testid="password" className="w-full rounded bg-slate-800 p-2" name="password" type="password" placeholder="Password" />
        <button data-testid="login-submit" className="w-full rounded bg-blue-700 p-2" type="submit">Sign in</button>
      </form>
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
    </div>
  );
}
