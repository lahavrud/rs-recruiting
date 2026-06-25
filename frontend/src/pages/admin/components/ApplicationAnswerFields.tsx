import { useTranslation } from "react-i18next";

import type { ApplicationWithDetails } from "@/types/candidates";

/** Service-concept/salary/strength/growth-area answers — shared by the legacy detail dialog and the record header. */
export default function ApplicationAnswerFields({ app }: { app: ApplicationWithDetails }) {
  const { t } = useTranslation("admin");

  const entries: { key: string; label: string; value: string }[] = [
    app.service_concept && {
      key: "serviceConcept",
      label: t("admin:applications.details.serviceConcept"),
      value: app.service_concept,
    },
    app.salary_expectations && {
      key: "salaryExpectations",
      label: t("admin:applications.details.salaryExpectations"),
      value: app.salary_expectations,
    },
    app.strength && {
      key: "strength",
      label: t("admin:applications.details.strength"),
      value: app.strength,
    },
    app.growth_area && {
      key: "growthArea",
      label: t("admin:applications.details.weakness"),
      value: app.growth_area,
    },
  ].filter((e): e is { key: string; label: string; value: string } => Boolean(e));

  if (entries.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {entries.map((entry) => (
        <div key={entry.key} className="rounded-lg border border-white/8 bg-well/40 p-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/35">
            {entry.label}
          </p>
          <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap text-white/75">
            {entry.value}
          </p>
        </div>
      ))}
    </div>
  );
}
