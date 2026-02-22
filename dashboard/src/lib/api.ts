export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API Error ${status}`);
    this.status = status;
    this.body = body;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function parseBody(res: Response): Promise<unknown> {
  const type = res.headers.get('content-type') || '';
  if (type.includes('application/json')) return res.json();
  return res.text();
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      ...(init?.headers ?? {})
    }
  });
  const body = await parseBody(res);
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export async function downloadTradesXlsx(query: URLSearchParams): Promise<Blob> {
  const res = await fetch(`${API_BASE}/exports/trades.xlsx?${query.toString()}`, { credentials: 'include' });
  if (!res.ok) throw new ApiError(res.status, await parseBody(res));
  return res.blob();
}
