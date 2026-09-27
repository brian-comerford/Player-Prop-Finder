import { useEffect } from "react";

// A fixed-position overlay alone doesn't stop the page behind it from
// scrolling on mobile Safari -- a touch drag that starts anywhere on
// screen can still scroll the underlying body, dragging the "fixed"
// modal along with it and exposing the table rows behind. Pinning the
// body itself (position: fixed at its current scroll offset) is the
// standard workaround, since plain `overflow: hidden` on body is known
// to be ignored by iOS Safari for touch scrolling.
export function useLockBodyScroll() {
  useEffect(() => {
    const { body } = document;
    const scrollY = window.scrollY;
    const prev = {
      position: body.style.position,
      top: body.style.top,
      width: body.style.width,
      overflow: body.style.overflow,
    };

    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.width = "100%";
    body.style.overflow = "hidden";

    return () => {
      body.style.position = prev.position;
      body.style.top = prev.top;
      body.style.width = prev.width;
      body.style.overflow = prev.overflow;
      window.scrollTo(0, scrollY);
    };
  }, []);
}
