"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */
type LineOptions = {
  color?: string;
  glow?: number;
  count?: number;
};

type DotOptions = {
  color?: string;
  glow?: number;
  count?: number;
  size?: number;
  flicker?: number;
};

type CometOptions = {
  color?: string;
  glow?: number;
  count?: number;
  speed?: number;
  tail?: number;
  delay?: number;
  collide?: number;
};

type RepelOptions = {
  radius?: number;
  strength?: number;
};

type VortexProps = {
  background?: string;
  lineOptions?: LineOptions;
  dotOptions?: DotOptions;
  cometOptions?: CometOptions;
  repel?: boolean;
  repelOptions?: RepelOptions;
  style?: React.CSSProperties;
};

type SplinePoint = [number, number];
type SplineFn = (x: number) => number;

type VortexConfig = {
  background: string;
  lineOptions: LineOptions;
  dotOptions: DotOptions;
  cometOptions: CometOptions;
  repel: boolean;
  repelOptions: RepelOptions;
  running: boolean;
};

type VortexHandle = {
  rebuild: () => void;
  dispose: () => void;
};

type Disposable = { dispose: () => void };

type Strand = {
  lane: number;
  speed: number;
  pulse: number;
  wobblePhase: number;
  from: number;
  to: number;
  bright: number;
  offset: number;
  pts: Float32Array;
  cols: Float32Array;
};

type Dot = {
  s: number;
  lane: number;
  strand: number;
  pulse: number;
  flickerRate: number;
  bright: number;
};

type CometRipple = {
  active: boolean;
  x: number;
  y: number;
  z: number;
  at: number;
  amp: number;
};

type Comet = {
  bright: number;
  lane: number;
  speed: number;
  pulse: number;
  wobblePhase: number;
  base: number;
  boost: number;
  boostMul: number;
  racing: boolean;
  s: number;
  idle: number;
  idleFor: number;
  trail: Float32Array;
  trailCol: Float32Array;
  geo: THREE.BufferGeometry;
  line: THREE.Line;
  head: THREE.Sprite;
};

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */
const clamp = (v: number, min: number, max: number): number =>
  Math.min(Math.max(v, min), max);

function createSpline(points: SplinePoint[]): SplineFn {
  const n = points.length;
  const slopes: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    slopes[i] =
      (points[i + 1][1] - points[i][1]) / (points[i + 1][0] - points[i][0]);
  }
  const m: number[] = [slopes[0]];
  for (let i = 1; i < n - 1; i++) {
    m[i] = slopes[i - 1] * slopes[i] <= 0 ? 0 : (slopes[i - 1] + slopes[i]) / 2;
  }
  m[n - 1] = slopes[n - 2];
  for (let i = 0; i < n - 1; i++) {
    if (Math.abs(slopes[i]) < 1e-12) {
      m[i] = m[i + 1] = 0;
      continue;
    }
    const a = m[i] / slopes[i];
    const b = m[i + 1] / slopes[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * slopes[i];
      m[i + 1] = t * b * slopes[i];
    }
  }
  return (x: number): number => {
    if (x <= points[0][0]) return points[0][1];
    if (x >= points[n - 1][0]) return points[n - 1][1];
    let k = 0;
    while (k < n - 2 && points[k + 1][0] < x) k++;
    const dx = points[k + 1][0] - points[k][0];
    const t = (x - points[k][0]) / dx;
    const t2 = t * t;
    const t3 = t2 * t;
    return (
      (2 * t3 - 3 * t2 + 1) * points[k][1] +
      (t3 - 2 * t2 + t) * dx * m[k] +
      (-2 * t3 + 3 * t2) * points[k + 1][1] +
      (t3 - t2) * dx * m[k + 1]
    );
  };
}

function bakeLookup(fn: SplineFn, size = 1024): Float32Array {
  const arr = new Float32Array(size);
  for (let i = 0; i < size; i++) arr[i] = fn(i / (size - 1));
  return arr;
}

function sampleLookup(arr: Float32Array, t: number): number {
  if (t <= 0) return arr[0];
  if (t >= 1) return arr[arr.length - 1];
  const f = t * (arr.length - 1);
  const i = Math.floor(f);
  return arr[i] + (arr[i + 1] - arr[i]) * (f - i);
}

function smoothstep(x: number, min: number, max: number): number {
  if (x <= min) return 0;
  if (x >= max) return 1;
  const t = (x - min) / (max - min);
  return 1 - (1 - t) ** 3;
}

