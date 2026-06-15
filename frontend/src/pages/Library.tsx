import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import CoverCard from "../components/CoverCard";

export default function Library() {
  const { data: series, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: api.library,
  });
  const { data: cont } = useQuery({
    queryKey: ["continue"],
    queryFn: api.continueReading,
  });

  return (
    <>
      <header className="topbar">
        <h1>Library</h1>
      </header>
      <div className="content">
        {isLoading && <div className="spinner" />}

        {cont && cont.length > 0 && (
          <>
            <div className="section-title">Continue reading</div>
            <div className="row-scroll">
              {cont.map((c) => (
                <Link
                  key={c.chapter.id}
                  to={`/read/${c.chapter.id}`}
                  className="cover-card"
                >
                  <div style={{ position: "relative" }}>
                    <img
                      className="cover"
                      src={c.series.cover_url || "/icon-512.png"}
                      alt={c.series.title}
                    />
                    <span className="type-tag">Ch. {c.chapter.number_label}</span>
                  </div>
                  <div className="title">{c.series.title}</div>
                </Link>
              ))}
            </div>
          </>
        )}

        {series && series.length > 0 ? (
          <>
            <div className="section-title">My series</div>
            <div className="grid">
              {series.map((s) => (
                <CoverCard
                  key={s.id}
                  to={`/series/${s.id}`}
                  title={s.title}
                  cover={s.cover_url}
                  type={s.type}
                  badge={s.unread_count || undefined}
                />
              ))}
            </div>
          </>
        ) : (
          !isLoading && (
            <div className="center-msg">
              <p>Your library is empty.</p>
              <Link to="/browse" className="btn" style={{ display: "inline-block" }}>
                Browse to add series
              </Link>
            </div>
          )
        )}
      </div>
    </>
  );
}
