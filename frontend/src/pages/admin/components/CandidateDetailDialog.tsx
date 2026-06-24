import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { MatchList, type MatchEntry } from "@/components/admin/MatchList";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Eyebrow from "@/components/ui/Eyebrow";
import ResumeButton from "@/components/ui/ResumeViewer";
import { getApplications } from "@/services/adminApplications";
import { getCandidateJobMatches } from "@/services/adminCandidates";
import type {
  ApplicationWithDetails,
  CandidateJobMatchRead,
  CandidateProfileRead,
} from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";
import { sanitizeLinkedInUrl } from "@/utils/validators";

interface DetailProps {
  candidate: CandidateProfileRead | null;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export default function CandidateDetailDialog({
  candidate,
  onClose,
  onEdit,
  onDelete,
}: DetailProps) {
  const { t } = useTranslation(["admin", "common"]);
  const [applications, setApplications] = useState<ApplicationWithDetails[] | null>(
    null,
  );
  const [hasAppsError, setHasAppsError] = useState(false);
  const [resumeViewerOpen, setResumeViewerOpen] = useState(false);

  useEffect(() => {
    // Reset state when the target candidate changes — the only sane way to
    // clear the previous candidate's applications before fetching the new
    // one's. setState-in-effect is intentional here.
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!candidate) {
      setApplications(null);
      setHasAppsError(false);
      return;
    }
    const ctrl = new AbortController();
    setApplications(null);
    setHasAppsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getApplications({ candidate_id: candidate.id, limit: 100 }, ctrl.signal)
      .then((page) => setApplications(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setHasAppsError(true);
      });
    return () => ctrl.abort();
  }, [candidate]);

  if (!candidate) return null;
  const c = candidate;

  return (
    <Dialog
      open={candidate != null}
      onOpenChange={(o) => !o && onClose()}
      title={c.full_name}
      description={c.email}
      size="lg"
      preventOutsideClose={resumeViewerOpen}
      footer={
        <>
          <Button variant="danger" onClick={onDelete}>
            {t("admin:candidates.deleteAction")}
          </Button>
          <Button onClick={onEdit}>{t("admin:candidates.editAction")}</Button>
        </>
      }
    >
      <CandidateDetailBody
        candidate={c}
        applications={applications}
        hasAppsError={hasAppsError}
        onLeavePage={onClose}
        onResumeViewerChange={setResumeViewerOpen}
      />
    </Dialog>
  );
}

