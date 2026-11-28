import { useSyncExternalStore } from "react";

// Live match for a CSS media query, e.g. useMediaQuery("(min-width: 640px)").
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches
  );
}
