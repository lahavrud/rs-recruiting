/* WebGL renderer for the hero's silk backdrop — layered bands of "molten
   silk" pouring through the void beside the hero copy. Hand-rolled fragment
   shader on a fullscreen triangle: no 3D library, one draw call per frame.

   Color travels the warm-sunset ramp the tokens reserve for exactly this
   (plum → wine → copper → gold); all colors are read from the CSS tokens at
   runtime, never duplicated here except as jsdom-only fallbacks. */

import * as Sentry from "@sentry/react";

export type RGB = readonly [number, number, number];

export interface SilkPalette {
  voidColor: RGB;
  plum: RGB;
  wine: RGB;
  copper: RGB;
  gold: RGB;
  goldLight: RGB;
}

export interface SilkRenderer {
  resize(width: number, height: number, dpr: number): void;
  draw(time: number, pointerX: number, pointerY: number, fade: number): void;
  dispose(): void;
}

const VERT_SRC = `#version 300 es
void main() {
  /* Fullscreen triangle from gl_VertexID — no buffers, no attributes. */
  vec2 corners[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
  gl_Position = vec4(corners[gl_VertexID], 0.0, 1.0);
}`;

const FRAG_SRC = `#version 300 es
precision highp float;

uniform vec2 uRes;
uniform float uTime;
uniform vec2 uPointer;
uniform float uFade;
uniform vec3 uVoid;
uniform vec3 uPlum;
uniform vec3 uWine;
uniform vec3 uCopper;
uniform vec3 uGold;
uniform vec3 uGoldLight;

out vec4 outColor;

float hash21(vec2 p) {
  p = fract(p * vec2(234.34, 435.345));
  p += dot(p, p + 34.23);
  return fract(p.x * p.y);
}

/* Warm-metal ramp: plum -> wine -> copper -> gold -> gold-light.
   The wine zone is kept narrow — any wider and it reads candy-pink. */
vec3 ramp(float t) {
  t = clamp(t, 0.0, 1.0);
  vec3 c = mix(uPlum, uWine, smoothstep(0.00, 0.20, t));
  c = mix(c, uCopper, smoothstep(0.14, 0.46, t));
  c = mix(c, uGold, smoothstep(0.44, 0.78, t));
  c = mix(c, uGoldLight, smoothstep(0.76, 1.00, t));
  return c;
}

/* One silk band. uv is layer-normalized (y up). cx anchors the centerline,
   slant leans it diagonally, amp drives the meander, halfW the band width. */
vec3 band(vec2 uv, float cx, float slant, float amp, float halfW, float phase, float gain) {
  float t = uTime;

  /* Domain-warp the flow coordinate so the meander feels organic. */
  float y = uv.y + 0.05 * sin(uv.y * 3.7 + t * 0.11 + phase * 2.1);

  /* Centerline: diagonal lean + three meander octaves + pointer bow. */
  float c = cx + slant * (y - 0.5)
    + amp * sin(y * 2.4 + t * 0.16 + phase)
    + amp * 0.45 * sin(y * 5.3 - t * 0.10 + phase * 1.7)
    + amp * 0.18 * sin(y * 9.1 + t * 0.23 + phase * 2.9)
    + uPointer.x * 0.045 * (0.35 + 0.65 * y);

  /* Twist: the band narrows where it turns edge-on, widens face-on. */
  float turn = 0.5 + 0.5 * sin(y * 2.2 - t * 0.13 + phase * 3.3);
  float w = halfW * mix(0.30, 1.0, turn);

  /* Signed cross-band coordinate: -1..1 between the silk's edges.
     Edges stay defined — silk, not smoke. */
  float s = (uv.x - c) / w;
  float body = pow(smoothstep(1.0, 0.45, abs(s)), 1.9);

  /* Fine threads running along the weave. */
  float threads = 0.78 + 0.22 * sin(s * 12.0 + y * 24.0 - t * 0.4 + phase * 5.0);

  /* A specular sheen that slides slowly across the width. */
  float sheenPos = 0.55 * sin(t * 0.19 + y * 1.9 + phase * 1.3) - uPointer.y * 0.2;
  float sheen = exp(-pow((s - sheenPos) / 0.26, 2.0));

  /* Folds (where the band turns edge-on) catch more light. */
  float fold = 1.0 + 1.8 * pow(1.0 - turn, 2.0);

  /* Hue rises through the ramp with height, shifted across the width.
     Starts above the plum floor so the base reads burgundy-bronze. */
  vec3 col = ramp(0.18 + y * 0.72 + s * 0.08 + 0.04 * sin(t * 0.07 + phase));

  /* Tight halo — just a breath of light into the void, not a wash. */
  float halo = 0.10 * exp(-abs(uv.x - c) / (w * 1.8));

  float core = body * threads * (0.40 + 1.05 * sheen) * fold;
  return col * (core + halo) * gain;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes;

  vec3 acc = vec3(0.0);
  /* Back band: broad, dim, opposite lean — atmospheric depth. */
  acc += band(uv, 0.34, 0.42, 0.16, 0.26, 5.1, 0.45);
  /* Hero band: the main pour of copper and gold, sweeping diagonally. */
  acc += band(uv, 0.45, -0.34, 0.13, 0.17, 0.0, 1.1);
  /* Accent filament: a narrow bright thread riding the hero band. */
  acc += band(uv, 0.49, -0.36, 0.13, 0.05, 0.55, 0.9);

  /* Edge discipline: dissolve before the copy column (inline-start side)
     and duck out before passing behind the navbar — its backdrop-blur would
     smear anything bright into a seam. No bottom fade: the canvas ends on
     the client ribbon's top border, which cuts the silk clean. */
  float fade = 1.0 - 0.85 * smoothstep(0.80, 0.985, uv.y);
  fade *= 1.0 - smoothstep(0.70, 0.97, uv.x);
  acc *= fade * uFade;

  /* Filmic-ish rolloff keeps highlights molten instead of clipped. */
  vec3 col = vec3(1.0) - exp(-acc * 1.5);

  /* Grain dithers away gradient banding on the near-black ground. */
  float grain = (hash21(gl_FragCoord.xy + fract(uTime) * 100.0) - 0.5) * (3.0 / 255.0);

  outColor = vec4(uVoid + col + grain, 1.0);
}`;

