import { useTranslation } from "react-i18next";
import {
  AnswerBlock,
  NoteField,
  RevisitBanner,
} from "./TriageComponents";
import { IconDocument } from "./TriageIcons";
import { formatTriageDate, type Decision } from "./triageTypes";
import type { TriageItem } from "./useTriageQueue";
import { sanitizeLinkedInUrl } from "@/utils/validators";

/**
 * One candidate's content card. Used inside the carousel — rendered for the
 * current candidate and its prev/next siblings simultaneously so the slide
 * animation shows real content sliding in.
 *
 * `active=false` makes the card visually present but interaction-inert: no
 * tabstops, disabled buttons, links without hrefs. This prevents tab-focus
 * from leaking into off-screen cards.
 */
export function CandidateCard({
  app,
  decision,
  active,
  onOpenResume,
  onUndoDecision,
}: {
  app: TriageItem;
  decision: Decision | null;
  active: boolean;
  onOpenResume: () => void;
  onUndoDecision: () => void;
}) {
  const { t } = useTranslation('admin');
  const hasResume = app.candidate.resume_path != null;
  return (
    <div
      className="h-full w-full shrink-0 overflow-y-auto px-5 py-6 sm:px-8 sm:py-8"
      aria-hidden={!active}
    >
      <div className="mx-auto w-full max-w-2xl space-y-8">
        {decision && (
          <RevisitBanner decision={decision} onUndo={onUndoDecision} />
        )}

        {/* Identity + resume button. On desktop the button sits inline at
            the end of the row, vertically centered against the whole details
            block (not just the name) so it reads as a sibling of the entire
            identity. On mobile it stacks below, centered. */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between lg:gap-6">
          <header className="min-w-0 flex-1">
            <h1 className="text-2xl font-light text-white sm:text-3xl">
              {app.candidate.full_name}
            </h1>
            <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-white/55">
              <span>{app.job.title}</span>
              <span className="text-white/20">·</span>
              <span className="text-copper">{app.companyName}</span>
              <span className="text-white/20">·</span>
              <span>{app.job.location}</span>
              <span className="text-white/20">·</span>
              <span className="text-white/40">{formatTriageDate(app.created_at)}</span>
            </p>

            <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <a
                href={active ? `mailto:${app.candidate.email}` : undefined}
                className="text-white/65 hover:text-copper"
                tabIndex={active ? 0 : -1}
              >
                {app.candidate.email}
              </a>
              <a
                href={active ? `tel:${app.candidate.phone}` : undefined}
                className="text-white/65 hover:text-copper"
                tabIndex={active ? 0 : -1}
              >
                {app.candidate.phone}
              </a>
              {app.candidate.linkedin_url && (
                <a
                  href={active ? sanitizeLinkedInUrl(app.candidate.linkedin_url) : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-copper hover:text-gold"
                  tabIndex={active ? 0 : -1}
                >
                  LinkedIn ↗
                </a>
              )}
            </p>
          </header>

          {hasResume && (
            <div className="flex justify-center lg:shrink-0 lg:justify-end">
              <button
                type="button"
                onClick={onOpenResume}
                disabled={!active}
                className="inline-flex items-center gap-2 rounded-sm border border-white/10 bg-card/40 px-4 py-2 text-sm text-white/75 transition hover:border-copper/40 hover:bg-card/70 hover:text-white disabled:cursor-default disabled:opacity-60"
                tabIndex={active ? 0 : -1}
              >
                <IconDocument />
                <span>{t("admin:applications.triage.openResume")}</span>
              </button>
            </div>
          )}
        </div>

        {/* Application answers — all optional per the API; skip empty ones */}
        <div className="space-y-6">
          {app.service_concept && (
            <AnswerBlock
              label={t("admin:applications.details.serviceConcept")}
              body={app.service_concept}
            />
          )}
          {(app.salary_expectations || app.strength) && (
            <div className="grid gap-6 sm:grid-cols-2">
              {app.salary_expectations && (
                <AnswerBlock
                  label={t("admin:applications.details.salaryExpectations")}
                  body={app.salary_expectations}
                  compact
                />
              )}
              {app.strength && (
                <AnswerBlock
                  label={t("admin:applications.details.strength")}
                  body={app.strength}
                  compact
                />
              )}
            </div>
          )}
          {app.growth_area && (
            <AnswerBlock
              label={t("admin:applications.details.weakness")}
              body={app.growth_area}
            />
          )}
        </div>

        <div>
          <p className="mb-1.5 text-xs text-white/35">{t("admin:applications.triage.noteLabel")}</p>
          <NoteField key={app.id} initial={app.admin_notes ?? ""} />
        </div>
      </div>
    </div>
  );
}
