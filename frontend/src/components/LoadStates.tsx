import type { ReactNode } from "react";

function Bar({ className }: { className: string }) {
  return <div className={`rounded-md bg-slate-200 dark:bg-slate-800 ${className}`} />;
}

// Placeholder in the shape of what's loading, so the page doesn't jump
// when the data lands. listOnly skips the header/tabs (for a tab whose
// data loads after the page itself).
export function LoadingSkeleton({ listOnly = false }: { listOnly?: boolean }) {
  return (
    <div className="motion-safe:animate-pulse" role="status" aria-label="Loading">
      {!listOnly && (
        <div className="mb-6 space-y-3">
          <div className="flex items-center gap-2">
            <Bar className="h-9 w-9 rounded-lg" />
            <Bar className="h-7 w-56" />
          </div>
          <Bar className="h-4 w-48" />
          <Bar className="h-4 w-full max-w-xl" />
          <div className="flex gap-4 pt-3">
            <Bar className="h-5 w-14" />
            <Bar className="h-5 w-24" />
            <Bar className="h-5 w-16" />
            <Bar className="h-5 w-10" />
          </div>
        </div>
      )}
      <Bar className="mb-4 h-16 w-full rounded-xl" />
      <div className="space-y-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="space-y-3 rounded-xl border border-slate-200 p-3.5 dark:border-slate-800">
            <div className="flex justify-between">
              <Bar className="h-4 w-36" />
              <Bar className="h-4 w-14 rounded-full" />
            </div>
            <Bar className="h-4 w-56" />
            <div className="grid grid-cols-3 gap-2">
              <Bar className="h-7" />
              <Bar className="h-7" />
              <Bar className="h-7" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// A load failure in the reader's terms, with a way out.
export function LoadError({ what, detail, children }: { what: string; detail: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-900 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
      <p className="font-medium">Couldn&apos;t load {what}.</p>
      <p className="mt-1 text-sm">
        Check your connection and try again.{children}
      </p>
      <p className="mt-1 break-words text-xs opacity-75">{detail}</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="press mt-3 h-11 rounded-lg bg-red-900 px-4 text-sm font-medium text-white hover:bg-red-800 dark:bg-red-200 dark:text-red-950 dark:hover:bg-red-100 sm:h-9"
      >
        Try again
      </button>
    </div>
  );
}
