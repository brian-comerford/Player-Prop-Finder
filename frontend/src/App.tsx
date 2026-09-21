import { useEffect, useMemo, useState } from "react";
import Banner from "./components/Banner";
import Filters, { DEFAULT_FILTERS, type FilterState } from "./components/Filters";
import PropsTable from "./components/PropsTable";
import PropDetail from "./components/PropDetail";
import InfoPage from "./components/InfoPage";
import { fetchMeta, fetchProps } from "./lib/data";
import type { Meta, Prop } from "./lib/types";
import { sideEdge } from "./lib/odds";
import { useTheme } from "./lib/useTheme";

const CONFIDENCE_RANK: Record<string, number> = { Low: 0, Medium: 1, High: 2 };
type Tab = "props" | "info";

export default function App() {
  const [props, setProps] = useState<Prop[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<Prop | null>(null);
  const [tab, setTab] = useState<Tab>("props");
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    Promise.all([fetchProps(), fetchMeta()])
      .then(([p, m]) => {
        setProps(p);
        setMeta(m);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const filtered = useMemo(() => {
    if (!props) return [];
    const search = filters.search.trim().toLowerCase();
    const minConfidenceRank = CONFIDENCE_RANK[filters.minConfidence] ?? 0;
    return props
      .filter((p) => (search ? p.player_name.toLowerCase().includes(search) : true))
      .filter((p) => (filters.position === "All" ? true : p.position === filters.position))
      .filter((p) => (filters.market === "All" ? true : p.market === filters.market))
      .filter((p) => (filters.matchup === "All" ? true : p.matchup === filters.matchup))
      .filter((p) => (filters.timeSlot === "All" ? true : p.time_slot === filters.timeSlot))
      .filter((p) => (sideEdge(p, p.recommended_side) ?? 0) >= filters.minEdge)
      .filter((p) => CONFIDENCE_RANK[p.confidence] >= minConfidenceRank)
      .sort((a, b) => b.recommended_edge - a.recommended_edge);
  }, [props, filters]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
          Couldn't load prop data ({error}). If you're running this locally, make sure you've
          run <code>npm run sync-data</code> after generating <code>data/*.json</code>.
        </div>
      )}

      {!error && (!props || !meta) && (
        <div className="py-20 text-center text-slate-500 dark:text-slate-400">Loading props…</div>
      )}

      {props && meta && (
        <div className="space-y-5">
          <Banner meta={meta} />

          <div className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
            {(["props", "info"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                  tab === t
                    ? "border-slate-900 text-slate-900 dark:border-white dark:text-white"
                    : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                {t === "props" ? "Props" : "Info"}
              </button>
            ))}
          </div>

          {tab === "props" ? (
            <>
              <Filters meta={meta} filters={filters} onChange={setFilters} />
              <div className="text-sm text-slate-500 dark:text-slate-400">
                Showing {filtered.length} of {props.length} props
              </div>
              <PropsTable props={filtered} onSelect={setSelected} />
            </>
          ) : (
            <InfoPage theme={theme} onThemeChange={setTheme} />
          )}
        </div>
      )}

      {selected && <PropDetail prop={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
