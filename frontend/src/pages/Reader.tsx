import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { ChapterInfo, Prefs } from "../lib/types";

type Mode = "paged" | "webtoon";

function resolveMode(info: ChapterInfo, prefs?: Prefs): Mode {
  const pref = prefs?.reading_mode ?? "auto";
  if (pref === "paged" || pref === "webtoon") return pref;
  // auto: series default, else by type
  if (info.default_mode === "paged" || info.default_mode === "webtoon")
    return info.default_mode;
  return info.series_type === "manhwa" || info.series_type === "manhua"
    ? "webtoon"
    : "paged";
}

export default function Reader() {
  const { chapterId } = useParams();
  const id = Number(chapterId);
  const nav = useNavigate();

  const { data: info } = useQuery({
    queryKey: ["chapterInfo", id],
    queryFn: () => api.chapterInfo(id),
  });
  const { data: prefs } = useQuery({ queryKey: ["prefs"], queryFn: api.prefs });

  const [chrome, setChrome] = useState(false);
  const [mode, setMode] = useState<Mode>("paged");
  const [rtl, setRtl] = useState(false);
  const [fit, setFit] = useState<"width" | "height" | "original">("width");

  useEffect(() => {
    if (info && prefs) {
      setMode(resolveMode(info, prefs));
      setRtl(prefs.rtl);
      setFit((prefs.fit as "width" | "height" | "original") ?? "width");
    }
  }, [info, prefs]);

  if (!info) {
    return (
      <div className="reader">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="reader">
      <ReaderChrome
        info={info}
        chrome={chrome}
        mode={mode}
        rtl={rtl}
        fit={fit}
        setMode={setMode}
        setRtl={setRtl}
        setFit={setFit}
        onClose={() => nav(`/series/${info.series_id}`)}
        onJump={(cid) => nav(`/read/${cid}`)}
      />
      {mode === "paged" ? (
        <PagedReader
          key={id}
          info={info}
          rtl={rtl}
          fit={fit}
          toggleChrome={() => setChrome((c) => !c)}
          onNext={() => info.next_chapter_id && nav(`/read/${info.next_chapter_id}`)}
          onPrev={() => info.prev_chapter_id && nav(`/read/${info.prev_chapter_id}`)}
        />
      ) : (
        <WebtoonReader
          key={id}
          info={info}
          fit={fit}
          toggleChrome={() => setChrome((c) => !c)}
          onNext={() => info.next_chapter_id && nav(`/read/${info.next_chapter_id}`)}
        />
      )}
    </div>
  );
}

function ReaderChrome({
  info,
  chrome,
  mode,
  rtl,
  fit,
  setMode,
  setRtl,
  setFit,
  onClose,
  onJump,
}: {
  info: ChapterInfo;
  chrome: boolean;
  mode: Mode;
  rtl: boolean;
  fit: string;
  setMode: (m: Mode) => void;
  setRtl: (v: boolean) => void;
  setFit: (v: "width" | "height" | "original") => void;
  onClose: () => void;
  onJump: (id: number) => void;
}) {
  const [showJump, setShowJump] = useState(false);
  const { data: chapters } = useQuery({
    queryKey: ["chapters", info.series_id],
    queryFn: () => api.chapters(info.series_id),
    enabled: showJump,
  });

  return (
    <>
      <div className={`reader-chrome top ${chrome ? "" : "hidden"}`}>
        <button className="icon-btn" onClick={onClose}>←</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {info.series_title}
          </div>
          <div style={{ fontSize: 12, color: "#aaa" }}>
            Ch. {info.chapter.number_label || info.chapter.number}
          </div>
        </div>
        <button className="icon-btn" onClick={() => setShowJump((v) => !v)}>☰</button>
      </div>

      {showJump && chrome && (
        <div
          style={{
            position: "absolute",
            top: 60,
            right: 10,
            maxHeight: "60vh",
            overflowY: "auto",
            background: "#15151c",
            border: "1px solid #26262f",
            borderRadius: 12,
            zIndex: 20,
            width: 260,
            padding: 6,
          }}
        >
          {chapters?.filter((c) => c.downloaded).map((c) => (
            <div
              key={c.id}
              className="chapter-item"
              style={{ background: c.id === info.chapter.id ? "#2a2440" : undefined }}
              onClick={() => {
                setShowJump(false);
                onJump(c.id);
              }}
            >
              <span className="num">Ch. {c.number_label || c.number}</span>
            </div>
          ))}
        </div>
      )}

      <div className={`reader-chrome bottom ${chrome ? "" : "hidden"}`}>
        <div className="reader-row" style={{ justifyContent: "space-between" }}>
          <button
            className="btn secondary"
            disabled={!info.prev_chapter_id}
            onClick={() => info.prev_chapter_id && onJump(info.prev_chapter_id)}
          >
            ‹ Prev
          </button>
          <div className="seg">
            <button className={mode === "paged" ? "on" : ""} onClick={() => setMode("paged")}>
              Paged
            </button>
            <button className={mode === "webtoon" ? "on" : ""} onClick={() => setMode("webtoon")}>
              Webtoon
            </button>
          </div>
          <button
            className="btn secondary"
            disabled={!info.next_chapter_id}
            onClick={() => info.next_chapter_id && onJump(info.next_chapter_id)}
          >
            Next ›
          </button>
        </div>
        <div className="reader-row" style={{ justifyContent: "space-between" }}>
          <div className="seg">
            <button className={fit === "width" ? "on" : ""} onClick={() => setFit("width")}>
              Width
            </button>
            <button className={fit === "height" ? "on" : ""} onClick={() => setFit("height")}>
              Height
            </button>
            <button className={fit === "original" ? "on" : ""} onClick={() => setFit("original")}>
              Original
            </button>
          </div>
          {mode === "paged" && (
            <button className={`chip ${rtl ? "on" : ""}`} onClick={() => setRtl(!rtl)}>
              {rtl ? "RTL" : "LTR"}
            </button>
          )}
        </div>
      </div>
    </>
  );
}

function PagedReader({
  info,
  rtl,
  fit,
  toggleChrome,
  onNext,
  onPrev,
}: {
  info: ChapterInfo;
  rtl: boolean;
  fit: string;
  toggleChrome: () => void;
  onNext: () => void;
  onPrev: () => void;
}) {
  const total = info.page_count;
  const [page, setPage] = useState(info.chapter.current_page || 0);

  const go = useCallback(
    (dir: 1 | -1) => {
      setPage((p) => {
        const np = p + dir;
        if (np < 0) {
          onPrev();
          return p;
        }
        if (np >= total) {
          onNext();
          return p;
        }
        return np;
      });
    },
    [total, onNext, onPrev],
  );

  // logical prev/next mapped to screen sides depending on RTL
  const left = () => (rtl ? go(1) : go(-1));
  const right = () => (rtl ? go(-1) : go(1));

  // keyboard
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") right();
      else if (e.key === "ArrowLeft") left();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  // save progress (debounced via effect)
  useEffect(() => {
    const completed = page >= total - 1;
    const t = setTimeout(
      () => api.saveProgress(info.chapter.id, page, 0, completed).catch(() => {}),
      400,
    );
    return () => clearTimeout(t);
  }, [page, total, info.chapter.id]);

  // preload neighbors
  useEffect(() => {
    [page + 1, page + 2].forEach((p) => {
      if (p < total) {
        const img = new Image();
        img.src = api.pageUrl(info.chapter.id, p);
      }
    });
  }, [page, total, info.chapter.id]);

  return (
    <>
      <div className={`reader-paged fit-${fit}`}>
        <img
          src={api.pageUrl(info.chapter.id, page)}
          alt={`page ${page + 1}`}
          draggable={false}
        />
      </div>
      <div className="tap-zones">
        <div onClick={left} />
        <div onClick={toggleChrome} />
        <div onClick={right} />
      </div>
      <div className="page-indicator">
        {page + 1} / {total}
      </div>
    </>
  );
}

function WebtoonReader({
  info,
  fit,
  toggleChrome,
  onNext,
}: {
  info: ChapterInfo;
  fit: string;
  toggleChrome: () => void;
  onNext: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const total = info.page_count;
  const firedNext = useRef(false);

  // restore scroll once
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const restore = () => {
      if (info.chapter.current_page > 0 && total > 0) {
        el.scrollTop = (info.chapter.current_page / total) * el.scrollHeight;
      }
    };
    const t = setTimeout(restore, 100);
    return () => clearTimeout(t);
  }, [info.chapter.current_page, total]);

  const onScroll = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const frac = (el.scrollTop + el.clientHeight) / el.scrollHeight;
    const page = Math.min(total - 1, Math.floor((el.scrollTop / el.scrollHeight) * total));
    const completed = frac > 0.98;
    api.saveProgress(info.chapter.id, page, frac, completed).catch(() => {});
    if (completed && !firedNext.current) {
      firedNext.current = true;
      onNext();
    }
  }, [total, info.chapter.id, onNext]);

  // throttle scroll saves
  const lastSave = useRef(0);
  const handleScroll = () => {
    const now = Date.now();
    if (now - lastSave.current > 800) {
      lastSave.current = now;
      onScroll();
    }
  };

  return (
    <div
      className={`reader-webtoon fit-${fit}`}
      ref={ref}
      onScroll={handleScroll}
      onClick={toggleChrome}
    >
      {Array.from({ length: total }).map((_, i) => (
        <img
          key={i}
          src={api.pageUrl(info.chapter.id, i)}
          alt={`page ${i + 1}`}
          loading={i < 3 ? "eager" : "lazy"}
          draggable={false}
        />
      ))}
    </div>
  );
}
