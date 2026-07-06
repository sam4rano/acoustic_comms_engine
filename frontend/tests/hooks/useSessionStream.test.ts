import { renderHook } from '@testing-library/react';
import { useSessionStream } from '@/hooks/useSessionStream';
import { useSessionStore } from '@/stores/session-store';
import { WebSocketReconnector } from '@/lib/reconnect';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('@/lib/reconnect', () => ({
  WebSocketReconnector: vi.fn().mockImplementation(() => ({
    connect: vi.fn().mockResolvedValue({
      close: vi.fn(),
    }),
    abort: vi.fn(),
  })),
}));

vi.mock('@/stores/session-store', () => ({
  useSessionStore: vi.fn(),
}));

describe('useSessionStream', () => {
  const mockSetConnectionStatus = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    const store = {
      setConnectionStatus: mockSetConnectionStatus,
    };
    vi.mocked(useSessionStore).mockImplementation((selector: any) => {
      if (typeof selector === 'function') {
        return selector(store);
      }
      return store;
    });
  });

  it('returns expected interface shape', () => {
    const { result } = renderHook(() => useSessionStream('session-1'));

    expect(result.current).toHaveProperty('connect');
    expect(result.current).toHaveProperty('disconnect');
    expect(result.current).toHaveProperty('ws');
    expect(typeof result.current.connect).toBe('function');
    expect(typeof result.current.disconnect).toBe('function');
  });

  it('sets connection status to idle on disconnect', async () => {
    const { result } = renderHook(() => useSessionStream('session-1'));

    result.current.disconnect();

    expect(mockSetConnectionStatus).toHaveBeenCalledWith('idle');
  });
});
