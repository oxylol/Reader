import { Link } from "react-router-dom";

interface Props {
  to?: string;
  title: string;
  cover: string;
  type?: string;
  badge?: number;
  onClick?: () => void;
}

export default function CoverCard({ to, title, cover, type, badge, onClick }: Props) {
  const inner = (
    <>
      <div style={{ position: "relative" }}>
        <img
          className="cover"
          src={cover || "/icon-512.png"}
          alt={title}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src = "/icon-512.png";
          }}
        />
        {badge ? <span className="badge">{badge}</span> : null}
        {type && type !== "unknown" ? (
          <span className="type-tag">{type}</span>
        ) : null}
      </div>
      <div className="title">{title}</div>
    </>
  );
  if (to) {
    return (
      <Link className="cover-card" to={to}>
        {inner}
      </Link>
    );
  }
  return (
    <div className="cover-card" onClick={onClick} role="button">
      {inner}
    </div>
  );
}
