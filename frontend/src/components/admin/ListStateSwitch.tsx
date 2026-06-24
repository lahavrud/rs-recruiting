import type { ReactNode } from "react";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import NoResults from "@/components/ui/NoResults";

interface ListStateSwitchProps {
  isLoading: boolean;
  loading: ReactNode;
  error: unknown;
  onRetry: () => void;
  errorMessage: string;
  isEmpty: boolean;
  hasQuery: boolean;
  emptyEyebrow: string;
  emptyHeadline: string;
  children: ReactNode;
}

/** Loading/error/empty/no-results switch shared by every admin list+rail view. Renders `children` once data is present. */
export default function ListStateSwitch({
  isLoading,
  loading,
  error,
  onRetry,
  errorMessage,
  isEmpty,
  hasQuery,
  emptyEyebrow,
  emptyHeadline,
  children,
}: ListStateSwitchProps) {
  if (isLoading) return <>{loading}</>;
  if (error) return <ErrorState message={errorMessage} onRetry={onRetry} />;
  if (isEmpty) {
    return hasQuery ? <NoResults /> : <EmptyState eyebrow={emptyEyebrow} headline={emptyHeadline} />;
  }
  return <>{children}</>;
}