/** Detail body shared by the desktop dialog and the mobile inline expansion. */
export function CandidateDetailBody({
  candidate,
  applications: appsProp,
  hasAppsError: hasAppsErrorProp,
  onLeavePage,
  onResumeViewerChange,
}: {
  candidate: CandidateProfileRead;
  applications?: ApplicationWithDetails[] | null;
  hasAppsError?: boolean;
  onLeavePage?: () => void;
  onResumeViewerChange?: (open: boolean) => void;
}) {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const c = candidate;

  // Self-fetch the applications list when the parent didn't pass one (mobile).
  const useLocal = appsProp === undefined;
  const [localApps, setLocalApps] = useState<ApplicationWithDetails[] | null>(null);
  const [hasLocalAppsError, setHasLocalAppsError] = useState(false);
  useEffect(() => {
    if (!useLocal) return;
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setLocalApps(null);
    setHasLocalAppsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getApplications({ candidate_id: candidate.id, limit: 100 }, ctrl.signal)
      .then((page) => setLocalApps(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setHasLocalAppsError(true);
      });
    return () => ctrl.abort();
  }, [candidate.id, useLocal]);
  const applications = useLocal ? localApps : appsProp;
  const hasAppsError = useLocal ? hasLocalAppsError : (hasAppsErrorProp ?? false);

  const [matches, setMatches] = useState<CandidateJobMatchRead[] | null>(null);
  const [hasMatchesError, setHasMatchesError] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setMatches(null);
    setHasMatchesError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getCandidateJobMatches(candidate.id, ctrl.signal)
      .then(setMatches)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setHasMatchesError(true);
      });
    return () => ctrl.abort();
  }, [candidate.id]);
  const matchEntries: MatchEntry[] | null =
    matches?.map((m) => ({
      key: m.job.id,
      name: m.job.title,
      meta: m.job.location,
      score: m.score,
      onClick: () => {
        onLeavePage?.();
        navigate(`/admin/jobs?job=${m.job.id}`);
      },
    })) ?? null;

  return (
    <div className="space-y-5 text-sm">
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <a
          href={`mailto:${c.email}?subject=${encodeURIComponent(t("admin:candidates.emailSubject", { name: c.full_name }))}`}
          className="text-copper/85 transition hover:text-copper hover:underline"
        >
          {c.email}
        </a>
        {c.phone && <span className="text-white/60">{c.phone}</span>}
        {c.linkedin_url && (
          <a
            href={sanitizeLinkedInUrl(c.linkedin_url)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-copper hover:text-gold"
          >
            LinkedIn ↗
          </a>
        )}
        {c.resume_path ? (
          <ResumeButton
            resumePath={c.resume_path}
            candidateName={c.full_name}
            label={t("admin:candidates.table.resume")}
            onOpenChange={onResumeViewerChange}
          />
        ) : (
          <span className="text-white/40">
            {t("admin:candidates.table.resume")}: {t("admin:candidates.noFile")}
          </span>
        )}
      </div>

      <div className="border-t border-white/8 pt-4">
        <Eyebrow>{t("admin:candidates.applicationsSection")}</Eyebrow>
        {hasAppsError ? (
          <p className="mt-3 text-xs text-danger">
            {t("admin:candidates.errors.applicationsLoadFailed")}
          </p>
        ) : applications == null ? (
          <p className="mt-3 text-xs text-white/35">{t("common:loading")}</p>
        ) : applications.length === 0 ? (
          <p className="mt-3 text-xs text-white/35">
            {t("admin:candidates.noApplications")}
          </p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {applications.map((a) => {
              const hasAppAnswers =
                a.service_concept ||
                a.salary_expectations ||
                a.strength ||
                a.growth_area;
              return (
                <li key={a.id} className="rounded-sm border border-white/6 bg-card">
                  <button
                    type="button"
                    onClick={() => {
                      onLeavePage?.();
                      navigate(`/admin/applications?candidate=${a.candidate_id}`, {
                        state: { autoOpen: a },
                      });
                    }}
                    className="flex w-full items-center justify-between px-3 py-2 transition hover:border-copper/25 hover:bg-card-raised"
                  >
                    <span className="text-white/80">{a.job.title}</span>
                    <span className="text-xs text-white/40">
                      {t(`admin:applications.statusLabels.${a.status}`)} ·{" "}
                      {formatDate(a.created_at)}
                    </span>
                  </button>
                  {hasAppAnswers && (
                    <dl className="grid grid-cols-1 gap-x-8 gap-y-1 border-t border-white/6 px-3 py-2 text-xs sm:grid-cols-2">
                      {a.service_concept && (
                        <>
                          <dt className="text-white/35">
                            {t("admin:candidates.details.serviceConcept")}
                          </dt>
                          <dd className="text-white/60">{a.service_concept}</dd>
                        </>
                      )}
                      {a.salary_expectations && (
                        <>
                          <dt className="text-white/35">
                            {t("admin:candidates.details.salaryExpectations")}
                          </dt>
                          <dd className="text-white/60">{a.salary_expectations}</dd>
                        </>
                      )}
                      {a.strength && (
                        <>
                          <dt className="text-white/35">
                            {t("admin:candidates.details.strength")}
                          </dt>
                          <dd className="text-white/60">{a.strength}</dd>
                        </>
                      )}
                      {a.growth_area && (
                        <>
                          <dt className="text-white/35">
                            {t("admin:candidates.details.weakness")}
                          </dt>
                          <dd className="text-white/60">{a.growth_area}</dd>
                        </>
                      )}
                    </dl>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-white/8 pt-4">
        <Eyebrow>{t("admin:candidates.matchesSection")}</Eyebrow>
        <MatchList
          entries={matchEntries}
          hasError={hasMatchesError}
          emptyMessage={t("admin:candidates.noMatches")}
          errorMessage={t("admin:candidates.matchesLoadError")}
        />
      </div>
    </div>
  );
}
