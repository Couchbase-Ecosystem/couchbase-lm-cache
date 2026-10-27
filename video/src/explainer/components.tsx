import React from "react";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { colors, mono, sans } from "./theme";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

/** 0 → 1 between two frames, eased and clamped. */
export const progress = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

export const SceneBackground: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <AbsoluteFill
    style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: sans }}
  >
    {children}
  </AbsoluteFill>
);

/** Scene heading in the top-left safe area. */
export const SceneTitle: React.FC<{ kicker: string; title: string }> = ({
  kicker,
  title,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: 140,
        top: 100,
        right: 140,
        opacity: progress(frame, 0, 18),
        translate: `0px ${(1 - progress(frame, 0, 18)) * 20}px`,
      }}
    >
      <div
        style={{
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: colors.red,
        }}
      >
        {kicker}
      </div>
      <div style={{ fontSize: 76, fontWeight: 800, letterSpacing: -1.5, marginTop: 8 }}>
        {title}
      </div>
    </div>
  );
};

/** Explanatory sentence near the bottom; fades in at `from` and out at `to`. */
export const Explain: React.FC<{
  from: number;
  to?: number;
  children: React.ReactNode;
}> = ({ from, to = 100000, children }) => {
  const frame = useCurrentFrame();
  const opacity = progress(frame, from, from + 15) * (1 - progress(frame, to, to + 12));
  return (
    <div
      style={{
        position: "absolute",
        left: 160,
        right: 160,
        bottom: 110,
        textAlign: "center",
        fontSize: 50,
        lineHeight: 1.3,
        fontWeight: 500,
        opacity,
      }}
    >
      {children}
    </div>
  );
};

export const Em: React.FC<{ color?: string; children: React.ReactNode }> = ({
  color = colors.red,
  children,
}) => <span style={{ color, fontWeight: 700 }}>{children}</span>;

export const Box: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  border?: string;
  background?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ x, y, w, h, border = colors.line, background = colors.panel, children, style }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      borderRadius: 24,
      border: `3px solid ${border}`,
      background,
      boxSizing: "border-box",
      ...style,
    }}
  >
    {children}
  </div>
);

