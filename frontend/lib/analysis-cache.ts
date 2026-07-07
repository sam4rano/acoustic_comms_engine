const ANALYSIS_CACHE_KEY = "acoustic_comms_analysis_cache";
const MAX_CACHE_ENTRIES = 20;

interface CachedAnalysis {
  sessionId: string;
  data: Record<string, unknown>;
  cachedAt: number;
}

function _loadCache(): Record<string, CachedAnalysis> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(ANALYSIS_CACHE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, CachedAnalysis>;
  } catch {
    return {};
  }
}

function _saveCache(cache: Record<string, CachedAnalysis>): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(ANALYSIS_CACHE_KEY, JSON.stringify(cache));
  } catch {
    // localStorage full — evict oldest entries
    const entries = Object.entries(cache).sort((a, b) => a[1].cachedAt - b[1].cachedAt);
    const trimmed = Object.fromEntries(entries.slice(-MAX_CACHE_ENTRIES));
    try {
      localStorage.setItem(ANALYSIS_CACHE_KEY, JSON.stringify(trimmed));
    } catch {
      // still too large — keep half
      const half = Object.fromEntries(entries.slice(-Math.floor(MAX_CACHE_ENTRIES / 2)));
      localStorage.setItem(ANALYSIS_CACHE_KEY, JSON.stringify(half));
    }
  }
}

export function getCachedAnalysis(sessionId: string): Record<string, unknown> | null {
  const cache = _loadCache();
  return cache[sessionId]?.data ?? null;
}

export function setCachedAnalysis(sessionId: string, data: Record<string, unknown>): void {
  const cache = _loadCache();
  cache[sessionId] = { sessionId, data, cachedAt: Date.now() };
  _saveCache(cache);
}

export function hasCachedAnalysis(sessionId: string): boolean {
  const cache = _loadCache();
  return sessionId in cache;
}
