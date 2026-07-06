export interface paths {
  "/sessions": {
    get: {
      responses: { 200: { content: { "application/json": Session[] } } };
    };
    post: {
      requestBody: { content: { "application/json": CreateSessionRequest } };
      responses: { 201: { content: { "application/json": Session } } };
    };
  };
  "/sessions/{id}": {
    get: {
      parameters: { path: { id: string } };
      responses: { 200: { content: { "application/json": Session } } };
    };
  };
  "/sessions/{id}/analysis": {
    get: {
      parameters: { path: { id: string } };
      responses: { 200: { content: { "application/json": AnalysisReport } } };
    };
  };
}

export interface Session {
  id: string;
  user_id: string;
  title: string;
  language: string;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  turn_count: number;
  duration_ms: number;
  scores: CommunicationScores | null;
}

export type SessionStatus = "idle" | "connecting" | "live" | "reconnecting" | "ended";

export interface CreateSessionRequest {
  title: string;
  language?: string;
}

export interface CommunicationScores {
  overall: number;
  dimensions: DimensionScore[];
}

export interface DimensionScore {
  dimension: string;
  score: number;
  confidence: number;
  rationale: string;
  evidence: EvidenceRef[];
}

export interface EvidenceRef {
  type: "turn" | "embedding" | "document" | "event";
  id: string;
  quote: string | null;
  start_ms: number | null;
  end_ms: number | null;
}

export interface AnalysisReport {
  session_id: string;
  scores: CommunicationScores;
  coaching: CoachingAction[];
  summary: string;
  evidence: EvidenceRef[];
  agent_trace: AgentStepTrace[];
  confidence: number;
  degraded: boolean;
  degradation_reason: string | null;
}

export interface CoachingAction {
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  practice_tip: string;
  related_turns: string[];
  dimension: string;
}

export interface AgentStepTrace {
  agent: string;
  started_at: string;
  duration_ms: number;
  input_summary: string;
  output: Record<string, unknown>;
  model: string;
  token_usage: TokenUsage | null;
  error: string | null;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TurnNode {
  id: string;
  speaker_label: string;
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
  acoustic_labels: Record<string, string>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  weight: number;
}
