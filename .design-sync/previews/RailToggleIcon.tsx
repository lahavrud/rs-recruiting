import RailToggleIcon from "@/components/admin/RailToggleIcon";

export function RailToggleIconPreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">מצבים</p>
        <div className="flex items-center gap-8">
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              className="inline-flex size-8 items-center justify-center rounded-full text-white/45 transition hover:bg-white/8 hover:text-white/85"
            >
              <RailToggleIcon className="size-4" flipped={false} />
            </button>
            <span className="text-[10px] text-white/35">הצג רשימה</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              className="inline-flex size-8 items-center justify-center rounded-full text-white/45 transition hover:bg-white/8 hover:text-white/85"
            >
              <RailToggleIcon className="size-4" flipped={true} />
            </button>
            <span className="text-[10px] text-white/35">הסתר רשימה</span>
          </div>
        </div>
      </div>
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">בתוך רצועת edge toggle</p>
        <div className="relative h-24 w-4 overflow-hidden rounded bg-well">
          <div className="absolute inset-y-0 start-1/2 w-px -translate-x-1/2 bg-white/8" />
          <div className="absolute top-1/2 start-1/2 flex size-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/12 bg-card-raised text-white/45">
            <RailToggleIcon className="size-3.5" flipped={false} />
          </div>
        </div>
      </div>
    </div>
  );
}
