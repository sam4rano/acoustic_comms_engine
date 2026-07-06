export type WsMessageType =
  | "audio_chunk"
  | "transcript_delta"
  | "transcript_final"
  | "acoustic_label"
  | "emotion"
  | "prosody"
  | "stress"
  | "session_state"
  | "error";

export interface WsMessage {
  type: WsMessageType;
  payload: unknown;
  ts: number;
}

export interface AudioChunkPayload {
  sequence: number;
  data: string;
  sample_rate: number;
}

export interface TranscriptDeltaPayload {
  turn_id: string;
  text: string;
  is_final: boolean;
  speaker_label: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
}

export interface AcousticLabelPayload {
  turn_id: string;
  head: "emotion" | "prosody" | "stress" | "fluency";
  label: string;
  score: number;
  start_ms: number;
  end_ms: number;
}

export interface SessionStatePayload {
  status: "idle" | "connecting" | "live" | "reconnecting" | "ended";
  session_id: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}
