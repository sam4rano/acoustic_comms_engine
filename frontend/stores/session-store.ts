import { create } from "zustand";
import type { Session, SessionStatus } from "@/types";

interface SessionState {
  sessions: Session[];
  activeSession: Session | null;
  connectionStatus: SessionStatus;
  setSessions: (sessions: Session[]) => void;
  setActiveSession: (session: Session | null) => void;
  setConnectionStatus: (status: SessionStatus) => void;
  addSession: (session: Session) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  activeSession: null,
  connectionStatus: "idle",

  setSessions: (sessions) => set({ sessions }),
  setActiveSession: (session) => set({ activeSession: session }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  addSession: (session) =>
    set((state) => ({ sessions: [session, ...state.sessions] })),
}));
