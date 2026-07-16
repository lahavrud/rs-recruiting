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
  /** Optional sub-line for the empty state — e.g. why rows might be filtered out. */
  emptyDescription?: string;
  /** Optional CTA rendered in both the empty and no-results branches. */
  emptyAction?: ReactNode;
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
  emptyDescription,
  emptyAction,
  children,
}: ListStateSwitchProps) {
  if (isLoading) return <>{loading}</>;
  if (error) return <ErrorState message={errorMessage} onRetry={onRetry} />;
  if (isEmpty) {
    return hasQuery ? (
      <NoResults>{emptyAction}</NoResults>
    ) : (
      <EmptyState
        eyebrow={emptyEyebrow}
        headline={emptyHeadline}
        description={emptyDescription}
        action={emptyAction}
      />
    );
  }
  return <>{children}</>;
}
