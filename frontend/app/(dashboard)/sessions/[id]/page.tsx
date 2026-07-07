"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, BarChart3, Mic, Square } from "lucide-react";
import { SessionTimer } from "@/components/session/SessionTimer";
import { TranscriptPanel } from "@/components/session/TranscriptPanel";
import { DisconnectOverlay } from "@/components/session/DisconnectOverlay";
import { useSessionStream, useWsHandler } from "@/hooks/useSessionStream";
import { useSessionStore } from "@/stores/session-store";
import { hasCachedAnalysis, setCachedAnalysis } from "@/lib/analysis-cache";
import type { WsMessage } from "@/lib/ws-protocol";

/* ── helpers ─────────────────────────────────────────────── */

function uint8ToBase64(bytes: Uint8Array): string {
  const CHUNK = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

function float32ToInt16(samples: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16.buffer;
}

/* ── waveform analyser ───────────────────────────────────── */

function WaveformVisualizer({ stream }: { stream: MediaStream | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    if (!stream) return;
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const analyzer = ctx.createAnalyser();
    analyzer.fftSize = 128;
    src.connect(analyzer);

    const canvas = canvasRef.current;
    if (!canvas) return;

    const draw = () => {
      const data = new Uint8Array(analyzer.frequencyBinCount);
      analyzer.getByteTimeDomainData(data);
      const w = canvas.width;
      const h = canvas.height;
      const c = canvas.getContext("2d");
      if (!c) return;
      c.clearRect(0, 0, w, h);
      c.beginPath();
      c.strokeStyle = "#0d9488";
      c.lineWidth = 2;
      const step = w / data.length;
      for (let i = 0; i < data.length; i++) {
        const x = i * step;
        const y = (data[i] / 255) * h;
        i === 0 ? c.moveTo(x, y) : c.lineTo(x, y);
      }
      c.stroke();
      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animRef.current);
      ctx.close();
    };
  }, [stream]);

  return <canvas ref={canvasRef} width={320} height={60} className="rounded-lg bg-zinc-100 dark:bg-zinc-800" />;
}

/* ── types ────────────────────────────────────────────────── */

interface TranscriptEntry {
  turn_id: string;
  speaker_label: string;
  text: string;
  is_final: boolean;
  timestamp: number;
}

interface AcousticLabel {
  head: string;
  label: string;
  score: number;
  start_ms: number;
  end_ms: number;
}

