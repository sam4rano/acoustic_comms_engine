export type WsMessageType =
  | "audio_frame"
  | "start_session"
  | "end_session"
  | "transcript"
  | "acoustic_label"
  | "audio_event"
  | "error"
  | "state_change"
  | "ping"
  | "pong"
  | "config_update";

export interface WsMessage {
  type: WsMessageType;
  payload: unknown;
  message_id?: string;
}

export interface TranscriptPayload {
  turn_id: string;
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
  is_partial: boolean;
  speaker_label: string;
}

export interface AcousticLabelPayload {
  head: string;
  label: string;
  confidence: number;
  metadata?: Record<string, unknown>;
  turn_id: string;
}

export interface StateChangePayload {
  session_id: string;
  status: string;
  config?: Record<string, unknown>;
  frames_processed?: number;
  errors?: number;
}

export interface ErrorPayload {
  message: string;
  sequence?: number;
}
