import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useTranslation } from "react-i18next";

import { ghostInputCls } from "@/styles/forms";
import {
  JOB_REQ_MAX_COUNT,
  JOB_REQ_MIN_COUNT,
  JOB_REQ_TEXT_MAX,
  type JobRequirementItem,
} from "@/types/api";

interface Props {
  value: JobRequirementItem[];
  onChange: (next: JobRequirementItem[]) => void;
  error?: string;
}

const REQUIREMENT_PLACEHOLDER_POOL = [
  "5+ שנות ניסיון בניהול מתקנים",
  "רישיון נהיגה בתוקף",
  "שליטה ב-Excel ובמערכות ERP",
  "ידע במערכות BMS / בקרת בניין",
  "תעודת מיזוג אוויר",
  "ניסיון בניהול צוות של 10+ עובדים",
  "תואר ראשון בהנדסה",
  "הסמכה בבטיחות אש",
  "שליטה בעברית ובערבית ברמת שפת אם",
  "כושר ניהולי גבוה",
  "ניסיון בעבודה מול לקוחות עסקיים",
  "זמינות לכוננות בסופי שבוע",
];

function shuffled<T>(arr: readonly T[]): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

const TOUCH_DELAY_MS = 200;
const TOUCH_TOLERANCE_PX = 5;

// ── Sortable row ─────────────────────────────────────────────────────────────
// Grip handle activates drag. Click the text → inline edit.

interface ReqItemProps {
  id: number;
  req: JobRequirementItem;
  index: number;
  placeholder: string;
  canRemove: boolean;
  onUpdate: (index: number, text: string) => void;
  onRemove: (index: number) => void;
}

