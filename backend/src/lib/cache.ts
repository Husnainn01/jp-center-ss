/**
 * Simple in-memory cache with TTL. No Redis needed at this scale.
 * Cache is invalidated when scraper syncs (via POST /api/cache/invalidate).
 */

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
}

const store = new Map<string, CacheEntry<unknown>>();

const DEFAULT_TTL_MS = 2 * 60 * 1000; // 2 minutes default

export function cacheGet<T>(key: string): T | null {
  const entry = store.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return null;
  }
  return entry.data as T;
}

export function cacheSet<T>(key: string, data: T, ttlMs = DEFAULT_TTL_MS): void {
  store.set(key, { data, expiresAt: Date.now() + ttlMs });
}

export function cacheInvalidate(pattern?: string): number {
  if (!pattern) {
    const count = store.size;
    store.clear();
    return count;
  }
  let count = 0;
  for (const key of store.keys()) {
    if (key.includes(pattern)) {
      store.delete(key);
      count++;
    }
  }
  return count;
}

/**
 * Cache-through helper: returns cached value or calls fn() and caches the result.
 */
export async function cached<T>(key: string, fn: () => Promise<T>, ttlMs = DEFAULT_TTL_MS): Promise<T> {
  const hit = cacheGet<T>(key);
  if (hit !== null) return hit;
  const data = await fn();
  cacheSet(key, data, ttlMs);
  return data;
}
