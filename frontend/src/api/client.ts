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
const sessionKey = 'tf_access_token';
let exchange: Promise<string> | undefined;

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function storedSession(): string {
  try {
    return localStorage.getItem(sessionKey) || '';
  } catch {
    return '';
  }
}

function saveSession(token: string) {
  try {
    localStorage.setItem(sessionKey, token);
  } catch {
    // Telegram webviews can disable storage; the in-flight session still works.
  }
}

function clearSession() {
  try {
    localStorage.removeItem(sessionKey);
  } catch {
  }
}

async function exchangeTelegram(): Promise<string> {
  if (!platform.initData) {
    throw new ApiError('unauthorized', 401);
  }
  if (!exchange) {
    exchange = fetch(`${apiOrigin}/api/auth/telegram`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        init_data: platform.initData,
      }),
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || typeof data.access_token !== 'string') {
          throw new ApiError(errorDetail(data.detail), response.status);
        }
        saveSession(data.access_token);
        return data.access_token;
      })
      .finally(() => {
        exchange = undefined;
      });
  }
  return exchange;
}

export async function api<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  signal?: AbortSignal,
  retry = true,
): Promise<T> {
  const token = storedSession();
  const response = await fetch(`${apiOrigin}/api${path}`, {
    method,
    signal,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': platform.initData,
      ...(token
        ? {
          Authorization: `Bearer ${token}`,
        }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && retry && path !== '/auth/telegram') {
    clearSession();
    await exchangeTelegram();
    return api<T>(path, method, body, signal, false);
  }
  if (!response.ok) {
    throw new ApiError(errorDetail(data.detail), response.status);
  }
  return data as T;
}