function SortableReqItem({
  req,
  index,
  placeholder,
  canRemove,
  onUpdate,
  onRemove,
  id,
}: ReqItemProps) {
  const { t } = useTranslation(["common"]);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(req.text);

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed === "") {
      if (req.text === "" && canRemove) {
        onRemove(index);
      } else {
        setDraft(req.text); // restore: user cleared existing text, or last item can't be removed
      }
    } else {
      onUpdate(index, trimmed);
    }
    setEditing(false);
  };

  const startEdit = () => {
    setDraft(req.text);
    setEditing(true);
  };

  return (
    <li
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`group flex cursor-grab items-center gap-2 py-0.5 active:cursor-grabbing ${isDragging ? "relative z-50 opacity-50" : "touch:active:scale-[0.98]"}`}
    >
      {/* Grip dots — visual cue that the row is draggable; always visible on mobile */}
      <span
        aria-hidden="true"
        className="shrink-0 opacity-40 transition-opacity sm:opacity-0 sm:group-hover:opacity-60"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-3.5 text-white/50"
          aria-hidden="true"
        >
          <circle cx="5" cy="3.5" r="1" />
          <circle cx="5" cy="8" r="1" />
          <circle cx="5" cy="12.5" r="1" />
          <circle cx="11" cy="3.5" r="1" />
          <circle cx="11" cy="8" r="1" />
          <circle cx="11" cy="12.5" r="1" />
        </svg>
      </span>

      {/* Copper bullet */}
      <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-copper/60" />

      {editing ? (
        <input
          type="text"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
            if (e.key === "Escape") { setDraft(req.text); setEditing(false); }
          }}
          onPointerDown={(e) => e.stopPropagation()}
          maxLength={JOB_REQ_TEXT_MAX}
          placeholder={placeholder}
          className={`${ghostInputCls} flex-1 cursor-text`}
        />
      ) : (
        <span
          onClick={startEdit}
          className="flex-1 cursor-pointer select-none text-sm leading-relaxed"
        >
          {req.text ? (
            <span className="text-white/80 transition-colors hover:text-white/95">{req.text}</span>
          ) : (
            <span className="italic text-white/25">{placeholder}</span>
          )}
        </span>
      )}

      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={() => onRemove(index)}
        disabled={!canRemove}
        aria-label={t("common:removeRequirement")}
        className="inline-flex size-6 shrink-0 items-center justify-center rounded-sm text-white/25 opacity-0 transition group-hover:opacity-100 hover:text-danger/70 disabled:cursor-not-allowed disabled:hover:text-white/25"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-3.5"
          aria-hidden="true"
        >
          <path d="M3 8a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 3 8Z" />
        </svg>
      </button>
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function JobRequirementsInput({ value, onChange, error }: Props) {
  const { t } = useTranslation(["common"]);
  const canAdd = value.length < JOB_REQ_MAX_COUNT;
  const canRemove = value.length > JOB_REQ_MIN_COUNT;
  const placeholders = useMemo(() => shuffled(REQUIREMENT_PLACEHOLDER_POOL), []);

  const nextId = useRef(value.length);
  const [ids, setIds] = useState<number[]>(() => value.map((_, i) => i));

  // Keep ids in sync with value.length. When save() strips empty requirements
  // the parent re-seeds value with fewer items; without this, ids retains its
  // old length and SortableContext holds ghost IDs with no useSortable consumer.
  useEffect(() => {
    if (ids.length !== value.length) {
      setIds((prev) => {
        if (prev.length > value.length) return prev.slice(0, value.length);
        const extra = Array.from(
          { length: value.length - prev.length },
          () => nextId.current++,
        );
        return [...prev, ...extra];
      });
    }
  }, [ids.length, value.length]);

  // Safe for the current render: effect above runs asynchronously, so trim
  // any trailing ghost IDs here to avoid a one-tick bad render.
  const renderIds = ids.length > value.length ? ids.slice(0, value.length) : ids;

  // null = not adding; string = inline add input is open
  const [draftNew, setDraftNew] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: TOUCH_DELAY_MS, tolerance: TOUCH_TOLERANCE_PX } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = useCallback(({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const oldIndex = renderIds.indexOf(active.id as number);
    const newIndex = renderIds.indexOf(over.id as number);
    if (oldIndex === -1 || newIndex === -1) return;
    setIds((prev) => arrayMove(prev, oldIndex, newIndex));
    onChange(arrayMove(value, oldIndex, newIndex));
  }, [renderIds, value, onChange]);

  const update = (i: number, text: string) => {
    const next = value.slice();
    next[i] = { text };
    onChange(next);
  };

  const remove = (i: number) => {
    setIds((prev) => prev.filter((_, idx) => idx !== i));
    onChange(value.filter((_, idx) => idx !== i));
  };

  const add = () => setDraftNew("");

  const commitNew = () => {
    if (draftNew === null) return;
    const trimmed = draftNew.trim();
    if (trimmed.length > 0) {
      const newId = nextId.current++;
      setIds((prev) => [...prev, newId]);
      onChange([...value, { text: trimmed }]);
    }
    setDraftNew(null);
  };

  return (
    <div>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={renderIds} strategy={verticalListSortingStrategy}>
          <ul className="space-y-0.5">
            {value.map((req, i) => (
              <SortableReqItem
                key={renderIds[i]}
                id={renderIds[i]}
                req={req}
                index={i}
                placeholder={placeholders[i % placeholders.length]}
                canRemove={canRemove}
                onUpdate={update}
                onRemove={remove}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>

      {draftNew !== null && (
        <div className="mt-0.5 flex items-center gap-2 py-0.5">
          <span className="size-3.5 shrink-0" aria-hidden="true" />
          <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-copper/60" />
          <input
            type="text"
            autoFocus
            value={draftNew}
            onChange={(e) => setDraftNew(e.target.value)}
            onBlur={commitNew}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
              if (e.key === "Escape") setDraftNew(null);
            }}
            maxLength={JOB_REQ_TEXT_MAX}
            placeholder={placeholders[value.length % placeholders.length]}
            className={`${ghostInputCls} flex-1 cursor-text`}
          />
        </div>
      )}

      <div className="mt-2 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={add}
          disabled={!canAdd || draftNew !== null}
          className="flex items-center gap-2 text-sm text-copper/70 transition hover:text-copper disabled:cursor-not-allowed disabled:opacity-30"
        >
          {/* Spacer matching the grip handle column so + and label align with the list */}
          <span className="size-3.5 shrink-0" aria-hidden="true" />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="size-3 shrink-0"
            aria-hidden="true"
          >
            <path d="M8 2.75a.75.75 0 0 1 .75.75v3.75h3.75a.75.75 0 0 1 0 1.5H8.75v3.75a.75.75 0 0 1-1.5 0V8.75H3.5a.75.75 0 0 1 0-1.5h3.75V3.5A.75.75 0 0 1 8 2.75Z" />
          </svg>
          {t("common:addRequirement")}
        </button>
        <span className="text-[11px] text-white/25">
          {t("common:requirementCount", {
            count: value.length,
            min: JOB_REQ_MIN_COUNT,
            max: JOB_REQ_MAX_COUNT,
          })}
        </span>
      </div>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}
