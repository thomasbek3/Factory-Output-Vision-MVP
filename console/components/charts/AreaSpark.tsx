"use client";

import { useId } from "react";
import { cn } from "@/lib/utils";

type AreaSparkTone = "good" | "bad";
type AreaSparkSize = "hero" | "kpi" | "cam";

const toneColor: Record<AreaSparkTone, string> = {
  good: "#46C26B",
  bad: "#FF5449",
};

const sizeMap: Record<AreaSparkSize, { width: number; height: number; className: string }> = {
  hero: { width: 420, height: 120, className: "h-[120px] w-full" },
  kpi: { width: 180, height: 48, className: "h-[48px] w-full" },
  cam: { width: 180, height: 40, className: "h-[40px] w-full" },
};

function toPoints(values: number[], width: number, height: number) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const topPad = Math.max(4, height * 0.08);
  const bottomPad = Math.max(4, height * 0.1);
  const usableHeight = height - topPad - bottomPad;

  return values.map((value, index) => ({
    x: values.length === 1 ? width : (index / (values.length - 1)) * width,
    y: topPad + (1 - (value - min) / range) * usableHeight,
  }));
}

function smoothPath(points: Array<{ x: number; y: number }>) {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  const commands = [`M ${points[0].x} ${points[0].y}`];

  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[Math.max(0, index - 1)];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[Math.min(points.length - 1, index + 2)];

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    commands.push(`C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`);
  }

  return commands.join(" ");
}

export function AreaSpark({
  values,
  color = "good",
  size = "kpi",
  endpoint = false,
  className,
  "aria-label": ariaLabel = "sparkline",
}: {
  values: number[];
  color?: AreaSparkTone;
  size?: AreaSparkSize;
  endpoint?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const id = useId().replace(/:/g, "");
  const preset = sizeMap[size];
  const safeValues = values.length ? values : [0];
  const points = toPoints(safeValues, preset.width, preset.height);
  const linePath = smoothPath(points);
  const baseline = preset.height;
  const areaPath = `${linePath} L ${preset.width} ${baseline} L 0 ${baseline} Z`;
  const stroke = toneColor[color];
  const endpointPoint = points.at(-1);

  return (
    <svg
      role="img"
      aria-label={ariaLabel}
      viewBox={`0 0 ${preset.width} ${preset.height}`}
      preserveAspectRatio="none"
      className={cn("block overflow-visible", preset.className, className)}
    >
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-12%" y="-60%" width="124%" height="220%">
          <feGaussianBlur stdDeviation="2" />
        </filter>
      </defs>
      <path d={areaPath} fill={`url(#${id}-fill)`} />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" opacity="0.4" filter={`url(#${id}-glow)`} />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" />
      {endpoint && endpointPoint ? (
        <>
          <circle cx={endpointPoint.x} cy={endpointPoint.y} r="5" fill={stroke} opacity="0.24" filter={`url(#${id}-glow)`} />
          <circle cx={endpointPoint.x} cy={endpointPoint.y} r="2.75" fill={stroke} />
        </>
      ) : null}
    </svg>
  );
}
