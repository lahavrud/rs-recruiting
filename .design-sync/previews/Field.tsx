import Field from "@/components/ui/Field";

export function FieldPreview() {
  return (
    <div className="space-y-6 bg-page p-8 max-w-md">
      <Field label="שם מלא" required>
        <input
          className="w-full rounded-sm border border-white/15 bg-well px-3 py-2 text-sm text-white/85 focus:border-copper/50 focus:outline-none"
          defaultValue="דנה לוי"
        />
      </Field>
      <Field label="דואר אלקטרוני" id="email" optional hint="נשמר בסודיות מוחלטת">
        <input
          id="email"
          type="email"
          className="w-full rounded-sm border border-white/15 bg-well px-3 py-2 text-sm text-white/85 focus:border-copper/50 focus:outline-none"
          defaultValue="dana@example.com"
        />
      </Field>
      <Field label="טלפון נייד" id="phone" error="יש להזין מספר ישראלי תקין (05X-XXXXXXX)">
        <input
          id="phone"
          className="w-full rounded-sm border border-danger bg-well px-3 py-2 text-sm text-white/85 focus:outline-none"
          defaultValue="123"
        />
      </Field>
      <Field label="תיאור קצר" id="bio">
        <textarea
          id="bio"
          rows={3}
          className="w-full resize-none rounded-sm border border-white/15 bg-well px-3 py-2 text-sm text-white/85 focus:border-copper/50 focus:outline-none"
          defaultValue="מהנדסת בניין מנוסה עם רקע בניהול פרויקטים."
        />
      </Field>
    </div>
  );
}
