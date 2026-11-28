import { useEffect, useId, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { useLockBodyScroll } from "../lib/useLockBodyScroll";

// How long the exit transition runs before the sheet actually unmounts --
// keep in step with .sheet-panel[data-closing] in index.css.
const EXIT_MS = 260;
// A drag-down past this share of the sheet's height, or a flick faster
// than this (px/ms), dismisses it; anything less springs back.
const DISMISS_DISTANCE = 0.25;
const DISMISS_VELOCITY = 0.5;

function isPhoneLayout(): boolean {
  return window.matchMedia("(max-width: 639px)").matches;
}

// The detail/track-record overlay: a bottom sheet on phones (slides up,
// drag the header down to dismiss) and a centered dialog from sm: up.
// Owns its own enter/exit transitions, so callers just unmount it from
// onClose -- which only fires once the exit has finished playing.
export default function Sheet({
  title,
  subtitle,
  onClose,
  maxWidth = "sm:max-w-2xl",
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  maxWidth?: string;
  children: ReactNode;
}) {
  useLockBodyScroll();
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const closingRef = useRef(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const drag = useRef<{ startY: number; lastY: number; lastT: number; velocity: number } | null>(null);

  function close() {
    if (closingRef.current) return;
    closingRef.current = true;
    setClosing(true);
    setOpen(false);
    window.setTimeout(() => onCloseRef.current(), EXIT_MS);
  }

  useEffect(() => {
    // Mount in the closed position, then flip to open on the next frame so
    // the transition has a starting point to animate from.
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const frame = requestAnimationFrame(() => {
      setOpen(true);
      panelRef.current?.focus({ preventScroll: true });
    });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.({ preventScroll: true });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    // Let taps on the close button through as ordinary clicks.
    if (!isPhoneLayout() || closingRef.current || (e.target as Element).closest("button")) return;
    drag.current = { startY: e.clientY, lastY: e.clientY, lastT: e.timeStamp, velocity: 0 };
    e.currentTarget.setPointerCapture(e.pointerId);
    if (panelRef.current) panelRef.current.style.transition = "none";
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    const panel = panelRef.current;
    if (!d || !panel) return;
    const raw = e.clientY - d.startY;
    // Dragging up past the resting point gets heavy friction instead of
    // stopping dead, so it still feels attached to the finger.
    const dy = raw >= 0 ? raw : -Math.sqrt(-raw) * 2;
    panel.style.transform = `translateY(${dy}px)`;
    const dt = e.timeStamp - d.lastT;
    if (dt > 0) d.velocity = (e.clientY - d.lastY) / dt;
    d.lastY = e.clientY;
    d.lastT = e.timeStamp;
  }

  function onPointerEnd(e: PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    const panel = panelRef.current;
    drag.current = null;
    if (!d || !panel) return;
    const dy = e.clientY - d.startY;
    // Hand the transform back to the stylesheet: it either springs back to
    // open or carries on to closed from wherever the finger let go.
    panel.style.transition = "";
    panel.style.transform = "";
    if (dy > panel.offsetHeight * DISMISS_DISTANCE || (d.velocity > DISMISS_VELOCITY && dy > 10)) close();
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center sm:items-center sm:p-4">
      <div
        className="sheet-overlay absolute inset-0 bg-black/40"
        data-open={open}
        data-closing={closing || undefined}
        onClick={close}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-open={open}
        data-closing={closing || undefined}
        className={`sheet-panel relative flex w-full flex-col rounded-t-2xl bg-white shadow-xl outline-none dark:bg-slate-900 sm:rounded-2xl ${maxWidth}`}
      >
        <div
          className="sheet-handle shrink-0 px-5 pb-3 pt-2 sm:pt-5"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
        >
          <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-700 sm:hidden" aria-hidden="true" />
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id={titleId} className="text-xl font-bold tracking-tight">
                {title}
              </h2>
              {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={close}
              className="press -mr-2 -mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label="Close"
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
        <div className="sheet-body min-h-0 flex-1 overflow-y-auto px-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
          {children}
        </div>
      </div>
    </div>
  );
}
