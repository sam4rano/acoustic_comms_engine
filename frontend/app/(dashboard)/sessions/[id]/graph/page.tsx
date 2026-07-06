import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Conversation Graph — Acoustic Comms",
};

export default async function GraphPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Conversation Graph
          </h1>
          <p className="text-sm text-zinc-500 font-mono">{id}</p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-center h-[500px] text-sm text-zinc-500">
          Conversation graph visualization will render here.
        </div>
      </div>
    </div>
  );
}
