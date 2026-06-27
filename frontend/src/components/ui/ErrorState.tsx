import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * Error placeholder with optional retry button. Falls back to a generic
 * Hebrew message when the caller doesn't pass a specific one.
 */
export default function ErrorState({
  message,
  onRetry,
  className = "",
}: ErrorStateProps) {
  const { t } = useTranslation('common');
  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center rounded-xl border border-danger/30 bg-card px-6 py-16 text-center ${className}`}
    >
      <Eyebrow color="danger">{t("common:errorEyebrow")}</Eyebrow>
      <div className="mt-3 h-px w-8 bg-danger/40" />
      <p className="mt-5 max-w-md text-sm text-white/70">
        {message ?? t("common:genericError")}
      </p>
      {onRetry && (
        <Button variant="ghost" size="md" className="mt-6" onClick={onRetry}>
          {t("common:retry")}
        </Button>
      )}
    </div>
  );
}
