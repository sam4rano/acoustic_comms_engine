"use client";

import {
  RadarChart as RechartRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import type { DimensionScore } from "@/types";

interface RadarChartProps {
  dimensions: DimensionScore[];
}

export function RadarChart({ dimensions }: RadarChartProps) {
  const data = dimensions.map((d) => ({
    dimension: d.dimension.charAt(0).toUpperCase() + d.dimension.slice(1),
    score: d.score,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RechartRadar data={data}>
        <PolarGrid stroke="hsl(var(--zinc-200))" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fontSize: 11, fill: "hsl(var(--zinc-500))" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fontSize: 10, fill: "hsl(var(--zinc-400))" }}
        />
        <Radar
          dataKey="score"
          stroke="hsl(var(--teal-500))"
          fill="hsl(var(--teal-500))"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RechartRadar>
    </ResponsiveContainer>
  );
}
