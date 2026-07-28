import { useTranslation } from "react-i18next";

import ResumeButton from "@/components/ui/ResumeViewer";
import type { CandidateAdminRead } from "@/types/candidates";
import { sanitizeLinkedInUrl } from "@/utils/validators";

/** Contact/identity row: email, phone, LinkedIn, resume.
 *
 * A tombstoned candidate has no contact data left — the address on the row is the
 * synthetic `deleted-<id>@deleted`, which resolves nowhere. Render it as plain text
 * so it can't be mistaken for (or used as) a working mailto.
 */
export default function CandidateContactInfo({
  candidate: c,
}: {
  candidate: Pick<
    CandidateAdminRead,
    "email" | "full_name" | "phone" | "linkedin_url" | "resume_path" | "is_deleted"
  >;
}) {
  const { t } = useTranslation("admin");

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[15px]">
      {c.is_deleted ? (
        <span className="text-white/40">{t("admin:candidates.deletedSubtitle")}</span>
      ) : (
        <a
          href={`mailto:${c.email}?subject=${encodeURIComponent(t("admin:candidates.emailSubject", { name: c.full_name }))}`}
          className="text-copper/85 transition hover:text-copper hover:underline"
        >
          {c.email}
        </a>
      )}
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
        />
      ) : (
        <span className="text-white/40">
          {/* "not uploaded" would be a lie for a tombstone: it was uploaded, then purged. */}
          {c.is_deleted
            ? t("admin:candidates.resumePurged")
            : `${t("admin:candidates.table.resume")}: ${t("admin:candidates.noFile")}`}
        </span>
      )}
    </div>
  );
}
