import { useState } from "react";
import RangeSlider from "@/components/ui/RangeSlider";

function formatSalary(n: number) {
  return `₪${n.toLocaleString("he-IL")}`;
}

export function RangeSliderPreview() {
  const [salary, setSalary] = useState<[number, number]>([15000, 35000]);
  const [exp, setExp] = useState<[number, number]>([2, 8]);
  return (
    <div className="space-y-10 bg-card p-8 max-w-md">
      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-copper">טווח שכר</p>
        <p className="mb-4 text-xs text-white/40">
          {formatSalary(salary[0])} – {formatSalary(salary[1])}
        </p>
        <RangeSlider
          min={5000}
          max={60000}
          step={1000}
          value={salary}
          onChange={setSalary}
          formatValue={formatSalary}
          ariaLabelMin="שכר מינימלי"
          ariaLabelMax="שכר מקסימלי"
        />
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-copper">שנות ניסיון (isLarge)</p>
        <p className="mb-4 text-xs text-white/40">{exp[0]}–{exp[1]} שנים</p>
        <RangeSlider
          min={0}
          max={20}
          step={1}
          value={exp}
          onChange={setExp}
          formatValue={(n) => `${n} שנים`}
          ariaLabelMin="ניסיון מינימלי"
          ariaLabelMax="ניסיון מקסימלי"
          isLarge
        />
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-copper">ללא תוויות</p>
        <RangeSlider
          min={0}
          max={100}
          value={[20, 70]}
          onChange={() => {}}
          shouldShowLabels={false}
        />
      </div>
    </div>
  );
}
