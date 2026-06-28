import { useTranslation } from "react-i18next";

// Each document is one translation string split into blocks by a blank line.
// A block whose first line is a numbered heading ("1. ...") renders that line
// as a section heading; the remaining lines render as the body, with single
// newlines preserved so the retention bullet list keeps its line breaks.
const SECTION_HEADING_RE = /^\d+\.\s/;

export default function LegalProse({ bodyKey }: { bodyKey: string }) {
  const { t } = useTranslation(["legal", "auth"]);
  return (
    <>
      {t(bodyKey)
        .split("\n\n")
        .map((block, i) => {
          const [first, ...rest] = block.split("\n");
          const body = rest.join("\n");
          const isSection = SECTION_HEADING_RE.test(first);
          return (
            <section key={i} className="space-y-2">
              {isSection ? (
                <h2 className="text-sm font-semibold text-white/80">{first}</h2>
              ) : (
                <p className="text-sm leading-7 text-white/55">{first}</p>
              )}
              {body && (
                <p className="text-sm leading-7 whitespace-pre-line text-white/55">
                  {body}
                </p>
              )}
            </section>
          );
        })}
    </>
  );
}
