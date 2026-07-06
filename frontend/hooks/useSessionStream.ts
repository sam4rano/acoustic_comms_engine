"use client";

import { useEffect, useRef, useCallback } from "react";
import { useSessionStore } from "@/stores/session-store";
import { WebSocketReconnector } from "@/lib/reconnect";
import type { WsMessage } from "@/lib/ws-protocol";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export function useSessionStream(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnector = useRef(new WebSocketReconnector());
  const setConnectionStatus = useSessionStore((s) => s.setConnectionStatus);

  const connect = useCallback(async () => {
    setConnectionStatus("connecting");
    try {
      const ws = await reconnector.current.connect(`${WS_URL}/${sessionId}`, {
        onReconnect: (attempt) => {
          setConnectionStatus("reconnecting");
          console.info(`Reconnecting (attempt ${attempt})`);
        },
        onMaxAttempts: () => {
          setConnectionStatus("idle");
          console.error("Max reconnection attempts reached");
        },
      });
      wsRef.current = ws;
      setConnectionStatus("live");
    } catch {
      setConnectionStatus("idle");
    }
  }, [sessionId, setConnectionStatus]);

  const disconnect = useCallback(() => {
    reconnector.current.abort();
    wsRef.current?.close();
    wsRef.current = null;
    setConnectionStatus("idle");
  }, [setConnectionStatus]);

  useEffect(() => {
    return () => {
      reconnector.current.abort();
      wsRef.current?.close();
    };
  }, []);

  return { connect, disconnect, ws: wsRef };
}

export function useWsHandler(handler: (msg: WsMessage) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  return ref;
}
