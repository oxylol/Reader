import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, coverUrl } from "../lib/api";

export default function SeriesPage() {
  const { id } = useParams();
  const seriesId = Number(id);
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data: series } = useQuery({
    queryKey: ["series", seriesId],
    queryFn: () => api.series(seriesId),
  });
  const { data: job } = useQuery({
    queryKey: ["job", seriesId],
    queryFn: () => api.jobForSeries(seriesId),
    refetchInterval: (q) => {
      const s = q.state.data?.state;
      return s === "running" || s === "queued" ? 2000 : false;
    },
  });
  const jobActive = job?.state === "running" || job?.state === "queued";
  const { data: chapters, isLoading } = useQuery({
    queryKey: ["chapters", seriesId],
    queryFn: () => api.chapters(seriesId),
    // While a download job is populating chapters, keep refetching so the list
    // fills in without a manual reload.
    refetchInterval: jobActive ? 3000 : false,
  });

  const unfollow = useMutation({
    mutationFn: () => api.unfollow(seriesId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      nav("/");
    },
  });
  const redownload = useMutation({
    mutationFn: () => api.download(seriesId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", seriesId] }),
  });

  const progressPct = useMemo(() => {
    if (!job || !job.total_chapters) return 0;
    return Math.round((job.done_chapters / job.total_chapters) * 100);
  }, [job]);

  const firstUnread = useMemo(() => {
    if (!chapters) return null;
    return chapters.find((c) => !c.read && c.downloaded) ?? chapters.find((c) => c.downloaded);
  }, [chapters]);

  if (!series) return <div className="spinner" />;

  return (
    <>
      <header className="topbar">
        <button className="back" onClick={() => nav(-1)}>←</button>
        <h1 style={{ fontSize: 16 }}>{series.title}</h1>
      </header>
      <div className="content">
        <div className="series-hero">
          <img className="cover" src={coverUrl(series.cover_url)} alt={series.title} />
          <div className="series-meta">
            <h2>{series.title}</h2>
            <div className="muted">
              {series.type} · {series.status}
              {series.year ? ` · ${series.year}` : ""}
            </div>
            <div className="muted" style={{ marginTop: 4 }}>
              {series.downloaded_count}/{series.chapter_count} chapters downloaded
            </div>
          </div>
        </div>

        {job && (job.state === "running" || job.state === "queued") && (
          <div style={{ marginTop: 14 }}>
            <div className="muted" style={{ marginBottom: 6 }}>
              Downloading… {job.message || `${job.done_chapters}/${job.total_chapters}`}
            </div>
            <div className="progress-bar">
              <div style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        )}

        <div className="reader-row" style={{ marginTop: 14, gap: 8 }}>
          {firstUnread && (
            <button className="btn" onClick={() => nav(`/read/${firstUnread.id}`)}>
              {chapters?.some((c) => c.read) ? "Continue" : "Start reading"}
            </button>
          )}
          <button className="btn secondary" onClick={() => redownload.mutate()}>
            Check for updates
          </button>
          <button className="btn danger" onClick={() => unfollow.mutate()}>
            Remove
          </button>
        </div>

        {series.tags.length > 0 && (
          <div className="tag-list" style={{ marginTop: 12 }}>
            {series.tags.map((t) => (
              <span className="tag" key={t}>{t}</span>
            ))}
          </div>
        )}

        {series.description && (
          <p className="desc" style={{ marginTop: 12 }}>{series.description}</p>
        )}

        <div className="section-title">Chapters</div>
        {isLoading && <div className="spinner" />}
        <div className="chapter-list">
          {chapters?.map((c) => (
            <div
              key={c.id}
              className={`chapter-item ${c.read ? "read" : ""}`}
              onClick={() => c.downloaded && nav(`/read/${c.id}`)}
              style={{ opacity: c.downloaded ? undefined : 0.4 }}
            >
              <span className={`dot ${c.read ? "off" : ""}`} />
              <span className="num">
                Ch. {c.number_label || c.number}
                {c.title ? ` — ${c.title}` : ""}
              </span>
              <span className="muted">
                {c.downloaded ? `${c.page_count}p` : "…"}
              </span>
            </div>
          ))}
          {chapters && chapters.length === 0 && (
            <div className="center-msg">
              No chapters yet — the download job is fetching the list.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
