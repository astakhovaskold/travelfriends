import {PHT} from './photos';

const cache = new Map<string, string>();

export async function photo(
  dest: string,
  signal?: AbortSignal,
): Promise<string> {
  const cached = cache.get(dest);
  if (cached !== undefined) {
    return cached;
  }
  const key = `ph1:${dest}`;
  try {
    const saved = localStorage.getItem(key);
    if (saved !== null) {
      cache.set(dest, saved);
      return saved;
    }
  } catch {
  }
  try {
    const response = await fetch(
      'https://en.wikipedia.org/api/rest_v1/page/summary/' +
      encodeURIComponent(
        ((PHT as Record<string, string>)[dest] || dest).replace(/ /g, '_'),
      ),
      {
        signal,
      },
    );
    const data = response.ok ? await response.json() : {};
    const url = data?.thumbnail?.source || '';
    cache.set(dest, url);
    try {
      localStorage.setItem(key, url);
    } catch {
    }
    return url;
  } catch {
    return '';
  }
}

export const big = (url: string, pixels: number) =>
  url.replace(/\/\d+px-/, `/${pixels}px-`);
