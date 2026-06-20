import PolicyLayout from "@/pages/public/components/PolicyLayout";

export default function TermsPage() {
  return (
    <PolicyLayout
      titleKey="legal:terms.title"
      bodyKey="auth:register.agreementTextSiteTerms"
      canonicalPath="/terms"
      eyebrowKey="legal:terms.updated"
    />
  );
}
