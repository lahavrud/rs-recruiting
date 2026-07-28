import { createSilkRenderer, readSilkPalette } from "../landingSilkUtils";

/* jsdom has no WebGL2, so `getContext("webgl2")` returns null and the renderer
   already takes the CSS-wash path. These cases cover the hostile contexts we
   saw in production instead: privacy extensions, hardened browsers and in-app
   WebViews that hand back something truthy but not a usable GL context. */

function canvasReturning(context: unknown): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.getContext = (() => context) as HTMLCanvasElement["getContext"];
  return canvas;
}

describe("createSilkRenderer", () => {
  const palette = readSilkPalette();

  it("falls back to the wash when WebGL2 is unavailable", () => {
    expect(createSilkRenderer(canvasReturning(null), palette)).toBeNull();
  });

  it("falls back to the wash for a stubbed context missing GL methods", () => {
    // The production failure: `e.getShaderParameter is not a function`.
    const stub = { VERTEX_SHADER: 0, FRAGMENT_SHADER: 1, createShader: () => ({}) };
    expect(createSilkRenderer(canvasReturning(stub), palette)).toBeNull();
  });

  it("falls back to the wash when getContext itself throws", () => {
    const canvas = document.createElement("canvas");
    canvas.getContext = (() => {
      throw new Error("WebGL is disabled");
    }) as HTMLCanvasElement["getContext"];
    expect(createSilkRenderer(canvas, palette)).toBeNull();
  });

  it("falls back to the wash when a present GL method throws", () => {
    expect(createSilkRenderer(canvasReturning(throwingContext()), palette)).toBeNull();
  });
});

/* A context whose methods all exist — so it clears the probe — but throw when
   called, the way a farbling shim behaves. */
function throwingContext(): unknown {
  return new Proxy(
    {},
    {
      get: (_target, prop) => {
        if (prop === "VERTEX_SHADER" || prop === "FRAGMENT_SHADER") return 0;
        return () => {
          throw new Error(`blocked: ${String(prop)}`);
        };
      },
    },
  );
}

describe("silk failure reporting", () => {
  afterEach(() => {
    vi.doUnmock("@sentry/react");
    vi.resetModules();
  });

  /** Re-import with a mocked Sentry so the module's one-shot flag starts fresh. */
  async function loadWithMockedSentry() {
    vi.resetModules();
    const captureException = vi.fn();
    vi.doMock("@sentry/react", () => ({ captureException }));
    return { captureException, mod: await import("../landingSilkUtils") };
  }

  it("reports a thrown GL failure once, however many times it recurs", async () => {
    const { captureException, mod } = await loadWithMockedSentry();
    const canvas = canvasReturning(throwingContext());
    const palette = mod.readSilkPalette();

    expect(mod.createSilkRenderer(canvas, palette)).toBeNull();
    expect(mod.createSilkRenderer(canvas, palette)).toBeNull();

    expect(captureException).toHaveBeenCalledTimes(1);
    expect(captureException.mock.calls[0]?.[1]).toMatchObject({
      tags: { feature: "landing-silk" },
    });
  });

  it("stays quiet for environments that simply lack WebGL2", async () => {
    // Every visitor on a privacy extension would otherwise be an event.
    const { captureException, mod } = await loadWithMockedSentry();
    const palette = mod.readSilkPalette();

    expect(mod.createSilkRenderer(canvasReturning(null), palette)).toBeNull();
    expect(mod.createSilkRenderer(canvasReturning({}), palette)).toBeNull();

    expect(captureException).not.toHaveBeenCalled();
  });
});
