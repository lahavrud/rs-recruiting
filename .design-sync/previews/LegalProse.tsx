export function LegalProsePreview() {
  const paragraphs = [
    "אנו ב-RS Recruiting מחויבים לשמירה על פרטיותך. מדיניות זו מסבירה כיצד אנו אוספים, משתמשים ומגנים על המידע האישי שלך בעת שימוש בשירותינו.",
    "המידע שנאסף כולל פרטי קשר, קורות חיים, ניסיון מקצועי, וכל מידע אחר שתבחר לשתף עמנו. אנו משתמשים במידע זה אך ורק לצורך חיבור בין מועמדים מתאימים לבין מעסיקים.",
    "יש לך הזכות לעיין במידע, לתקנו, או לבקש מחיקתו בכל עת. לפניות בנושא פרטיות ניתן לפנות אלינו בכתובת privacy@rsrecruiting.co.il.",
  ];

  return (
    <div className="space-y-8 bg-card p-8 max-w-2xl">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">פסקאות טקסט משפטי</p>
        <div className="space-y-5">
          {paragraphs.map((p, i) => (
            <p key={i} className="text-sm leading-7 text-white/55">{p}</p>
          ))}
        </div>
      </div>
      <p className="text-xs text-white/30">
        LegalProse מקבל מפתח תרגום ומפצל ע&quot;י פסקאות (\n\n). טקסט גולמי מוצג כאן לדמו.
      </p>
    </div>
  );
}
