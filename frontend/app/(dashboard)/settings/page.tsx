import type { Metadata } from "next";
import { Settings } from "lucide-react";

export const metadata: Metadata = {
  title: "Settings — Acoustic Comms",
};

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Settings</h1>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-3">
          <Settings className="h-5 w-5 text-zinc-400" />
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
            Preferences
          </h2>
        </div>
        <p className="mt-3 text-sm text-zinc-500">
          Application settings will be available here.
        </p>
      </div>
    </div>
  );
}
