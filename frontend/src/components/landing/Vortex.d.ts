import type { CSSProperties } from "react";

export interface VortexProps {
  background?: string;
  lineOptions?: { color?: string; glow?: number; count?: number };
  dotOptions?: { color?: string; glow?: number; count?: number; size?: number; flicker?: number };
  cometOptions?: {
    color?: string;
    glow?: number;
    count?: number;
    speed?: number;
    tail?: number;
    delay?: number;
    collide?: number;
  };
  repel?: boolean;
  repelOptions?: { radius?: number; strength?: number };
  style?: CSSProperties;
}

declare const Vortex: React.FC<VortexProps>;
export default Vortex;
