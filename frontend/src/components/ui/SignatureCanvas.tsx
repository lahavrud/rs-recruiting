import { forwardRef, useMemo, useRef, useImperativeHandle } from "react";

import { useTranslation } from "react-i18next";
import ReactSignatureCanvas from "react-signature-canvas";

import Button from "@/components/ui/Button";

export interface SignatureCanvasRef {
  toDataURL: () => string;
  isEmpty: () => boolean;
  clear: () => void;
}

interface Props {
  hasError?: boolean;
  onBegin?: () => void;
}

const SignatureCanvas = forwardRef<SignatureCanvasRef, Props>(
  ({ hasError, onBegin }, ref) => {
    const { t } = useTranslation('common');
    const innerRef = useRef<ReactSignatureCanvas>(null);

    // Resolve copper token at mount so the pen color follows theme tokens.
    const penColor = useMemo(() => {
      if (typeof window === "undefined") return "var(--color-copper)";
      const v = getComputedStyle(document.documentElement)
        .getPropertyValue("--color-copper")
        .trim();
      return v || "var(--color-copper)";
    }, []);

    useImperativeHandle(ref, () => ({
      toDataURL: () => innerRef.current?.toDataURL("image/png") ?? "",
      isEmpty: () => innerRef.current?.isEmpty() ?? true,
      clear: () => innerRef.current?.clear(),
    }));

    return (
      <div className="space-y-2">
        <div
          className={`overflow-hidden rounded-sm border bg-well ${
            hasError ? "border-danger" : "border-white/15 focus-within:border-copper/60"
          }`}
        >
          <ReactSignatureCanvas
            ref={innerRef}
            onBegin={onBegin}
            canvasProps={{
              className: "w-full touch-none",
              height: 140,
              style: { display: "block" },
            }}
            backgroundColor="transparent"
            penColor={penColor}
          />
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => innerRef.current?.clear()}
        >
          {t("common:clear")}
        </Button>
      </div>
    );
  },
);

SignatureCanvas.displayName = "SignatureCanvas";
export default SignatureCanvas;