/* ------------------------------------------------------------------ */
/* React component                                                     */
/* ------------------------------------------------------------------ */
export default function Vortex({
  background = "#000000",
  lineOptions = { color: "#ffffff", glow: 10, count: 240 },
  dotOptions = { color: "#ffffff", glow: 10, count: 8000, size: 20, flicker: 10 },
  cometOptions = {
    color: "#eca8d6",
    glow: 6,
    count: 10,
    speed: 6,
    tail: 19,
    delay: 8,
    collide: 6,
  },
  repel = true,
  repelOptions = { radius: 60, strength: 10 },
  style,
}: VortexProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const vortexRef = useRef<VortexHandle | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  const optionsRef = useRef<VortexConfig>({
    background,
    lineOptions,
    dotOptions,
    cometOptions,
    repel,
    repelOptions,
    running: true,
  });
  optionsRef.current = {
    background,
    lineOptions,
    dotOptions,
    cometOptions,
    repel,
    repelOptions,
    running: !reducedMotion,
  };
  const configKey = JSON.stringify({
    background,
    lineOptions,
    dotOptions,
    cometOptions,
    repel,
    repelOptions,
  });

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const opts = optionsRef.current;

    try {
      vortexRef.current = initVortex(canvas, container, {
        background: opts.background,
        lineOptions: opts.lineOptions,
        dotOptions: opts.dotOptions,
        cometOptions: opts.cometOptions,
        repel: opts.repel,
        repelOptions: opts.repelOptions,
        running: !reducedMotion,
      });
    } catch (e) {
      console.warn("[Vortex] init failed:", e);
      return;
    }

    return () => {
      try {
        vortexRef.current?.dispose();
      } catch (e) {
        console.warn("[Vortex] dispose failed:", e);
      }
      vortexRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configKey, reducedMotion]);

  return (
    <div
      ref={containerRef}
      style={{
        ...style,
        position: "relative",
        width: "100%",
        height: "100%",
        background,
        overflow: "hidden",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Core                                                                */
/* ------------------------------------------------------------------ */
function initVortex(
  canvas: HTMLCanvasElement,
  container: HTMLElement,
  config: VortexConfig
): VortexHandle {
  const lineOpts = config.lineOptions ?? {};
  const dotOpts = config.dotOptions ?? {};
  const cometOpts = config.cometOptions ?? {};
  const repelOpts = config.repelOptions ?? {};

  const probe = canvas.getContext("webgl2") || canvas.getContext("webgl");
  if (!probe) {
    throw new Error("WebGL is not available in this browser/context.");
  }

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });
  renderer.setClearColor(0, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.toneMapping = THREE.ReinhardToneMapping;
  renderer.toneMappingExposure = 1.25;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(134 - 75, 1, 0.1, 500);
  const root = new THREE.Group();
  scene.add(root);

  const uniforms: {
    uMouse: { value: THREE.Vector2 };
    uAspect: { value: number };
    uRadius: { value: number };
    uStrength: { value: number };
  } = {
    uMouse: { value: new THREE.Vector2(0, 0) },
    uAspect: { value: 1 },
    uRadius: { value: 0.2 },
    uStrength: { value: 0 },
  };

  const applyRepelShader = <T extends THREE.Material>(
    material: T,
    { instanced = false }: { instanced?: boolean } = {}
  ): T => {
    material.onBeforeCompile = (shader: THREE.WebGLProgramParametersWithUniforms) => {
      shader.uniforms.uMouse = uniforms.uMouse;
      shader.uniforms.uAspect = uniforms.uAspect;
      shader.uniforms.uRadius = uniforms.uRadius;
      shader.uniforms.uStrength = uniforms.uStrength;

      const repelUniforms = `
      uniform vec2 uMouse;
      uniform float uAspect;
      uniform float uRadius;
      uniform float uStrength;
    `;

      const repelBody = instanced
        ? `
        if (uStrength > 0.0 && uRadius > 0.0 && gl_Position.w > 0.0) {
          vec4 repelCenterClip = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
          if (repelCenterClip.w > 0.0) {
            vec2 centerNdc = repelCenterClip.xy / repelCenterClip.w;
            vec2 off = centerNdc - uMouse;
            float dist = length(off * vec2(uAspect, 1.0));
            float f = uStrength * exp(-(dist * dist) / (2.0 * uRadius * uRadius));
            float m = length(off);
            if (m > 1e-4) {
              vec2 push = (off / m) * f;
              vec2 ndc = gl_Position.xy / gl_Position.w;
              ndc += push;
              gl_Position.xy = ndc * gl_Position.w;
            }
          }
        }
      `
        : `
        if (uStrength > 0.0 && uRadius > 0.0 && gl_Position.w > 0.0) {
          vec2 ndc = gl_Position.xy / gl_Position.w;
          vec2 off = ndc - uMouse;
          float dist = length(off * vec2(uAspect, 1.0));
          float f = uStrength * exp(-(dist * dist) / (2.0 * uRadius * uRadius));
          float m = length(off);
          if (m > 1e-4) {
            ndc += (off / m) * f;
            gl_Position.xy = ndc * gl_Position.w;
          }
        }
      `;

      shader.vertexShader = shader.vertexShader
        .replace("void main() {", `${repelUniforms}\nvoid main() {`)
        .replace("#include <fog_vertex>", `#include <fog_vertex>\n${repelBody}`);
    };
    return material;
  };

  const disposables: Disposable[] = [];
  const track = <T extends Disposable>(obj: T): T => {
    disposables.push(obj);
    return obj;
  };

  const A: {
    floorRadius: number;
    waistRadius: number;
    crownRadius: number;
    waistAt: number;
    twist: number;
    zoom: number;
    flowDir: number;
    flowSpeed: number;
    lineCount: number;
    lineColor: string;
    lineGlow: number;
    showDots: boolean;
    dotCount: number;
    dotSize: number;
    dotColor: string;
    dotGlow: number;
    dotFlicker: number;
    showComets: boolean;
    cometCount: number;
    cometSpeed: number;
    cometColor: string;
    cometGlow: number;
    cometTail: number;
    cometDelay: number;
    collideForce: number;
    hoverRepel: boolean;
    repelRadius: number;
    repelStrength: number;
    running: boolean;
  } = {
    floorRadius: 1150 / 60,
    waistRadius: 53 / 60,
    crownRadius: 380 / 60,
    waistAt: 1 - 50 / 100,
    twist: 3,
    zoom: 75,
    flowDir: 1,
    flowSpeed: 10 / 100,

    lineCount: lineOpts.count ?? 240,
    lineColor: lineOpts.color ?? "#ffffff",
    lineGlow: (lineOpts.glow ?? 10) / 10,

    showDots: true,
    dotCount: dotOpts.count ?? 8000,
    dotSize: (dotOpts.size ?? 20) / 1000,
    dotColor: dotOpts.color ?? "#ffffff",
    dotGlow: ((dotOpts.glow ?? 10) / 10) * 4.2,
    dotFlicker: (dotOpts.flicker ?? 10) / 10,

    showComets: true,
    cometCount: cometOpts.count ?? 10,
    cometSpeed: ((cometOpts.speed ?? 6) / 10) * 0.15,
    cometColor: cometOpts.color ?? "#eca8d6",
    cometGlow: (cometOpts.glow ?? 6) / 10,
    cometTail: cometOpts.tail ?? 19,
    cometDelay: cometOpts.delay ?? 8,
    collideForce: (cometOpts.collide ?? 6) / 10,

    hoverRepel: config.repel ?? true,
    repelRadius: repelOpts.radius ?? 60,
    repelStrength: repelOpts.strength ?? 10,

    running: config.running !== false,
  };

  let strands: Strand[] = [];
  let strandPositions = new Float32Array(0);
  let strandColors = new Float32Array(0);
  let strandMesh: THREE.LineSegments | null = null;

  let dots: Dot[] = [];
  let dotMesh: THREE.InstancedMesh | null = null;
  let dotPositions = new Float32Array(0);
  let dotColors = new Float32Array(0);
  let dotScales = new Float32Array(0);
  let dotVelocities = new Float32Array(0);
  let dotImpulses = new Float32Array(0);
  let dotDisplacements = new Float32Array(0);

  let cometRipples: CometRipple[] = Array.from({ length: 16 }, () => ({
    active: false,
    x: 0,
    y: 0,
    z: 0,
    at: 0,
    amp: 1,
  }));
  let rippleActive = false;
  let comets: Comet[] = [];

  let splineRadius: Float32Array = new Float32Array(0);
  let splineHeight: Float32Array = new Float32Array(0);
  let splineTwist: Float32Array = new Float32Array(0);

  let rafId = 0;
  let firstFrameTime = 0;
  let viewportHeight = 1;

  const colors = {
    strand: new THREE.Color(),
    dot: new THREE.Color(),
    comet: new THREE.Color(),
  };
  const cache = { line: "", dot: "", comet: "" };

  const geomHelper = {
    writePoint(
      arr: Float32Array,
      idx: number,
      t: number,
      lane: number,
      flow: number,
      wobbleAmp: number,
      wobblePhase: number,
      time: number
    ): void {
      const r = sampleLookup(splineRadius, t);
      const h = sampleLookup(splineHeight, t);
      const tw = sampleLookup(splineTwist, t) + lane + flow;
      const radius =
        r + Math.sin(25 * t + wobblePhase + 0.3 * time) * wobbleAmp * r;
      arr[idx] = Math.cos(tw) * radius;
      arr[idx + 1] = h;
      arr[idx + 2] = Math.sin(tw) * radius;
    },
    lane: (i: number, total: number): number => (i / total) * Math.PI * 2,
  };

  function updateColors(cfg: typeof A): void {
    if (cfg.lineColor !== cache.line) {
      colors.strand.set(cfg.lineColor);
      cache.line = cfg.lineColor;
    }
    if (cfg.dotColor !== cache.dot) {
      colors.dot.set(cfg.dotColor);
      cache.dot = cfg.dotColor;
    }
    if (cfg.cometColor !== cache.comet) {
      colors.comet.set(cfg.cometColor);
      cache.comet = cfg.cometColor;
      for (const c of comets) {
        (c.head.material as THREE.SpriteMaterial).color.setRGB(
          1.2 * colors.comet.r,
          1.2 * colors.comet.g,
          1.2 * colors.comet.b
        );
      }
    }
  }

  function rebuild(): void {
    for (let i = root.children.length - 1; i >= 0; i--) {
      root.remove(root.children[i]);
    }
    for (const d of disposables) d.dispose();
    disposables.length = 0;

    const cfg = A;
    const waistAt = clamp(cfg.waistAt, 0.08, 0.92);
    const floorR = cfg.floorRadius;
    const crownR = cfg.crownRadius;
    const twistAngle = cfg.twist * Math.PI * 2;

    splineRadius = bakeLookup(
      createSpline([
        [0, floorR],
        [0.24 * waistAt, 0.667 * floorR],
        [0.5 * waistAt, 0.3 * floorR],
        [0.76 * waistAt, 0.08 * floorR],
        [waistAt, cfg.waistRadius],
        [waistAt + 0.3 * (1 - waistAt), 0.2 * crownR],
        [waistAt + 0.6 * (1 - waistAt), 0.44 * crownR],
        [1, crownR],
      ])
    );
    splineHeight = bakeLookup(
      createSpline([
        [0, 0],
        [0.1, 0.2],
        [0.2, 0.8],
        [0.35, 2],
        [0.5, 3.8],
        [0.75, 7],
        [1, 10],
      ])
    );
    splineTwist = bakeLookup(
      createSpline([
        [0, 0],
        [0.15, 0.15 * twistAngle],
        [0.25, 0.25 * twistAngle],
        [0.45, 0.55 * twistAngle],
        [0.6, 0.7 * twistAngle],
        [0.8, 0.88 * twistAngle],
        [1, twistAngle],
      ])
    );

    camera.fov = 134 - cfg.zoom;
    camera.updateProjectionMatrix();
    updateColors(cfg);

    /* Strands */
    const count = Math.max(3, Math.round(cfg.lineCount));
    const totalPoints = 399 * count * 2;
    strandPositions = new Float32Array(3 * totalPoints);
    strandColors = new Float32Array(3 * totalPoints);

    const strandGeom = track(new THREE.BufferGeometry());
    strandGeom.setAttribute(
      "position",
      new THREE.BufferAttribute(strandPositions, 3).setUsage(
        THREE.DynamicDrawUsage
      )
    );
    strandGeom.setAttribute(
      "color",
      new THREE.BufferAttribute(strandColors, 3).setUsage(
        THREE.DynamicDrawUsage
      )
    );

    const strandMat = track(
      applyRepelShader(
        new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: 0.5,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
      )
    );

    strandMesh = new THREE.LineSegments(strandGeom, strandMat);
    strandMesh.frustumCulled = false;
    root.add(strandMesh);

    strands = [];
    for (let i = 0; i < count; i++) {
      strands.push({
        lane: geomHelper.lane(i, count),
        speed: 0.95 + 0.1 * Math.random(),
        pulse: Math.random() * Math.PI * 2,
        wobblePhase: Math.random() * Math.PI * 2,
        from: 0,
        to: 1,
        bright: 0.5,
        offset: 399 * i * 6,
        pts: new Float32Array(1200),
        cols: new Float32Array(1200),
      });
    }

    /* Dots */
    const dotCount = cfg.showDots ? Math.max(0, Math.round(cfg.dotCount)) : 0;
    dots = [];
    for (let i = 0; i < dotCount; i++) {
      const s =
        Math.random() < 0.5
          ? 0.2 + 0.4 * Math.random()
          : 0.05 + 0.9 * Math.random();
      const strandIdx = Math.floor(Math.random() * strands.length);
      dots.push({
        s,
        lane: strands[strandIdx].lane,
        strand: strandIdx,
        pulse: Math.random() * Math.PI * 2,
        flickerRate: 0.15 + 4.5 * Math.random(),
        bright: 0.04 + Math.pow(Math.random(), 1.5) * 0.96,
      });
    }

    dotPositions = new Float32Array(3 * dotCount);
    dotColors = new Float32Array(3 * dotCount);
    dotScales = new Float32Array(dotCount).fill(1);
    dotVelocities = new Float32Array(3 * dotCount);
    dotImpulses = new Float32Array(dotCount);
    dotDisplacements = new Float32Array(3 * dotCount);

    if (dotCount > 0) {
      const dotGeom = track(new THREE.PlaneGeometry(1, 1));
      const dotMat = track(
        applyRepelShader(
          new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.9,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          }),
          { instanced: true }
        )
      );

      dotMesh = new THREE.InstancedMesh(dotGeom, dotMat, dotCount);
      dotMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      const instColor = new THREE.InstancedBufferAttribute(dotColors, 3);
      instColor.setUsage(THREE.DynamicDrawUsage);
      dotMesh.instanceColor = instColor;
      dotMesh.frustumCulled = false;
      root.add(dotMesh);
    } else {
      dotMesh = null;
    }

    /* Comets */
    cometRipples = cometRipples.map(() => ({
      active: false,
      x: 0,
      y: 0,
      z: 0,
      at: 0,
      amp: 1,
    }));

    const cometTexture = track(
      (() => {
        const c = document.createElement("canvas");
        c.width = c.height = 32;
        const ctx = c.getContext("2d");
        if (ctx) {
          const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
          grad.addColorStop(0, "rgba(255,255,255,0.9)");
          grad.addColorStop(0.3, "rgba(255,120,255,0.4)");
          grad.addColorStop(0.7, "rgba(200,50,200,0.08)");
          grad.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = grad;
          ctx.fillRect(0, 0, 32, 32);
        }
        const tex = new THREE.CanvasTexture(c);
        tex.needsUpdate = true;
        return tex;
      })()
    );

    const cometCount = cfg.showComets
      ? Math.max(0, Math.round(cfg.cometCount))
      : 0;
    const tailLen = Math.max(2, Math.round(cfg.cometTail));
    comets = [];

    for (let i = 0; i < cometCount; i++) {
      const trailPos = new Float32Array(3 * tailLen);
      const trailCol = new Float32Array(3 * tailLen);

      const geom = track(new THREE.BufferGeometry());
      geom.setAttribute(
        "position",
        new THREE.BufferAttribute(trailPos, 3).setUsage(THREE.DynamicDrawUsage)
      );
      geom.setAttribute(
        "color",
        new THREE.BufferAttribute(trailCol, 3).setUsage(THREE.DynamicDrawUsage)
      );

      const mat = track(
        applyRepelShader(
          new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.9,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          })
        )
      );

      const line = new THREE.Line(geom, mat);
      line.frustumCulled = false;

      const spriteMat = track(
        new THREE.SpriteMaterial({
          map: cometTexture,
          transparent: true,
          opacity: 0,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          color: new THREE.Color(
            1.2 * colors.comet.r,
            1.2 * colors.comet.g,
            1.2 * colors.comet.b
          ),
        })
      );

      const head = new THREE.Sprite(spriteMat);
      head.scale.set(0.35, 0.35, 1);

      root.add(line);
      root.add(head);

      const strand = strands[Math.floor(Math.random() * strands.length)];
      const speed = cfg.cometSpeed * (0.7 + 0.6 * Math.random());

      comets.push({
        bright: 0.7 + 0.3 * Math.random(),
        lane: strand.lane,
        speed,
        pulse: strand.speed,
        wobblePhase: strand.wobblePhase,
        base: speed,
        boost: 0,
        boostMul: 1,
        racing: false,
        s: 0,
        idle: 0,
        idleFor: 0.4 + (i / Math.max(1, cometCount)) * cfg.cometDelay,
        trail: trailPos,
        trailCol,
        geo: geom,
        line,
        head,
      });
    }
  }

  /* Resize / pointer */
  function resize(): void {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    viewportHeight = h;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    uniforms.uAspect.value = w / h;
    uniforms.uRadius.value = clamp(A.repelRadius / (h / 2), 0.01, 3);
    if (!A.running) renderer.render(scene, camera);
  }

  const ro = new ResizeObserver(resize);
  let pointerStrength = 0;

  const onPointerMove = (e: PointerEvent): void => {
    const rect = container.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    uniforms.uMouse.value.set(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -(((e.clientY - rect.top) / rect.height) * 2 - 1)
    );
    pointerStrength =
      A.hoverRepel && A.running
        ? 0.45 * clamp(A.repelStrength / 100, 0, 1)
        : 0;
  };
  const onPointerLeave = (): void => {
    pointerStrength = 0;
  };

  container.addEventListener("pointermove", onPointerMove);
  container.addEventListener("pointerleave", onPointerLeave);
  container.addEventListener("pointercancel", onPointerLeave);

  /* Physics helpers */
  function applyRipple(
    x: number,
    y: number,
    z: number,
    time: number,
    target: Float32Array,
    offset: number
  ): void {
    let dx = 0,
      dy = 0,
      dz = 0,
      any = false;

    for (let i = 0; i < 16; i++) {
      const r = cometRipples[i];
      if (!r.active) continue;

      const dt = (time - r.at) / 1000;
      if (dt > 2.5) {
        r.active = false;
        continue;
      }
      any = true;

      const vx = x - r.x,
        vy = y - r.y,
        vz = z - r.z;
      const dist = Math.sqrt(vx * vx + vy * vy + vz * vz);
      if (dist < 0.001 || dist > 3) continue;

      const wavefront = Math.abs(dist - 5 * dt);
      if (wavefront > 1.2) continue;

      const g = Math.cos((wavefront / 1.2) * Math.PI * 0.5);
      const decay = Math.exp(-dt / 0.8);
      const invDist = 1 / Math.max(dist, 0.3);
      const amp = 0.5 * r.amp * 0.04 * g * decay * invDist;

      dx += (vx / dist) * amp;
      dy += (vy / dist) * amp;
      dz += (vz / dist) * amp;
    }

    if (!any) rippleActive = false;

    target[offset] += dx;
    target[offset + 1] += dy;
    target[offset + 2] += dz;
  }

  function updateDotPhysics(dt: number): void {
    let anyActive = false;

    for (let i = 0; i < dots.length; i++) {
      const idx = 3 * i;

      for (let j = 0; j < 3; j++) {
        const force =
          -50 * dotDisplacements[idx + j] - 9 * dotVelocities[idx + j];
        dotVelocities[idx + j] += force * dt;
        dotDisplacements[idx + j] += dotVelocities[idx + j] * dt;
      }

      const dSq =
        dotDisplacements[idx] ** 2 +
        dotDisplacements[idx + 1] ** 2 +
        dotDisplacements[idx + 2] ** 2;
      const vSq =
        dotVelocities[idx] ** 2 +
        dotVelocities[idx + 1] ** 2 +
        dotVelocities[idx + 2] ** 2;

      if (dSq < 1e-8 && vSq < 1e-8) {
        dotDisplacements[idx] =
          dotDisplacements[idx + 1] =
          dotDisplacements[idx + 2] =
          0;
        dotVelocities[idx] =
          dotVelocities[idx + 1] =
          dotVelocities[idx + 2] =
          0;
      } else {
        anyActive = true;
      }

      const impulseForce = -65 * (dotScales[i] - 1) - 11 * dotImpulses[i];
      dotImpulses[i] += impulseForce * dt;
      dotScales[i] += dotImpulses[i] * dt;

      if (
        Math.abs(dotScales[i] - 1) < 0.001 &&
        Math.abs(dotImpulses[i]) < 0.001
      ) {
        dotScales[i] = 1;
        dotImpulses[i] = 0;
      } else {
        anyActive = true;
      }
    }

    if (!anyActive) rippleActive = false;
  }

  function spawnRipple(dotIdx: number, time: number, amp: number): void {
    const x = dotPositions[3 * dotIdx];
    const y = dotPositions[3 * dotIdx + 1];
    const z = dotPositions[3 * dotIdx + 2];

    rippleActive = true;

    let slot = 0;
    let oldest = Infinity;
    for (let i = 0; i < 16; i++) {
      if (!cometRipples[i].active) {
        slot = i;
        break;
      }
      if (cometRipples[i].at < oldest) {
        oldest = cometRipples[i].at;
        slot = i;
      }
    }
    cometRipples[slot] = { active: true, x, y, z, at: time, amp };

    for (let i = 0; i < dots.length; i++) {
      const dx = dotPositions[3 * i] - x;
      const dy = dotPositions[3 * i + 1] - y;
      const dz = dotPositions[3 * i + 2] - z;
      const dSq = dx * dx + dy * dy + dz * dz;
      if (dSq > 4 || dSq < 1e-4) continue;

      const d = Math.sqrt(dSq);
      const falloff = 1 - d / 2;
      const push = (0.5 * amp * falloff * falloff) / Math.max(d, 0.1);

      dotVelocities[3 * i] += dx * push;
      dotVelocities[3 * i + 1] += dy * push;
      dotVelocities[3 * i + 2] += dz * push;

      const scaleUp = 1 + 0.8 * amp * falloff * falloff;
      if (scaleUp > dotScales[i]) dotScales[i] = scaleUp;
    }
  }

  function checkCometCollisions(dt: number, time: number): void {
    const force = A.collideForce;
    if (force <= 0) return;

    const radiusSq = 0.8 * 0.8;

    for (const c of comets) {
      if (!c.racing) continue;

      const cx = c.trail[0],
        cy = c.trail[1],
        cz = c.trail[2];
      if (cx === 0 && cy === 0 && cz === 0) continue;

      for (let i = 0; i < dots.length; i++) {
        const dx = dotPositions[3 * i] - cx;
        const dy = dotPositions[3 * i + 1] - cy;
        const dz = dotPositions[3 * i + 2] - cz;

        if (dx * dx + dy * dy + dz * dz < radiusSq && dotImpulses[i] === 0) {
          dotImpulses[i] = 0.001;
          dotVelocities[3 * i] = 6 * force;
          dotScales[i] = 1 + 0.3 * force;

          spawnRipple(i, time, force);

          c.boost = 0.4;
          c.boostMul = 1 + 0.6 * force;
          c.speed = c.base * c.boostMul;
        }
      }
    }
  }

  /* Animation */
  let accum = 0;
  let frameIndex = 0;
  let hasStarted = false;
  let prevTime = performance.now();
  const tmpMat = new THREE.Matrix4();

  function animate(time: number): void {
    rafId = requestAnimationFrame(animate);

    const cfg = A;
    const dt = Math.min((time - prevTime) / 1000, 0.04);
    prevTime = time;

    if (!cfg.running) {
      if (!hasStarted) {
        renderer.render(scene, camera);
        hasStarted = true;
      }
      return;
    }
    hasStarted = false;

    if (firstFrameTime === 0) firstFrameTime = time;
    const tSince = (time - firstFrameTime) / 1000;
    const fadeIn = smoothstep(tSince, 0, 2);
    const dotFade = smoothstep(tSince, 1.2, 3);
    const cometFade = smoothstep(tSince, 3, 5);

    updateColors(cfg);

    const fovTarget = 134 - cfg.zoom;
    if (camera.fov !== fovTarget) {
      camera.fov = fovTarget;
      camera.updateProjectionMatrix();
    }
    uniforms.uRadius.value = clamp(
      cfg.repelRadius / (viewportHeight / 2),
      0.01,
      3
    );

    accum += dt * cfg.flowSpeed;

    const uStr = uniforms.uStrength;
    uStr.value += (pointerStrength - uStr.value) * Math.min(1, 12 * dt);

    /* Strands */
    if (strandMesh) {
      for (const s of strands) {
        const flowPos = accum * s.speed;
        const glow = s.bright * cfg.lineGlow;
        const pulse = 0.15 + 1.5 * glow;
        const head =
          Math.min(
            0.5 * glow * (0.9 + 0.1 * Math.sin(0.18 * time + s.pulse)),
            0.7
          ) * Math.min(3 * fadeIn, 1);

        const headPos = s.from + fadeIn * (s.to - s.from);
        const edgeFade = 0.15 * (s.to - s.from);

        const { pts, cols } = s;

        for (let i = 0; i < 400; i++) {
          const t = i / 399;
          const param = s.from + t * (s.to - s.from);
          const idx = 3 * i;

          geomHelper.writePoint(
            pts,
            idx,
            param,
            s.lane,
            flowPos,
            0.008,
            s.wobblePhase,
            time
          );

          if (rippleActive) {
            applyRipple(pts[idx], pts[idx + 1], pts[idx + 2], time, pts, idx);
          }

          let edgeFadeFactor = 1;
          if (t < 0.15) {
            const e = t / 0.15;
            edgeFadeFactor = e * e;
          } else if (t > 0.85) {
            const e = (1 - t) / 0.15;
            edgeFadeFactor = e * e;
          }

          let headFactor = 1;
          if (param > headPos) headFactor = 0;
          else if (param > headPos - edgeFade) {
            headFactor = (headPos - param) / edgeFade;
            headFactor *= headFactor;
          }

          const bright = edgeFadeFactor * pulse * headFactor * head;
          cols[idx] = colors.strand.r * bright;
          cols[idx + 1] = colors.strand.g * bright;
          cols[idx + 2] = colors.strand.b * bright;
        }

        let off = s.offset;
        for (let i = 0; i < 399; i++) {
          const a = 3 * i;
          const b = (i + 1) * 3;

          strandPositions[off] = pts[a];
          strandPositions[off + 1] = pts[a + 1];
          strandPositions[off + 2] = pts[a + 2];
          strandColors[off] = cols[a];
          strandColors[off + 1] = cols[a + 1];
          strandColors[off + 2] = cols[a + 2];

          strandPositions[off + 3] = pts[b];
          strandPositions[off + 4] = pts[b + 1];
          strandPositions[off + 5] = pts[b + 2];
          strandColors[off + 3] = cols[b];
          strandColors[off + 4] = cols[b + 1];
          strandColors[off + 5] = cols[b + 2];

          off += 6;
        }
      }

      strandMesh.geometry.attributes.position.needsUpdate = true;
      strandMesh.geometry.attributes.color.needsUpdate = true;
    }

    /* Dot physics */
    if (rippleActive) updateDotPhysics(dt);

    /* Dots */
    if (dotMesh && dots.length > 0) {
      const size = cfg.dotSize;

      for (let i = 0; i < dots.length; i++) {
        const dot = dots[i];
        const s = strands[dot.strand] ?? strands[0];
        const flow = accum * s.speed;
        const idx = 3 * i;

        geomHelper.writePoint(
          dotPositions,
          idx,
          dot.s,
          dot.lane,
          flow,
          0.008,
          s.wobblePhase,
          time
        );

        const scale = dotScales[i] * size * cfg.dotGlow * dotFade;
        tmpMat.makeScale(scale, scale, scale);
        tmpMat.setPosition(
          dotPositions[idx] + dotDisplacements[idx],
          dotPositions[idx + 1] + dotDisplacements[idx + 1],
          dotPositions[idx + 2] + dotDisplacements[idx + 2]
        );
        dotMesh.setMatrixAt(i, tmpMat);

        const flicker =
          1 -
          cfg.dotFlicker +
          cfg.dotFlicker *
            (0.08 +
              0.92 *
                Math.max(
                  0,
                  Math.sin(0.001 * time * dot.flickerRate + dot.pulse)
                ) **
                  2.5);

        const impulse = 1 + dotImpulses[i] * 0.5;
        const bright = dot.bright * flicker * cfg.dotGlow * impulse * dotFade;

        dotColors[idx] = colors.dot.r * bright;
        dotColors[idx + 1] = colors.dot.g * bright;
        dotColors[idx + 2] = colors.dot.b * bright;
      }

      dotMesh.instanceMatrix.needsUpdate = true;
      if (dotMesh.instanceColor) dotMesh.instanceColor.needsUpdate = true;
      (dotMesh.material as THREE.MeshBasicMaterial).opacity = 0.9 * dotFade;
    }

    /* Comets */
    for (const c of comets) {
      const tailCount = c.trail.length / 3;

      if (!c.racing) {
        (c.head.material as THREE.SpriteMaterial).opacity = 0;
        if (cometFade < 0.3) continue;

        c.idle += dt;
        if (c.idle > c.idleFor) {
          c.racing = true;
          c.s = cfg.flowDir < 0 ? 0.95 : 0.03;
          c.base = cfg.cometSpeed * (0.7 + 0.6 * Math.random());
          c.speed = c.base;
          c.boost = 0;
          c.boostMul = 1;

          const s = strands[Math.floor(Math.random() * strands.length)];
          c.lane = s.lane;
          c.pulse = s.speed;
          c.wobblePhase = s.wobblePhase;
        }
        continue;
      }

      if (c.boost > 0) {
        c.boost -= dt;
        if (c.boost <= 0) {
          c.boost = 0;
          c.boostMul = 1;
        } else {
          c.boostMul = 1 + 0.6 * (c.boost / 0.4);
        }
        c.speed = c.base * c.boostMul;
      }

      c.s += dt * c.speed * cfg.flowDir;

      if (
        (cfg.flowDir < 0 && c.s < 0.03) ||
        (cfg.flowDir > 0 && c.s > 0.95)
      ) {
        c.racing = false;
        c.idle = 0;
        c.idleFor = cfg.cometDelay * (0.6 + 0.8 * Math.random());
        c.trailCol.fill(0);
        c.geo.attributes.color.needsUpdate = true;
        (c.head.material as THREE.SpriteMaterial).opacity = 0;
        continue;
      }

      const flow = accum * c.pulse;
      const fade =
        clamp((c.s - 0.03) / 0.1, 0, 1) * clamp((0.95 - c.s) / 0.1, 0, 1);

      for (let i = 0; i < tailCount; i++) {
        const t = clamp(c.s - 0.005 * i * cfg.flowDir, 0.005, 0.995);
        const idx = 3 * i;

        geomHelper.writePoint(
          c.trail,
          idx,
          t,
          c.lane,
          flow,
          0.008,
          c.wobblePhase,
          time
        );

        const falloff = (1 - i / tailCount) ** 2;
        const bright = c.bright * cfg.cometGlow * falloff * fade * cometFade;
        const scale = i < 3 ? 1.3 : 1;

        c.trailCol[idx] = colors.comet.r * bright * scale;
        c.trailCol[idx + 1] = colors.comet.g * bright * scale;
        c.trailCol[idx + 2] = colors.comet.b * bright * scale;
      }

      c.head.position.set(c.trail[0], c.trail[1], c.trail[2]);

      const boostScale = c.boost > 0 ? 1 + (c.boostMul - 1) * 0.8 : 1;
      (c.head.material as THREE.SpriteMaterial).opacity =
        0.35 * fade * cometFade * boostScale;
      c.head.scale.set(0.35 * boostScale, 0.35 * boostScale, 1);

      c.geo.attributes.position.needsUpdate = true;
      c.geo.attributes.color.needsUpdate = true;
    }

    /* Comet ↔ dot collisions */
    frameIndex++;
    if (frameIndex % 2 === 0 && dots.length > 0) {
      checkCometCollisions(dt, time);
    }

    renderer.render(scene, camera);
  }

  /* Camera */
  const camZ = new THREE.Vector3(3.4, -0.6, 10).normalize();
  const camLook = new THREE.Vector3(0, 5, 0);
  const fovDist = 5 / Math.tan(((67 * Math.PI) / 180) * 0.5);
  camera.position.copy(camLook).addScaledVector(camZ, fovDist);
  camera.lookAt(camLook);

  rebuild();
  ro.observe(container);
  resize();

  rafId = requestAnimationFrame(animate);

  return {
    rebuild,
    dispose(): void {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerleave", onPointerLeave);
      container.removeEventListener("pointercancel", onPointerLeave);
      for (const d of disposables) {
        try {
          d.dispose();
        } catch {
          /* noop */
        }
      }
      disposables.length = 0;
      renderer.dispose();
    },
  };
}
