export type ThinkingOrbState =
  | "working"
  | "searching"
  | "solving"
  | "listening"
  | "connecting"
  | "weaving"
  | "composing"
  | "breathing"
  | "shaping";

export type ThinkingOrbSize = 20 | 64 | number;

export interface ThinkingOrbProps extends React.HTMLAttributes<HTMLDivElement> {
  state?: ThinkingOrbState;
  size?: ThinkingOrbSize;
  speed?: number;
  dark?: boolean;
  paused?: boolean;
  className?: string;
}
