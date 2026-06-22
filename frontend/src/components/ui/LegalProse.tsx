import { useTranslation } from "react-i18next";

export default function LegalProse({ bodyKey }: { bodyKey: string }) {
  const { t } = useTranslation(["legal", "auth"]);
  return (
    <>
      {t(bodyKey)
        .split("\n\n")
        .map((para, i) => (
          <p key={i} className="text-sm leading-7 text-white/55">
            {para}
          </p>
        ))}
    </>
  );
}
