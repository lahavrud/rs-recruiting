import { useEffect, useState } from "react";

/**
 * Returns `true` once `src` has finished loading.
 *
 * Useful for CSS `background-image: url(...)` — those have no native load
 * event, so the dark overlay would otherwise appear over a blank area until
 * the network delivers the photo. Preload via `new Image()` and flip a
 * boolean once it's available; treat errors as "done" so the UI doesn't
 * stall when an asset 404s.
 *
 * For plain `<img>` elements, prefer `<FadeInImage>` (uses native onLoad).
 */
export function useImageLoaded(src: string): boolean {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const img = new Image();
    const finish = () => {
      if (!cancelled) setIsLoaded(true);
    };
    img.onload = finish;
    img.onerror = finish;
    img.src = src;
    // Cached images may already be complete by the time the listener attaches.
    if (img.complete) finish();
    return () => {
      cancelled = true;
    };
  }, [src]);

  return isLoaded;
}
