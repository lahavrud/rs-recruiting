import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";

interface Props {
  contractOpen: boolean;
  termsOpen: boolean;
  privacyOpen: boolean;
  onCloseContract: () => void;
  onCloseTerms: () => void;
  onClosePrivacy: () => void;
  onAcceptTerms: () => void;
  onAcceptPrivacy: () => void;
}

function ModalShell({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  const { t } = useTranslation('auth');
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
          <h2 className="text-sm font-medium text-white/80">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-white/40 transition hover:text-white/70"
            aria-label={t("auth:register.agreementClose")}
          >
            ✕
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
          {children}
        </div>
        <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">{footer}</div>
      </div>
    </div>
  );
}

export default function RegisterModals({
  contractOpen,
  termsOpen,
  privacyOpen,
  onCloseContract,
  onCloseTerms,
  onClosePrivacy,
  onAcceptTerms,
  onAcceptPrivacy,
}: Props) {
  const { t } = useTranslation(['auth', 'legal']);

  return (
    <>
      {contractOpen && (
        <ModalShell
          title={t("auth:register.agreementSectionService")}
          onClose={onCloseContract}
          footer={
            <Button type="button" size="lg" onClick={onCloseContract}>
              {t("auth:register.agreementClose")}
            </Button>
          }
        >
          {t("auth:register.agreementTextService")
            .split("\n\n")
            .map((para, i) => (
              <p key={i} className="text-sm leading-7 text-white/55">
                {para}
              </p>
            ))}
        </ModalShell>
      )}

      {termsOpen && (
        <ModalShell
          title={t("auth:register.agreementSectionSiteTerms")}
          onClose={onCloseTerms}
          footer={
            <Button type="button" size="lg" onClick={onAcceptTerms}>
              {t("auth:register.termsAcceptButton")}
            </Button>
          }
        >
          {t("legal:terms.body")
            .split("\n\n")
            .map((para, i) => (
              <p key={i} className="text-sm leading-7 text-white/55">
                {para}
              </p>
            ))}
        </ModalShell>
      )}

      {privacyOpen && (
        <ModalShell
          title={t("auth:register.agreementSectionPrivacy")}
          onClose={onClosePrivacy}
          footer={
            <Button type="button" size="lg" onClick={onAcceptPrivacy}>
              {t("auth:register.privacyAcceptButton")}
            </Button>
          }
        >
          {t("legal:privacy.body")
            .split("\n\n")
            .map((para, i) => (
              <p key={i} className="text-sm leading-7 text-white/55">
                {para}
              </p>
            ))}
        </ModalShell>
      )}
    </>
  );
}
