import type { JobPublicRead } from "@/types/jobs";
import { SALARY_FALLBACK } from "@/types/jobs";

export const SALARY_STEP = 500;

export interface SalaryBounds {
  min: number;
  max: number;
}

export function getSalaryBounds(jobs: JobPublicRead[]): SalaryBounds {
  let lo = Infinity;
  let hi = -Infinity;
  for (const j of jobs) {
    if (j.salary_min != null) lo = Math.min(lo, j.salary_min);
    if (j.salary_max != null) hi = Math.max(hi, j.salary_max);
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi) {
    return SALARY_FALLBACK;
  }
  return {
    min: Math.floor(lo / SALARY_STEP) * SALARY_STEP,
    max: Math.ceil(hi / SALARY_STEP) * SALARY_STEP,
  };
}

export function formatSalaryShort(n: number): string {
  return `${n.toLocaleString("he-IL")} ₪`;
}
