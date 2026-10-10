import {platform} from '../platform/telegram';

export function errorDetail(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v?.msg === 'string' ? v.msg : 'Invalid value'))
      .join('; ');
  }
  return 'Error';
}

const apiOrigin = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export async function api<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${apiOrigin}/api${path}`, {
    method,
    signal,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': platform.initData,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(errorDetail(data.detail));
  }
  return data as T;
}
