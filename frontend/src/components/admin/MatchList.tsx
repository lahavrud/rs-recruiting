import { useTranslation } from "react-i18next";

export interface MatchEntry {
  key: number;
  name: string;
  meta: string;
  score: number;
  onClick: () => void;
}

/** Radial gauge for a single match score (cosine similarity, 0–1). */
function RingGauge({ score }: { score: number }) {
  const r = 15;
  const c = 2 * Math.PI * r;
  const strokeCls =
    score >= 0.75 ? "stroke-success" : score >= 0.55 ? "stroke-copper" : "stroke-white/30";
  return (
    <svg viewBox="0 0 36 36" className="size-9 shrink-0 -rotate-90" aria-hidden="true">
      <circle cx="18" cy="18" r={r} className="fill-none stroke-well" strokeWidth="3" />
      <circle
        cx="18"
        cy="18"
        r={r}
        className={`fill-none ${strokeCls}`}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={`${c * score} ${c}`}
      />
      <text
        x="18"
        y="19"
        textAnchor="middle"
        dominantBaseline="middle"
        className="rotate-90 fill-white/80 text-[9px] font-medium"
        style={{ transformOrigin: "18px 18px" }}
      >
        {Math.round(score * 100)}
      </text>
    </svg>
  );
}

function MatchRow({ name, meta, score, onClick }: Omit<MatchEntry, "key">) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-sm border border-white/6 bg-card px-3 py-2.5 text-start transition hover:border-copper/25 hover:bg-card-raised"
    >
      <RingGauge score={score} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm text-white/85">{name}</span>
        <span className="block truncate text-xs text-white/40">{meta}</span>
      </span>
    </button>
  );
}

/** Ranked match list: loading/error/empty states + ring-gauge rows. Order is the rank. */
export function MatchList({
  entries,
  hasError,
  emptyMessage,
  errorMessage,
}: {
  entries: MatchEntry[] | null;
  hasError: boolean;
  emptyMessage: string;
  errorMessage: string;
}) {
  const { t } = useTranslation("common");
  if (hasError) return <p className="mt-3 text-xs text-danger">{errorMessage}</p>;
  if (entries == null) return <p className="mt-3 text-xs text-white/35">{t("loading")}</p>;
  if (entries.length === 0) {
    return <p className="mt-3 text-xs text-white/35">{emptyMessage}</p>;
  }
  return (
    <ul className="mt-3 space-y-1.5">
      {entries.map((e) => (
        <li key={e.key}>
          <MatchRow name={e.name} meta={e.meta} score={e.score} onClick={e.onClick} />
        </li>
      ))}
    </ul>
  );
}
