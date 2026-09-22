import { useEffect, useMemo, useRef, useState } from "react";
import { toPng } from "html-to-image";
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
// A saved-image table is meant to be a curated, shareable shortlist, not a
// screenshot of the entire dataset -- past this many rows the rendered PNG
// gets unwieldy to actually look at, and html-to-image's per-node cloning
// gets slow enough (multiple seconds, worse on a phone) that it reads as
// hung rather than working.
const EXPORT_ROW_LIMIT = 50;
type Tab = "props" | "info";

function summarizeFilters(filters: FilterState, meta: Meta): string {
  const parts: string[] = [];
  if (filters.search.trim()) parts.push(`Search: "${filters.search.trim()}"`);
  if (filters.position !== "All") parts.push(`Position: ${filters.position}`);
  if (filters.market !== "All") parts.push(meta.markets[filters.market] ?? filters.market);
  if (filters.matchup !== "All") parts.push(filters.matchup);
  if (filters.timeSlot !== "All") parts.push(filters.timeSlot);
  if (filters.minEdge > 0) parts.push(`Min. edge ${(filters.minEdge * 100).toFixed(0)}%+`);
  if (filters.minConfidence !== "Any") parts.push(`${filters.minConfidence}+ confidence`);
  return parts.length ? parts.join(" · ") : "No filters applied";
}

export default function App() {
  const [props, setProps] = useState<Prop[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<Prop | null>(null);
  const [tab, setTab] = useState<Tab>("props");
  const [exporting, setExporting] = useState(false);
  const tableWrapperRef = useRef<HTMLDivElement>(null);
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

  // Exports the current (filtered/sorted) table as a PNG someone can save or
  // share, e.g. after narrowing down to the bets they actually want. Builds
  // an off-screen clone rather than screenshotting the on-page table
  // directly, for two reasons: the visible table sits in a horizontally
  // scrolling container, so a direct capture would clip whatever's off
  // to the right; and the image is more useful as a standalone artifact
  // with its own title/filters/timestamp baked in, since it'll often be
  // viewed later with no other context (a saved file, a text to a friend).
  async function handleExportImage() {
    const tableEl = tableWrapperRef.current?.querySelector("table");
    if (!tableEl || !meta) return;
    if (filtered.length > EXPORT_ROW_LIMIT) {
      alert(
        `That's ${filtered.length} rows -- too many for one image (and painfully slow to render). ` +
          `Narrow it down with the filters above to ${EXPORT_ROW_LIMIT} or fewer props, then try again.`
      );
      return;
    }

    setExporting(true);
    const wrapper = document.createElement("div");
    const captureHost = document.createElement("div");
    try {
      const isDark = document.documentElement.classList.contains("dark");
      // html-to-image renders through an SVG <foreignObject>, which doesn't
      // reliably paint content from a fixed-position, far-off-screen node --
      // some engines lay it out but skip painting it. Absolute positioning
      // inside a zero-size, overflow-visible parent keeps it out of the
      // visible page (no reflow/flash) while still painting normally.
      wrapper.style.position = "absolute";
      wrapper.style.top = "0";
      wrapper.style.left = "0";
      wrapper.style.width = "max-content";
      wrapper.style.padding = "20px";
      wrapper.style.background = isDark ? "#0f172a" : "#ffffff";
      wrapper.style.fontFamily = getComputedStyle(document.body).fontFamily;

      captureHost.style.position = "fixed";
      captureHost.style.top = "0";
      captureHost.style.left = "0";
      captureHost.style.width = "0";
      captureHost.style.height = "0";
      captureHost.style.overflow = "visible";
      captureHost.style.zIndex = "-1";
      captureHost.appendChild(wrapper);

      const header = document.createElement("div");
      header.style.marginBottom = "12px";
      header.style.color = isDark ? "#e2e8f0" : "#0f172a";
      const title = document.createElement("div");
      title.style.fontSize = "18px";
      title.style.fontWeight = "700";
      title.textContent = "Player Prop Finder";
      const subtitle = document.createElement("div");
      subtitle.style.marginTop = "2px";
      subtitle.style.fontSize = "12px";
      subtitle.style.color = "#64748b";
      subtitle.textContent = `${summarizeFilters(filters, meta)} · ${filtered.length} props · ${new Date().toLocaleString()}`;
      header.appendChild(title);
      header.appendChild(subtitle);

      const tableFrame = document.createElement("div");
      tableFrame.style.border = `1px solid ${isDark ? "#1e293b" : "#e2e8f0"}`;
      tableFrame.style.borderRadius = "12px";
      tableFrame.style.overflow = "hidden";
      tableFrame.appendChild(tableEl.cloneNode(true));

      wrapper.appendChild(header);
      wrapper.appendChild(tableFrame);
      document.body.appendChild(captureHost);

      // Let the browser actually paint the newly-inserted content before
      // handing it to html-to-image -- without this, toPng can serialize
      // the node before layout has settled and come back with a blank image.
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

      const dataUrl = await toPng(wrapper, {
        pixelRatio: 2,
        width: wrapper.scrollWidth,
        height: wrapper.scrollHeight,
      });
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `player-prop-finder-${Date.now()}.png`;
      link.click();
    } catch (e) {
      console.error("Failed to export table image", e);
      alert("Couldn't save the image -- please try again.");
    } finally {
      if (captureHost.parentNode) captureHost.parentNode.removeChild(captureHost);
      setExporting(false);
    }
  }

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
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
                <span>
                  Showing {filtered.length} of {props.length} props
                </span>
                <div className="flex items-center gap-2">
                  {filtered.length > EXPORT_ROW_LIMIT && (
                    <span className="text-xs text-amber-600 dark:text-amber-400">
                      Narrow your filters to {EXPORT_ROW_LIMIT} or fewer props to save an image
                    </span>
                  )}
                  <button
                    onClick={handleExportImage}
                    disabled={exporting || filtered.length === 0 || filtered.length > EXPORT_ROW_LIMIT}
                    className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                  >
                    {exporting ? "Saving…" : "Save image"}
                  </button>
                </div>
              </div>
              <div ref={tableWrapperRef}>
                <PropsTable props={filtered} onSelect={setSelected} />
              </div>
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
