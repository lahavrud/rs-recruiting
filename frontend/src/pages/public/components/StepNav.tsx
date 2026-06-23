import { useTranslation } from "react-i18next";

type Step = 1 | 2 | 3;
const TOTAL_STEPS = 3;

export default function StepNav({
  step,
  isSubmitting,
  isPrivacyAccepted,
  isTermsAccepted,
  onBack,
  onNext,
}: {
  step: Step;
  isSubmitting: boolean;
  isPrivacyAccepted: boolean;
  isTermsAccepted: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation('publicJobs');
  const isFinal = step === TOTAL_STEPS;
  // Sticky bottom-0 — works as sibling of content inside min-h-screen flex-col.
  // Naturally stops before the footer (sticky can't extend past its parent).
  return (
    <div className="sticky bottom-0 z-40 border-t border-white/8 bg-page/96 px-6 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={step === 1}
          className="rounded-sm border border-white/15 px-4 py-2 text-sm text-white/65 transition hover:border-white/35 hover:text-white/90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          {t("publicJobs:application.steps.back")}
        </button>
        {isFinal ? (
          // Distinct `key` from the Continue button — guarantees React mounts
          // a fresh DOM node rather than reusing the same <button> and just
          // flipping `type` from "button" to "submit". Without this, an
          // in-flight pointer sequence on the old Continue button could land
          // on the now-submit button after the step transition and trigger
          // an unwanted form submission.
          <button
            key="step-final-submit"
            type="submit"
            form="apply-form"
            disabled={isSubmitting || !isPrivacyAccepted || !isTermsAccepted}
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50 sm:px-8 sm:py-3 sm:text-base"
          >
            {isSubmitting
              ? t("publicJobs:application.submittingText")
              : t("publicJobs:application.submitText")}
          </button>
        ) : (
          <button
            key="step-continue"
            type="button"
            onClick={(e) => {
              // Defensive: block any onward propagation that could in theory
              // reach the form and trigger a submit handler in the same tick.
              e.preventDefault();
              e.stopPropagation();
              onNext();
            }}
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold sm:px-8 sm:py-3 sm:text-base"
          >
            {t("publicJobs:application.steps.continue")}
          </button>
        )}
      </div>
    </div>
  );
}
