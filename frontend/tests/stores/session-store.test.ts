import { useSessionStore } from '@/stores/session-store';
import { describe, it, expect, beforeEach } from 'vitest';
import type { Session } from '@/types';

const makeSession = (overrides: Partial<Session> = {}): Session => ({
  id: 's1',
  user_id: 'u1',
  title: 'Test Session',
  language: 'en',
  status: 'idle',
  started_at: new Date().toISOString(),
  ended_at: null,
  turn_count: 0,
  duration_ms: 0,
  scores: null,
  ...overrides,
});

describe('session-store', () => {
  beforeEach(() => {
    useSessionStore.setState({
      sessions: [],
      activeSession: null,
      connectionStatus: 'idle',
    });
  });

  it('initialises with default state', () => {
    const state = useSessionStore.getState();
    expect(state.sessions).toEqual([]);
    expect(state.activeSession).toBeNull();
    expect(state.connectionStatus).toBe('idle');
  });

  it('adds a session', () => {
    const session = makeSession();
    useSessionStore.getState().addSession(session);

    const state = useSessionStore.getState();
    expect(state.sessions).toHaveLength(1);
    expect(state.sessions[0]).toEqual(session);
  });

  it('prepends new sessions', () => {
    const s1 = makeSession({ id: 's1' });
    const s2 = makeSession({ id: 's2' });
    useSessionStore.getState().addSession(s1);
    useSessionStore.getState().addSession(s2);

    const state = useSessionStore.getState();
    expect(state.sessions.map((s) => s.id)).toEqual(['s2', 's1']);
  });

  it('sets active session', () => {
    const session = makeSession();
    useSessionStore.getState().setActiveSession(session);

    expect(useSessionStore.getState().activeSession).toEqual(session);
  });

  it('sets connection status', () => {
    useSessionStore.getState().setConnectionStatus('live');

    expect(useSessionStore.getState().connectionStatus).toBe('live');
  });

  it('sets sessions list', () => {
    const sessions = [makeSession({ id: 's1' }), makeSession({ id: 's2' })];
    useSessionStore.getState().setSessions(sessions);

    expect(useSessionStore.getState().sessions).toHaveLength(2);
  });

  it('clears sessions when setting empty array', () => {
    useSessionStore.getState().addSession(makeSession());
    useSessionStore.getState().setSessions([]);

    expect(useSessionStore.getState().sessions).toEqual([]);
  });
});
