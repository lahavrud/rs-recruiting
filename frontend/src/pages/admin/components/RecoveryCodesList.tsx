import { useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";

const COPIED_RESET_MS = 2000;

/** MFA recovery codes, shown once, with copy and download (#1177). */
export default function RecoveryCodesList({ codes }: { codes: string[] }) {
  const { t } = useTranslation("admin");
  const [isCopied, setIsCopied] = useState(false);
  const text = codes.join("\n");

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), COPIED_RESET_MS);
    } catch {
      // Clipboard blocked (permissions / insecure context): download still works.
    }
  }

  function handleDownload() {
    const url = URL.createObjectURL(new Blob([`${text}\n`], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "rs-recruiting-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-3">
      <ul
        dir="ltr"
        className="grid grid-cols-2 gap-2 rounded-lg border border-white/10 bg-well p-4 font-mono text-sm text-white/85"
        data-testid="recovery-codes"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={handleCopy}>
          {isCopied ? t("admin:mfa.setup.done.copied") : t("admin:mfa.setup.done.copy")}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={handleDownload}>
          {t("admin:mfa.setup.done.download")}
        </Button>
      </div>
    </div>
  );
}
