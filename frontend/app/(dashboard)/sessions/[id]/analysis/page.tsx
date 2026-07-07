"use client";

import { useEffect, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Gauge, Zap, TrendingUp, Lightbulb, AlertTriangle } from "lucide-react";
import { getCachedAnalysis, setCachedAnalysis } from "@/lib/analysis-cache";

interface DimensionScore {
  dimension: string;
  score: number;
  confidence: number;
  rationale: string;
}

interface CoachingAction {
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  practice_tip: string;
  related_turns: string[];
  dimension: string;
}

interface TranscriptEntry {
  turn_id: string;
  speaker_label: string;
  text: string;
  is_final: boolean;
  timestamp: number;
}

interface DeliveryEvidence {
  wpm: number;
  hesitations: number;
  avg_hesitation_s: number;
  confirmed_fillers: number;
  word_count: number;
  target_word_count: number;
  duration_s: number;
}

interface AnalysisReport {
  session_id: string;
  status?: string;
  overall: number;
  dimensions: DimensionScore[];
  coaching: CoachingAction[];
  summary: string;
  delivery_evidence: DeliveryEvidence;
  transcript: TranscriptEntry[];
  confidence: number;
  degraded: boolean;
  degradation_reason: string | null;
}

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const angle = (score / 100) * 180;
  const color = score >= 70 ? "#0d9488" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex flex-col items-center">
      <svg width="80" height="44" viewBox="0 0 80 44" className="-mb-1">
        <path d="M8 40 A36 36 0 0 1 72 40" fill="none" stroke="#e4e4e7" strokeWidth="6" strokeLinecap="round" />
        <path
          d="M8 40 A36 36 0 0 1 72 40"
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 113} 113`}
        />
      </svg>
      <span className="text-2xl font-bold" style={{ color }}>{Math.round(score)}</span>
      <span className="text-xs text-zinc-500">{label}</span>
    </div>
  );
}

function ScoreBar({ score, label, color }: { score: number; label: string; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-xs font-medium text-zinc-600">{label}</span>
      <div className="flex-1 h-2 bg-zinc-100 rounded-full overflow-hidden dark:bg-zinc-800">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(0, score)}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-10 text-right text-xs font-mono text-zinc-500">{Math.round(score)}</span>
    </div>
  );
}

function formatWPM(wpm: number) {
  return `${Math.round(wpm)} WPM — ${wpm > 160 ? "slightly fast" : wpm < 140 ? "measured" : "ideal pace"}`;
}

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const cached = getCachedAnalysis(id) as AnalysisReport | null;
    if (cached && (cached.status === "complete" || cached.status === "degraded")) {
      if (cached.coaching && cached.coaching.length > 0 && cached.dimensions && cached.dimensions.length > 0) {
        setReport(cached);
        setLoading(false);
        return;
      }
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    fetch(`${apiUrl}/sessions/${id}/analysis`)
      .then((r) => {
        if (!r.ok) throw new Error(`Analysis not available yet (${r.status})`);
        return r.json();
      })
      .then((data) => {
        setReport(data);
        setCachedAnalysis(id, data);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <p className="text-sm text-zinc-500 animate-pulse">Loading analysis...</p>
      </div>
    );
  }

  if (error || !report || (report.status !== "complete" && report.status !== "degraded")) {
    const isNoSpeech = report?.status === "no_speech";
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Analysis</h1>
        <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-sm text-zinc-500">
            {error || (isNoSpeech ? "No speech detected in the recording." : "No analysis available for this session.")}
          </p>
          <p className="mt-2 text-xs text-zinc-400">
            {isNoSpeech ? "Try recording again with clearer audio." : "Complete a recording session first, then check back here."}
          </p>
        </div>
        <Link href="/sessions" className="text-teal-600 text-sm hover:underline">
          &larr; Back to sessions
        </Link>
      </div>
    );
  }

  const scoreColor = report.overall >= 70 ? "#0d9488" : report.overall >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <Link href="/sessions" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300">
          <ArrowLeft className="h-4 w-4" />
          Sessions
        </Link>
      </div>

      {report.degraded && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900/50 dark:bg-amber-900/20">
          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
          <span className="text-amber-800 dark:text-amber-200">{report.degradation_reason}</span>
        </div>
      )}

      {/* Overall Score */}
      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-6">
          <ScoreGauge score={report.overall} label="Overall" />
          <div>
            <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Communication Score</h2>
            <p className="mt-1 text-sm text-zinc-500">{report.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                <Gauge className="h-3 w-3" />
                {report.delivery_evidence.word_count} words
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                <Zap className="h-3 w-3" />
                {formatWPM(report.delivery_evidence.wpm)}
              </span>
              {report.delivery_evidence.hesitations > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                  Hesitations: {report.delivery_evidence.hesitations}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Dimension Scores */}
      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Dimension Scores</h3>
        <div className="space-y-3">
          {report.dimensions.map((d) => {
            const color = d.score >= 70 ? "#0d9488" : d.score >= 50 ? "#f59e0b" : "#ef4444";
            return (
              <div key={d.dimension}>
                <ScoreBar score={d.score} label={d.dimension} color={color} />
                <p className="mt-0.5 ml-32 text-xs text-zinc-400">{d.rationale}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Transcript */}
      {report.transcript.length > 0 && (
        <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Transcript</h3>
          <div className="space-y-3">
            {report.transcript.map((entry) => (
              <div key={entry.turn_id} className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-800/50">
                <span className="text-xs font-medium text-teal-600 dark:text-teal-400">
                  {entry.speaker_label}
                </span>
                <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">{entry.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Coaching Actions */}
      {report.coaching && report.coaching.length > 0 && (
      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="flex items-center gap-2 font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          <Lightbulb className="h-4 w-4 text-amber-500" />
          Coaching Recommendations
        </h3>
        <div className="space-y-4">
          {report.coaching.map((action, i) => (
            <div
              key={i}
              className={`rounded-lg border p-4 ${
                action.priority === "high"
                  ? "border-amber-200 bg-amber-50 dark:border-amber-900/30 dark:bg-amber-900/10"
                  : action.priority === "medium"
                    ? "border-blue-200 bg-blue-50 dark:border-blue-900/30 dark:bg-blue-900/10"
                    : "border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-800/50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-medium uppercase rounded-full px-2 py-0.5 ${
                    action.priority === "high"
                      ? "text-amber-700 bg-amber-200 dark:text-amber-300 dark:bg-amber-900/40"
                      : action.priority === "medium"
                        ? "text-blue-700 bg-blue-200 dark:text-blue-300 dark:bg-blue-900/40"
                        : "text-zinc-600 bg-zinc-200"
                  }`}
                >
                  {action.priority}
                </span>
                <span className="text-xs text-zinc-400">{action.dimension}</span>
              </div>
              <h4 className="mt-1 font-medium text-zinc-900 dark:text-zinc-100">{action.title}</h4>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {action.description}
              </p>
              <p className="mt-2 flex items-start gap-1 text-sm text-teal-700 dark:text-teal-400">
                <TrendingUp className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                {action.practice_tip}
              </p>
            </div>
          ))}
        </div>
      </div>
      )}

      {/* Delivery Evidence */}
      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Delivery Evidence</h3>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {report.delivery_evidence.wpm}
            </p>
            <p className="text-xs text-zinc-500">WPM</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {report.delivery_evidence.hesitations}
            </p>
            <p className="text-xs text-zinc-500">Hesitations</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {report.delivery_evidence.word_count}
            </p>
            <p className="text-xs text-zinc-500">Words</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {report.delivery_evidence.duration_s}s
            </p>
            <p className="text-xs text-zinc-500">Duration</p>
          </div>
        </div>
        <p className="mt-4 text-xs text-zinc-400">
          Target: {report.delivery_evidence.target_word_count} words for reliable coaching.
          Confidence: {(report.confidence * 100).toFixed(0)}%
        </p>
      </div>
    </div>
  );
}
