import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";

type Step = 1 | 2 | 3;
const TOTAL_STEPS = 3;

export default function Stepper({
  step,
  maxStep,
  onJump,
}: {
  step: Step;
  maxStep: Step;
  onJump: (s: Step) => void;
}) {
  const { t } = useTranslation('publicJobs');
  const labels: [Step, string][] = [
    [1, t("publicJobs:application.steps.identity")],
    [2, t("publicJobs:application.steps.resume")],
    [3, t("publicJobs:application.steps.questions")],
  ];
  return (
    <div>
      <Eyebrow className="mb-3">
        {t("publicJobs:application.steps.indicator", {
          current: step,
          total: TOTAL_STEPS,
        })}
      </Eyebrow>
      {/* Step 1 sits at the visual start of the row — in RTL that means
          the right side. Hebrew labels render naturally. */}
      <ol className="flex items-center gap-2">
        {labels.map(([n, label], i) => {
          const isActive = n === step;
          const isComplete = n < step;
          const isReachable = n <= maxStep;
          return (
            <li
              key={n}
              className="flex flex-1 items-center gap-2 first:ms-0 last:me-0"
            >
              <button
                type="button"
                disabled={!isReachable}
                onClick={() => onJump(n)}
                aria-current={isActive ? "step" : undefined}
                className={[
                  "group flex flex-1 items-center gap-2 rounded-full border px-2.5 py-1.5 text-xs transition",
                  isActive
                    ? "border-copper bg-copper/15 text-white"
                    : isComplete
                      ? "border-copper/30 text-white/70 hover:border-copper/60 hover:bg-copper/10"
                      : "border-white/10 text-white/35",
                  !isReachable && "cursor-default",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span
                  className={[
                    "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                    isActive
                      ? "bg-copper text-white"
                      : isComplete
                        ? "bg-copper/80 text-white"
                        : "bg-white/8 text-white/50",
                  ].join(" ")}
                >
                  {isComplete ? (
                    <svg
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      className="size-3"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M14.78 4.22a.75.75 0 0 1 0 1.06l-7 7a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06L7.25 10.69l6.47-6.47a.75.75 0 0 1 1.06 0Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    n
                  )}
                </span>
                <span className="truncate font-medium">{label}</span>
              </button>
              {i < labels.length - 1 && (
                <span
                  aria-hidden="true"
                  className={`h-px flex-1 transition-colors ${
                    isComplete ? "bg-copper/40" : "bg-white/8"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
