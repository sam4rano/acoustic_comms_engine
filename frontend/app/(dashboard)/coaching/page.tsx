import type { Metadata } from "next";
import { GraduationCap } from "lucide-react";
import { EmptyState } from "@/components/layout/EmptyState";

export const metadata: Metadata = {
  title: "Coaching — Acoustic Comms",
};

export default function CoachingPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Coaching</h1>

      <EmptyState
        icon={<GraduationCap className="h-12 w-12" />}
        title="No coaching actions yet"
        description="Complete a session analysis to receive personalized coaching recommendations."
      />
    </div>
  );
}
