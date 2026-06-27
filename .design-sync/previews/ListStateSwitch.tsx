import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";

export function ListStateSwitchPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">טעינה</p>
        <ListStateSwitch
          isLoading
          loading={<MobileListSkeleton count={3} />}
          error={null}
          onRetry={() => {}}
          errorMessage="שגיאה בטעינת הנתונים"
          isEmpty={false}
          hasQuery={false}
          emptyEyebrow="רשימה"
          emptyHeadline="אין פריטים עדיין"
        >
          <p>content</p>
        </ListStateSwitch>
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">שגיאה</p>
        <ListStateSwitch
          isLoading={false}
          loading={null}
          error={new Error("500")}
          onRetry={() => {}}
          errorMessage="לא ניתן לטעון את הרשימה. אנא נסה שנית."
          isEmpty={false}
          hasQuery={false}
          emptyEyebrow="רשימה"
          emptyHeadline="אין פריטים"
        >
          <p>content</p>
        </ListStateSwitch>
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — אין תוצאות לחיפוש</p>
        <ListStateSwitch
          isLoading={false}
          loading={null}
          error={null}
          onRetry={() => {}}
          errorMessage=""
          isEmpty
          hasQuery
          emptyEyebrow="מועמדים"
          emptyHeadline="לא נמצאו מועמדים"
        >
          <p>content</p>
        </ListStateSwitch>
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — אין נתונים בכלל</p>
        <ListStateSwitch
          isLoading={false}
          loading={null}
          error={null}
          onRetry={() => {}}
          errorMessage=""
          isEmpty
          hasQuery={false}
          emptyEyebrow="מועמדים"
          emptyHeadline="לא נוספו מועמדים עדיין"
        >
          <p>content</p>
        </ListStateSwitch>
      </div>
    </div>
  );
}
