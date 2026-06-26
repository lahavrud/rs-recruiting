/** Compact AI match score badge — copper for good, dimmed for weak, success for excellent. */
export default function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.75
      ? "bg-success/10 text-success"
      : score >= 0.55
        ? "bg-copper/10 text-copper"
        : "bg-white/6 text-white/35";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold tabular-nums ${cls}`}
      title={`ציון התאמה: ${pct}%`}
    >
      {pct}%
    </span>
  );
}
