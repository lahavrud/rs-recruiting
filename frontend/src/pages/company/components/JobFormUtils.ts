import type { JobCreate, JobRequirementItem } from "@/types/jobs";
import { JOB_REQ_MIN_COUNT } from "@/types/jobs";

const MIN_REQUIREMENTS = JOB_REQ_MIN_COUNT;

export const EMPTY_FORM: JobCreate = {
  title: "",
  short_description: "",
  description: "",
  requirements: Array.from({ length: MIN_REQUIREMENTS }, () => ({ text: "" })),
  tags: [],
  location: "",
  salary_min: 0,
  salary_max: 0,
};

export function emptyRequirements(): JobRequirementItem[] {
  return Array.from({ length: MIN_REQUIREMENTS }, () => ({ text: "" }));
}
