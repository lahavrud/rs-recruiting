export const SCORE_HIGH = 80;
export const SCORE_MID = 65;
export const PCT_MULTIPLIER = 100;

export function scoreBarColor(pct: number): string {
  return pct >= SCORE_HIGH ? "bg-success" : pct >= SCORE_MID ? "bg-copper" : "bg-warning";
}
