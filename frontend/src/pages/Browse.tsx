import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { DiscoverItem, SearchRequest } from "../lib/types";

const SHELVES = [
  { key: "trending", label: "Trending" },
  { key: "latest", label: "Latest" },
  { key: "newly_added", label: "New" },
  { key: "top_rated", label: "Top rated" },
];
const TIMEFRAMES = [
  { key: "today", label: "Today" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "all", label: "All" },
];
const TYPES = ["manga", "manhwa", "manhua"];
const STATUSES = ["ongoing", "completed", "hiatus", "cancelled"];
const SORTS = [
  { key: "popularity", label: "Popularity" },
  { key: "rating", label: "Rating" },
  { key: "latest", label: "Latest update" },
  { key: "recent", label: "Recently added" },
  { key: "chapters", label: "Chapter count" },
];
const GENRES = [
  "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
  "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller",
];

export default function Browse() {
  const [tab, setTab] = useState<"trending" | "search">("trending");
  return (
    <>
      <header className="topbar">
        <h1>Browse</h1>
        <div className="seg">
          <button className={tab === "trending" ? "on" : ""} onClick={() => setTab("trending")}>
            Trending
          </button>
          <button className={tab === "search" ? "on" : ""} onClick={() => setTab("search")}>
            Search
          </button>
        </div>
      </header>
      <div className="content">
        {tab === "trending" ? <Trending /> : <Search />}
      </div>
    </>
  );
}