/* ── page ─────────────────────────────────────────────────── */

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { connect, disconnect, ws } = useSessionStream(id);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  const [startedAt] = useState(() => new Date());
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [acousticLabels, setAcousticLabels] = useState<AcousticLabel[]>([]);
  const [recording, setRecording] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [wsReady, setWsReady] = useState(false);

  const audioChunks = useRef<Uint8Array[]>([]);
  const wsRef = useRef(false);

  useEffect(() => {
    if (hasCachedAnalysis(id)) {
      router.replace(`/sessions/${id}/analysis`);
    }
  }, [id, router]);

  /* ── WebSocket message handler ────────────────────────── */

  const handleMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case "transcript": {
        const p = msg.payload as Record<string, unknown>;
        setTranscripts((prev) => {
          const existing = prev.findIndex((t) => t.turn_id === (p.turn_id as string));
          const entry: TranscriptEntry = {
            turn_id: (p.turn_id as string) || crypto.randomUUID(),
            speaker_label: (p.speaker_label as string) || "Speaker",
            text: (p.text as string) || "",
            is_final: !(p.is_partial as boolean),
            timestamp: Date.now(),
          };
          if (existing >= 0) { const u = [...prev]; u[existing] = entry; return u; }
          return [...prev, entry];
        });
        break;
      }
      case "acoustic_label": {
        const p = msg.payload as Record<string, unknown>;
        setAcousticLabels((prev) => [...prev, {
          head: (p.head as string) || "", label: (p.label as string) || "",
          score: (p.score as number) || 0, start_ms: (p.start_ms as number) || 0, end_ms: (p.end_ms as number) || 0,
        }]);
        break;
      }
      case "state_change": {
        const p = msg.payload as Record<string, unknown>;
        if (p.status === "active") setWsReady(true);
        break;
      }
      case "error":
        console.warn("WS:", (msg.payload as Record<string, unknown>).message);
        break;
    }
  }, []);

  const handlerRef = useWsHandler(handleMessage);

  /* ── start recording ───────────────────────────────────── */

  const startRecording = useCallback(async () => {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      setStream(micStream);

      await connect();
      const sock = ws.current;
      if (!sock) { micStream.getTracks().forEach((t) => t.stop()); return; }

      if (sock.readyState !== WebSocket.OPEN) {
        await new Promise<void>((r) => sock.addEventListener("open", () => r(), { once: true }));
      }

      sock.addEventListener("message", (ev) => {
        try { handlerRef.current(JSON.parse(ev.data)); } catch { /* binary frame */ }
      });

      sock.send(JSON.stringify({ type: "start_session", payload: {
        session_id: id, user_id: "00000000-0000-0000-0000-000000000001",
        sample_rate: 16000, language: "en", enabled_heads: ["asr", "emotion", "prosody", "stress"],
      }}));

      const ctx = new AudioContext({ sampleRate: 16000 });
      const src = ctx.createMediaStreamSource(micStream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      src.connect(processor);
      processor.connect(ctx.destination);

      processor.onaudioprocess = (e) => {
        const chunk = e.inputBuffer.getChannelData(0);
        const pcm = float32ToInt16(chunk);
        audioChunks.current.push(new Uint8Array(pcm));
        if (sock.readyState === WebSocket.OPEN) sock.send(pcm);
      };

      setRecording(true);
    } catch (err) {
      console.error("Mic access failed:", err);
      setStream(null);
    }
  }, [connect, ws, handlerRef, id]);

  /* ── stop recording → analyze ──────────────────────────── */

  const stopRecording = useCallback(async () => {
    setRecording(false);

    const sock = ws.current;
    if (sock?.readyState === WebSocket.OPEN) {
      sock.send(JSON.stringify({ type: "end_session", payload: {} }));
    }
    disconnect();

    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setWsReady(false);

    const chunks = audioChunks.current;
    audioChunks.current = [];

    if (chunks.length === 0) {
      setSessionEnded(true);
      return;
    }

    setAnalyzing(true);
    const total = chunks.reduce((s, c) => s + c.length, 0);
    const combined = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) { combined.set(c, off); off += c.length; }

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/sessions/${id}/analysis/analyze`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audio_data: uint8ToBase64(combined), sample_rate: 16000, channels: 1, bits_per_sample: 16 }) },
      );
      if (res.ok) {
        const data = await res.json();
        if (data.status === "no_speech") {
          setSessionEnded(true);
          return;
        }
        setCachedAnalysis(id, data);
        router.push(`/sessions/${id}/analysis`);
        return;
      }
    } catch { /* fall through */ }
    setAnalyzing(false);
    setSessionEnded(true);
  }, [disconnect, stream, ws, id, router]);

  useEffect(() => { return () => { disconnect(); stream?.getTracks().forEach((t) => t.stop()); }; }, [disconnect, stream]);

  /* ── render states ─────────────────────────────────────── */

  if (analyzing) {
    return (
      <div className="mx-auto max-w-md space-y-6 pt-20 text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
        <h1 className="text-xl font-bold">Analyzing your session…</h1>
        <p className="text-sm text-zinc-500">Transcribing with Whisper and generating communication scores via Groq LLM.</p>
      </div>
    );
  }

  if (sessionEnded) {
    const handleViewAnalysis = () => {
      if (hasCachedAnalysis(id)) {
        router.push(`/sessions/${id}/analysis`);
        return;
      }
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      setAnalyzing(true);
      fetch(`${apiUrl}/sessions/${id}/analysis`)
        .then((r) => r.json())
        .then((data) => {
          if (data && data.status !== "pending") {
            setCachedAnalysis(id, data);
            router.push(`/sessions/${id}/analysis`);
          } else {
            setAnalyzing(false);
          }
        })
        .catch(() => setAnalyzing(false));
    };

    if (analyzing) {
      return (
        <div className="mx-auto max-w-md space-y-6 pt-20 text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          <h1 className="text-xl font-bold">Loading analysis…</h1>
        </div>
      );
    }

    return (
      <div className="mx-auto max-w-md space-y-6 pt-20 text-center">
        <h1 className="text-2xl font-bold">Session Complete</h1>
        <p className="text-sm text-zinc-500">Your session has ended.</p>
        <div className="flex justify-center gap-3">
          <button onClick={handleViewAnalysis}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700">
            <BarChart3 className="h-4 w-4" />View Analysis
          </button>
          <Link href="/sessions" className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800">
            Back to Sessions
          </Link>
        </div>
      </div>
    );
  }

  /* ── recording UI ──────────────────────────────────────── */

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      {/* top bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/sessions" className="text-sm text-zinc-500 hover:text-zinc-700">
            <ArrowLeft className="mr-1 inline h-4 w-4" />Sessions
          </Link>
          <h1 className="text-lg font-bold">Live Session</h1>
          {recording && <SessionTimer startedAt={startedAt} />}
          {recording && wsReady && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-300">
              <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              Connected
            </span>
          )}
        </div>
      </div>

      {/* waveform + record button */}
      <div className="flex flex-col items-center gap-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <WaveformVisualizer stream={stream} />

        {recording ? (
          <button onClick={stopRecording}
            className="inline-flex items-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-bold text-white shadow-lg transition hover:bg-red-700 active:scale-95">
            <Square className="h-4 w-4 fill-white" />
            Stop Recording
          </button>
        ) : (
          <button onClick={startRecording}
            className="inline-flex items-center gap-2 rounded-full bg-teal-600 px-6 py-3 text-sm font-bold text-white shadow-lg transition hover:bg-teal-700 active:scale-95">
            <Mic className="h-4 w-4" />
            Start Recording
          </button>
        )}

        <p className="text-xs text-zinc-400">
          {recording ? "Recording in progress — speak clearly" : "Click to start capturing audio"}
        </p>
      </div>

      {/* transcript */}
      <div className="relative h-[400px]">
        <TranscriptPanel entries={transcripts} />
        <DisconnectOverlay visible={connectionStatus === "reconnecting"} onRetry={() => connect()} />
      </div>
    </div>
  );
}
