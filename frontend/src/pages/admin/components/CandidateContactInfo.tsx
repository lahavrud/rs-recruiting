import { useTranslation } from "react-i18next";

import ResumeButton from "@/components/ui/ResumeViewer";
import type { CandidateProfileRead } from "@/types/candidates";
import { sanitizeLinkedInUrl } from "@/utils/validators";

/** Contact/identity row: email, phone, LinkedIn, resume. */
export default function CandidateContactInfo({
  candidate: c,
}: {
  candidate: CandidateProfileRead;
}) {
  const { t } = useTranslation('admin');

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[15px]">
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
        />
      ) : (
        <span className="text-white/40">
          {t("admin:candidates.table.resume")}: {t("admin:candidates.noFile")}
        </span>
      )}
    </div>
  );
}
