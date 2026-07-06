"use client";

import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { TurnNode, GraphEdge } from "@/types";
import { cn } from "@/lib/utils";

interface ConversationGraphProps {
  turns: TurnNode[];
  edges: GraphEdge[];
  className?: string;
}

type TurnFlowNode = Node<{ speaker_label: string; text: string }, "turn">;

const nodeTypes = {
  turn: ({ data }: NodeProps<TurnFlowNode>) => (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <Handle type="target" position={Position.Top} />
      <div className="text-xs font-medium text-zinc-500">{data.speaker_label}</div>
      <div className="mt-1 max-w-[200px] truncate text-sm text-zinc-800 dark:text-zinc-200">
        {data.text}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  ),
} satisfies Record<string, React.ComponentType<NodeProps<TurnFlowNode>>>;

export function ConversationGraph({ turns, edges: graphEdges, className }: ConversationGraphProps) {
  const initialNodes: TurnFlowNode[] = turns.map((t, i) => ({
    id: t.id,
    type: "turn" as const,
    position: { x: i % 2 === 0 ? 0 : 300, y: Math.floor(i / 2) * 150 },
    data: { speaker_label: t.speaker_label, text: t.text },
  }));

  const initialEdges: Edge[] = graphEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: true,
    style: { strokeWidth: Math.max(1, e.weight * 3) },
  }));

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className={cn("h-[500px] rounded-xl border border-zinc-200 dark:border-zinc-800", className)}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
