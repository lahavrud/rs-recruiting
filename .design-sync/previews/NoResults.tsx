import NoResults from "@/components/ui/NoResults";
import Button from "@/components/ui/Button";

export function NoResultsPreview() {
  return (
    <div className="space-y-6 bg-page p-8">
      <NoResults />
      <NoResults message="לא נמצאו מועמדים התואמים את הסינון שהגדרת." />
      <NoResults message="לא נמצאו תוצאות עבור החיפוש שלך.">
        <div className="mt-4">
          <Button variant="ghost" size="sm">נקה סינון</Button>
        </div>
      </NoResults>
    </div>
  );
}