/** A server: vLLM on a GPU, with an optional LMCache badge. */
export const Server: React.FC<{
  x: number;
  y: number;
  name: string;
  gpu: string;
  status: React.ReactNode;
  statusColor?: string;
  progressValue?: number;
  barColor?: string;
  lmcache?: boolean;
  highlight?: string;
}> = ({
  x,
  y,
  name,
  gpu,
  status,
  statusColor = colors.muted,
  progressValue = 0,
  barColor = colors.amber,
  lmcache = false,
  highlight,
}) => (
  <Box x={x} y={y} w={620} h={lmcache ? 360 : 270} border={highlight ?? colors.line}>
    <div style={{ padding: "26px 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 44, fontWeight: 800 }}>{name}</span>
        <span style={{ fontSize: 30, color: colors.muted }}>vLLM · {gpu}</span>
      </div>
      <div style={{ fontSize: 34, marginTop: 22, color: statusColor, minHeight: 44 }}>
        {status}
      </div>
      <div
        style={{
          marginTop: 18,
          height: 18,
          borderRadius: 9,
          background: "#232a3a",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.round(progressValue * 100)}%`,
            height: "100%",
            background: barColor,
            borderRadius: 9,
          }}
        />
      </div>
      {lmcache ? (
        <div
          style={{
            marginTop: 26,
            padding: "14px 20px",
            borderRadius: 14,
            background: "rgba(255,181,71,0.12)",
            color: colors.amber,
            fontSize: 28,
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          LMCache · KV cache off the GPU
        </div>
      ) : null}
    </div>
  </Box>
);

export const CouchbaseBucket: React.FC<{
  x: number;
  y: number;
  w?: number;
  documents?: React.ReactNode;
  children?: React.ReactNode;
}> = ({ x, y, w = 760, documents, children }) => (
  <Box x={x} y={y} w={w} h={170} border={colors.red} background="#1c1013">
    <div style={{ padding: "26px 34px", display: "flex", justifyContent: "space-between" }}>
      <div>
        <div style={{ fontSize: 46, fontWeight: 800 }}>Couchbase</div>
        <div style={{ fontSize: 30, color: colors.muted, marginTop: 6 }}>
          bucket “lmcache” · shared by all servers
        </div>
      </div>
      {documents !== undefined ? (
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 62, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
            {documents}
          </div>
          <div style={{ fontSize: 28, color: colors.muted }}>documents</div>
        </div>
      ) : null}
    </div>
    {children}
  </Box>
);

/** Straight arrow with an optional label; draws itself from `from` to `to`. */
export const Arrow: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  from: number;
  to: number;
  label?: string;
  labelOffset?: [number, number];
}> = ({ x1, y1, x2, y2, color, from, to, label, labelOffset = [0, 0] }) => {
  const frame = useCurrentFrame();
  const p = progress(frame, from, to);
  const ex = x1 + (x2 - x1) * p;
  const ey = y1 + (y2 - y1) * p;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width={1920} height={1080} style={{ position: "absolute" }}>
        <line x1={x1} y1={y1} x2={ex} y2={ey} stroke={color} strokeWidth={8} strokeLinecap="round" />
        {p > 0.05 ? (
          <polygon
            points="0,-16 30,0 0,16"
            fill={color}
            transform={`translate(${ex},${ey}) rotate(${(angle * 180) / Math.PI})`}
          />
        ) : null}
      </svg>
      {label ? (
        <div
          style={{
            position: "absolute",
            left: (x1 + x2) / 2 + labelOffset[0],
            top: (y1 + y2) / 2 + labelOffset[1],
            translate: "-50% -50%",
            fontSize: 32,
            fontWeight: 700,
            color,
            background: colors.bg,
            padding: "6px 14px",
            borderRadius: 10,
            opacity: progress(frame, to - 8, to + 6),
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/**
 * Highlights a rectangle of recorded footage: dims everything else and shows a
 * label next to it. Coordinates are in the 1920×1080 footage.
 */
export const Spotlight: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  from: number;
  to: number;
  color?: string;
  label: React.ReactNode;
  labelX: number;
  labelY: number;
  labelWidth?: number;
}> = ({ x, y, w, h, from, to, color = colors.red, label, labelX, labelY, labelWidth = 620 }) => {
  const frame = useCurrentFrame();
  const opacity = progress(frame, from, from + 10) * (1 - progress(frame, to, to + 10));
  if (opacity <= 0) return null;
  return (
    <AbsoluteFill style={{ opacity, pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: x - 10,
          top: y - 10,
          width: w + 20,
          height: h + 20,
          border: `5px solid ${color}`,
          borderRadius: 14,
          boxShadow: "0 0 0 4000px rgba(5,7,10,0.62)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: labelX,
          top: labelY,
          width: labelWidth,
          padding: "22px 28px",
          borderRadius: 18,
          background: colors.bg,
          border: `3px solid ${color}`,
          fontFamily: sans,
          fontSize: 40,
          lineHeight: 1.25,
          fontWeight: 600,
          color: colors.text,
          boxShadow: "0 18px 50px rgba(0,0,0,0.5)",
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};

export const Mono: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color,
}) => <span style={{ fontFamily: mono, color }}>{children}</span>;

export const Tag: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Interactive.Div
    name="Footage tag"
    style={{
      position: "absolute",
      right: 40,
      bottom: 30,
      padding: "10px 20px",
      borderRadius: 12,
      background: "rgba(11,13,18,0.85)",
      border: "2px solid #2a3142",
      color: "#eef1f7",
      fontFamily: sans,
      fontSize: 26,
      fontWeight: 600,
    }}
  >
    {children}
  </Interactive.Div>
);