function Trending() {
  const [shelf, setShelf] = useState("trending");
  const [tf, setTf] = useState("week");
  const { data, isLoading } = useQuery({
    queryKey: ["trending", shelf, tf],
    queryFn: () => api.trending(shelf, tf),
  });
  return (
    <>
      <div className="chip-row" style={{ marginBottom: 10 }}>
        {SHELVES.map((s) => (
          <button
            key={s.key}
            className={`chip ${shelf === s.key ? "on" : ""}`}
            onClick={() => setShelf(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>
      {shelf === "trending" && (
        <div className="chip-row" style={{ marginBottom: 14 }}>
          {TIMEFRAMES.map((t) => (
            <button
              key={t.key}
              className={`chip ${tf === t.key ? "on" : ""}`}
              onClick={() => setTf(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      {isLoading ? (
        <div className="spinner" />
      ) : (
        <ResultGrid items={data ?? []} />
      )}
    </>
  );
}

function Search() {
  const [query, setQuery] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [status, setStatus] = useState<string[]>([]);
  const [include, setInclude] = useState<string[]>([]);
  const [exclude, setExclude] = useState<string[]>([]);
  const [sort, setSort] = useState("popularity");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [results, setResults] = useState<DiscoverItem[] | null>(null);

  const mut = useMutation({
    mutationFn: (body: SearchRequest) => api.search(body),
    onSuccess: setResults,
  });

  function toggle(list: string[], set: (v: string[]) => void, v: string) {
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }
  // genre tri-state: none -> include -> exclude -> none
  function cycleGenre(g: string) {
    if (include.includes(g)) {
      setInclude(include.filter((x) => x !== g));
      setExclude([...exclude, g]);
    } else if (exclude.includes(g)) {
      setExclude(exclude.filter((x) => x !== g));
    } else {
      setInclude([...include, g]);
    }
  }

  function run(e?: React.FormEvent) {
    e?.preventDefault();
    mut.mutate({
      query,
      types,
      status,
      include_tags: include,
      exclude_tags: exclude,
      sort,
      year_from: yearFrom ? Number(yearFrom) : null,
      year_to: yearTo ? Number(yearTo) : null,
      limit: 40,
    });
  }

  return (
    <>
      <form onSubmit={run} style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          className="input"
          placeholder="Search title…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn" type="submit">Go</button>
      </form>

      <button
        className="chip"
        onClick={() => setShowFilters((v) => !v)}
        style={{ marginBottom: 12 }}
      >
        {showFilters ? "Hide filters ▲" : "Filters ▼"}
      </button>

      {showFilters && (
        <div style={{ marginBottom: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div className="muted">Type</div>
            <div className="chip-row">
              {TYPES.map((t) => (
                <button
                  key={t}
                  className={`chip ${types.includes(t) ? "on" : ""}`}
                  onClick={() => toggle(types, setTypes, t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="muted">Status</div>
            <div className="chip-row">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  className={`chip ${status.includes(s) ? "on" : ""}`}
                  onClick={() => toggle(status, setStatus, s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="muted">Genres (tap: include → exclude → off)</div>
            <div className="chip-row">
              {GENRES.map((g) => (
                <button
                  key={g}
                  className={`chip ${
                    include.includes(g) ? "on" : exclude.includes(g) ? "exclude" : ""
                  }`}
                  onClick={() => cycleGenre(g)}
                >
                  {exclude.includes(g) ? "− " : include.includes(g) ? "+ " : ""}
                  {g}
                </button>
              ))}
            </div>
          </div>
          <div className="reader-row">
            <div style={{ flex: 1 }}>
              <div className="muted">Year from</div>
              <input
                className="input"
                inputMode="numeric"
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
              />
            </div>
            <div style={{ flex: 1 }}>
              <div className="muted">Year to</div>
              <input
                className="input"
                inputMode="numeric"
                value={yearTo}
                onChange={(e) => setYearTo(e.target.value)}
              />
            </div>
          </div>
          <div>
            <div className="muted">Sort</div>
            <select
              className="input"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
          <button className="btn block" onClick={() => run()}>Apply filters</button>
        </div>
      )}

      {mut.isPending && <div className="spinner" />}
      {results && results.length === 0 && (
        <div className="center-msg">
          No results. Try relaxing your filters or clearing excluded genres.
        </div>
      )}
      {results && results.length > 0 && <ResultList items={results} />}
    </>
  );
}

function AddButton({ item }: { item: DiscoverItem }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const mut = useMutation({
    mutationFn: () => api.addSeries(item.source, item.source_id),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["library"] });
      nav(`/series/${s.id}`);
    },
  });
  if (item.in_library) {
    return <span className="chip on" style={{ pointerEvents: "none" }}>In library</span>;
  }
  return (
    <button className="btn" disabled={mut.isPending} onClick={() => mut.mutate()}>
      {mut.isPending ? "Adding…" : "+ Add"}
    </button>
  );
}

function ResultGrid({ items }: { items: DiscoverItem[] }) {
  if (items.length === 0) return <div className="center-msg">Nothing here yet.</div>;
  return (
    <div className="discover-list">
      {items.map((it) => (
        <DiscoverRow key={`${it.source}:${it.source_id}`} item={it} />
      ))}
    </div>
  );
}
function ResultList({ items }: { items: DiscoverItem[] }) {
  return (
    <div className="discover-list">
      {items.map((it) => (
        <DiscoverRow key={`${it.source}:${it.source_id}`} item={it} />
      ))}
    </div>
  );
}

function DiscoverRow({ item }: { item: DiscoverItem }) {
  return (
    <div className="discover-row">
      <img
        className="cover"
        src={item.cover_url || "/icon-512.png"}
        alt={item.title}
        loading="lazy"
      />
      <div className="info">
        <h3>{item.title}</h3>
        <div className="muted">
          {item.type !== "unknown" ? item.type : ""}
          {item.status !== "unknown" ? ` · ${item.status}` : ""}
          {item.year ? ` · ${item.year}` : ""}
          {item.sources.length > 1 ? ` · ${item.sources.length} sources` : ""}
        </div>
        {item.tags.length > 0 && (
          <div className="tag-list">
            {item.tags.slice(0, 4).map((t) => (
              <span className="tag" key={t}>{t}</span>
            ))}
          </div>
        )}
        <div style={{ marginTop: 8 }}>
          <AddButton item={item} />
        </div>
      </div>
    </div>
  );
}
