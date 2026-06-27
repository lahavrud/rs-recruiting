import type { JobCreate, JobRequirementItem } from "@/types/jobs";
import { JOB_REQ_MIN_COUNT } from "@/types/jobs";

const MIN_REQUIREMENTS = JOB_REQ_MIN_COUNT;
const DEFAULT_SALARY_MIN = 10000;
const DEFAULT_SALARY_MAX = 13000;

export const EMPTY_FORM: JobCreate = {
  title: "",
  short_description: "",
  description: "",
  requirements: Array.from({ length: MIN_REQUIREMENTS }, () => ({ text: "" })),
  tags: [],
  location: "",
  salary_min: DEFAULT_SALARY_MIN,
  salary_max: DEFAULT_SALARY_MAX,
};

export function emptyRequirements(): JobRequirementItem[] {
  return Array.from({ length: MIN_REQUIREMENTS }, () => ({ text: "" }));
}
