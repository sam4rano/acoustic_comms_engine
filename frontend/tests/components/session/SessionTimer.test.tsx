import { render, screen, act } from '@testing-library/react';
import { SessionTimer } from '@/components/session/SessionTimer';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('SessionTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('displays initial elapsed time as 00:00', () => {
    const now = Date.now();
    render(<SessionTimer startedAt={new Date(now)} />);

    expect(screen.getByText('00:00')).toBeInTheDocument();
  });

  it('shows time in MM:SS format after first tick', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    vi.setSystemTime(new Date('2026-01-01T00:00:59Z'));
    render(<SessionTimer startedAt={startedAt} />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText('01:00')).toBeInTheDocument();
  });

  it('updates elapsed time every second', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    render(<SessionTimer startedAt={startedAt} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText('00:05')).toBeInTheDocument();
  });

  it('pads single-digit minutes and seconds', () => {
    const startedAt = new Date('2026-01-01T00:00:05Z');
    vi.setSystemTime(new Date('2026-01-01T00:00:05Z'));
    render(<SessionTimer startedAt={startedAt} />);

    act(() => {
      vi.advanceTimersByTime(55000);
    });

    expect(screen.getByText('00:55')).toBeInTheDocument();
  });
});