/* Mirrors of the index.css @theme tokens — reachable only where computed
   styles are unavailable (jsdom); the browser always reads the live tokens. */
const FALLBACK_PALETTE: SilkPalette = {
  voidColor: [0.051, 0.043, 0.035],
  plum: [0.353, 0.165, 0.29],
  wine: [0.549, 0.29, 0.333],
  copper: [0.722, 0.451, 0.2],
  gold: [0.788, 0.659, 0.298],
  goldLight: [0.867, 0.749, 0.447],
};

function parseHexColor(raw: string): RGB | null {
  const hex = raw.trim().replace(/^#/, "");
  if (!/^[0-9a-f]{3}$|^[0-9a-f]{6}$/i.test(hex)) return null;
  const full =
    hex.length === 3
      ? hex
          .split("")
          .map((ch) => ch + ch)
          .join("")
      : hex;
  const CHANNEL_MAX = 255;
  const HEX_RADIX = 16;
  return [
    parseInt(full.slice(0, 2), HEX_RADIX) / CHANNEL_MAX,
    parseInt(full.slice(2, 4), HEX_RADIX) / CHANNEL_MAX,
    parseInt(full.slice(4, 6), HEX_RADIX) / CHANNEL_MAX,
  ];
}

/** Read the silk colors from the live CSS tokens (single source of truth). */
export function readSilkPalette(): SilkPalette {
  const styles = getComputedStyle(document.documentElement);
  const token = (name: string, fallback: RGB): RGB =>
    parseHexColor(styles.getPropertyValue(name)) ?? fallback;
  return {
    voidColor: token("--color-void", FALLBACK_PALETTE.voidColor),
    plum: token("--color-plum", FALLBACK_PALETTE.plum),
    wine: token("--color-wine", FALLBACK_PALETTE.wine),
    copper: token("--color-copper", FALLBACK_PALETTE.copper),
    gold: token("--color-gold", FALLBACK_PALETTE.gold),
    goldLight: token("--color-gold-light", FALLBACK_PALETTE.goldLight),
  };
}

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

/* Methods this renderer calls on the context. Anti-fingerprinting extensions,
   privacy-hardened browsers and some in-app WebViews hand back a stub object
   that passes the null check but implements almost none of the API — probe it
   before touching it so we take the CSS-wash rung of the ladder instead of
   throwing (`gl.getShaderParameter is not a function`, seen in production). */
const REQUIRED_GL_METHODS = [
  "createShader",
  "shaderSource",
  "compileShader",
  "getShaderParameter",
  "deleteShader",
  "createProgram",
  "attachShader",
  "linkProgram",
  "getProgramParameter",
  "deleteProgram",
  "useProgram",
  "getUniformLocation",
  "uniform1f",
  "uniform2f",
  "uniform3f",
  "viewport",
  "drawArrays",
  "isContextLost",
  "getExtension",
] as const;

function acquireContext(canvas: HTMLCanvasElement): WebGL2RenderingContext | null {
  let gl: WebGL2RenderingContext | null;
  try {
    gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
  } catch {
    // Some hardened builds throw outright rather than returning null.
    return null;
  }
  if (!gl) return null;
  const usable = REQUIRED_GL_METHODS.every((name) => typeof gl[name] === "function");
  return usable ? gl : null;
}

/* Falling back is silent for the user by design, but a silent fallback is an
   invisible regression: if a shader or uniform edit made `draw` throw for
   everyone, the hero would quietly become a CSS gradient and nobody would
   hear about it.

   Only *thrown* failures are reported. An absent or stubbed context is a
   supported rung of the ladder — reporting it would just log every visitor
   running a privacy extension. Report once per page load: these paths can
   fire per frame, and the wash looks fine, so this is a signal to watch
   rather than an incident. */
let silkFailureReported = false;

/** Report a handled silk failure to Sentry, at most once per page load. */
export function reportSilkFailure(cause: unknown): void {
  if (silkFailureReported) return;
  silkFailureReported = true;
  Sentry.captureException(cause, {
    level: "warning",
    tags: { feature: "landing-silk" },
  });
}

/** Build the renderer, or `null` on any environment we can't draw in — the
    caller falls back to the CSS wash. Never throws: a shimmed context can have
    every method and still throw when called, and this runs inside an effect,
    where an escaping error would take the whole landing page down with it. */
export function createSilkRenderer(
  canvas: HTMLCanvasElement,
  palette: SilkPalette,
): SilkRenderer | null {
  try {
    return buildSilkRenderer(canvas, palette);
  } catch (cause) {
    reportSilkFailure(cause);
    return null;
  }
}

function buildSilkRenderer(
  canvas: HTMLCanvasElement,
  palette: SilkPalette,
): SilkRenderer | null {
  const gl = acquireContext(canvas);
  if (!gl) return null;

  const vert = compileShader(gl, gl.VERTEX_SHADER, VERT_SRC);
  const frag = compileShader(gl, gl.FRAGMENT_SHADER, FRAG_SRC);
  if (!vert || !frag) return null;

  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vert);
  gl.attachShader(program, frag);
  gl.linkProgram(program);
  gl.deleteShader(vert);
  gl.deleteShader(frag);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program);
    return null;
  }
  gl.useProgram(program);

  const uRes = gl.getUniformLocation(program, "uRes");
  const uTime = gl.getUniformLocation(program, "uTime");
  const uPointer = gl.getUniformLocation(program, "uPointer");
  const uFade = gl.getUniformLocation(program, "uFade");

  const setColor = (name: string, [r, g, b]: RGB) => {
    gl.uniform3f(gl.getUniformLocation(program, name), r, g, b);
  };
  setColor("uVoid", palette.voidColor);
  setColor("uPlum", palette.plum);
  setColor("uWine", palette.wine);
  setColor("uCopper", palette.copper);
  setColor("uGold", palette.gold);
  setColor("uGoldLight", palette.goldLight);

  let width = 0;
  let height = 0;

  return {
    resize(cssWidth, cssHeight, dpr) {
      const newWidth = Math.max(1, Math.round(cssWidth * dpr));
      const newHeight = Math.max(1, Math.round(cssHeight * dpr));
      // Reassigning canvas.width/height reallocates the GL drawing buffer —
      // skip it when the pixel size hasn't actually changed, so a drag-resize
      // that fires many same-size observer ticks doesn't churn the GPU.
      if (newWidth === width && newHeight === height) return;
      width = newWidth;
      height = newHeight;
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
      gl.uniform2f(uRes, width, height);
    },
    draw(time, pointerX, pointerY, fade) {
      if (!width || !height || gl.isContextLost()) return;
      gl.uniform1f(uTime, time);
      gl.uniform2f(uPointer, pointerX, pointerY);
      gl.uniform1f(uFade, fade);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    dispose() {
      gl.deleteProgram(program);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}
