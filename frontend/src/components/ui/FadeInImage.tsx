import { type ImgHTMLAttributes, useState } from "react";

interface FadeInImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  /** Transition duration in ms (default 600). */
  fadeMs?: number;
}

/**
 * <img> wrapper that fades in once the asset has finished loading.
 * Mirrors the pattern used by Logo / LandingPage hero so every public-facing
 * image avoids the flash of broken-image placeholder under slow networks.
 */
export default function FadeInImage({
  fadeMs = 600,
  className = "",
  style,
  onLoad,
  ...rest
}: FadeInImageProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  return (
    <img
      {...rest}
      onLoad={(e) => {
        setIsLoaded(true);
        onLoad?.(e);
      }}
      className={className}
      style={{
        ...style,
        opacity: isLoaded ? 1 : 0,
        transition: `opacity ${fadeMs}ms ease-out`,
      }}
    />
  );
}
