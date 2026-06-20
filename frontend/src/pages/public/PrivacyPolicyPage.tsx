import PolicyLayout from "@/pages/public/components/PolicyLayout";

export default function PrivacyPolicyPage() {
  return (
    <PolicyLayout
      titleKey="legal:privacy.title"
      bodyKey="auth:register.agreementTextPrivacy"
      canonicalPath="/privacy-policy"
      eyebrowKey="legal:privacy.updated"
    />
  );
}
