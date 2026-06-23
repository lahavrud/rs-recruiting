import { useCallback, useEffect, useMemo, useState } from "react";

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
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useTranslation } from "react-i18next";

import { JOB_TAG_MAX_COUNT, JOB_TAG_MAX_LEN } from "@/types/jobs";
const TAG_EDIT_MIN_CHARS = 4;

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  error?: string;
}

const TAG_PLACEHOLDER_POOL = [
  "רכב צמוד",
  "טלפון נייד",
  "ארוחות",
  "קרן השתלמות",
  "ניהול בכיר",
  "תפקיד שטח",
  "BMS",
  "כוננות",
  "משמרות",
  "RFID",
  "סביבה",
  "חברה ציבורית",
];

function pickRandom<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

const TOUCH_DELAY_MS = 200;
const TOUCH_TOLERANCE_PX = 5;

// ── Sortable pill ─────────────────────────────────────────────────────────────
// Long press (250 ms) on the label → drag to reorder.
// Short click on the label → inline edit.
// × button removes the tag.

function SortableTag({
  tag,
  onRemove,
  onEdit,
}: {
  tag: string;
  onRemove: () => void;
  onEdit: (next: string) => void;
}) {
  const { t } = useTranslation(["common"]);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(tag);

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tag });

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== tag) onEdit(trimmed);
    else setDraft(tag);
    setIsEditing(false);
  };

  return (
    <span
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`inline-flex items-center rounded-full border text-xs font-medium text-copper ${
        isDragging ? "z-50 opacity-50" : ""
      } ${isEditing ? "border-copper/50 bg-copper/18 ps-2 pe-1 py-1" : "border-copper/35 bg-copper/12 ps-0 pe-1 py-0"}`}
    >
      {isEditing ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              e.currentTarget.blur();
            }
            if (e.key === "Escape") {
              setDraft(tag);
              setIsEditing(false);
            }
          }}
          maxLength={JOB_TAG_MAX_LEN}
          className="inline-block bg-transparent text-copper outline-none"
          style={{ width: `${Math.max(draft.length + 1, TAG_EDIT_MIN_CHARS)}ch` }}
        />
      ) : (
        <>
          {/* Tag text — drag target + tap/click to edit */}
          <span
            {...attributes}
            {...listeners}
            onClick={() => {
              setDraft(tag);
              setIsEditing(true);
            }}
            title={t("common:editTag")}
            className="cursor-grab select-none px-2 py-1 active:cursor-grabbing"
          >
            {tag}
          </span>
        </>
      )}

      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={onRemove}
        aria-label={`${t("common:removeTag")} ${tag}`}
        className="ms-0.5 inline-flex size-5 items-center justify-center rounded-full text-copper/70 transition hover:bg-copper/20 hover:text-copper"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-3"
          aria-hidden="true"
        >
          <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06L6.94 8l-4.72 4.72a.75.75 0 1 0 1.06 1.06L8 9.06l4.72 4.72a.75.75 0 1 0 1.06-1.06L9.06 8l4.72-4.72a.75.75 0 0 0-1.06-1.06L8 6.94 3.28 2.22Z" />
        </svg>
      </button>
    </span>
  );
}

// ── Add pill ──────────────────────────────────────────────────────────────────

function AddTagPill({
  existing,
  onAdd,
}: {
  existing: string[];
  onAdd: (tag: string) => void;
}) {
  const { t } = useTranslation(["common"]);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const placeholder = useMemo(() => pickRandom(TAG_PLACEHOLDER_POOL), []);

  const commit = () => {
    const trimmed = draft.trim();
    if (
      trimmed &&
      trimmed.length <= JOB_TAG_MAX_LEN &&
      !existing.some((v) => v.toLowerCase() === trimmed.toLowerCase())
    ) {
      onAdd(trimmed);
    }
    setDraft("");
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <span className="inline-flex items-center rounded-full border border-copper/50 bg-copper/15 py-1 px-2.5 text-xs font-medium">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            }
            if (e.key === "Escape") {
              setDraft("");
              setIsEditing(false);
            }
          }}
          maxLength={JOB_TAG_MAX_LEN}
          placeholder={placeholder}
          className="inline-block min-w-0 bg-transparent text-copper placeholder:text-copper/35 outline-none"
          style={{ width: `${Math.max(draft.length + 1, TAG_EDIT_MIN_CHARS)}ch` }}
        />
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setIsEditing(true)}
      aria-label={t("common:addTag")}
      className="inline-flex items-center gap-1 rounded-full border border-dashed border-copper/40 py-1 px-2 text-xs font-medium text-copper/70 transition hover:border-copper/65 hover:text-copper"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        fill="currentColor"
        className="size-3"
        aria-hidden="true"
      >
        <path d="M8 2.75a.75.75 0 0 1 .75.75v3.75h3.75a.75.75 0 0 1 0 1.5H8.75v3.75a.75.75 0 0 1-1.5 0V8.75H3.5a.75.75 0 0 1 0-1.5h3.75V3.5A.75.75 0 0 1 8 2.75Z" />
      </svg>
      {t("common:addTag")}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function JobTagsInput({ value, onChange, error }: Props) {
  const { t } = useTranslation(["common"]);

  // Deduplicate preserving first occurrence (case-insensitive).
  // Guards against dnd-kit ID collisions when the server returns duplicate tag
  // values; two useSortable({ id: tag }) calls with the same string corrupt the
  // internal hit map and make drops silently no-op or reorder the wrong item.
  const uniqValue = useMemo(
    () =>
      value.filter(
        (tag, i, arr) =>
          arr.findIndex((t) => t.toLowerCase() === tag.toLowerCase()) === i,
      ),
    [value],
  );
  useEffect(() => {
    if (uniqValue.length !== value.length) onChange(uniqValue);
    // onChange is a stable prop; value is the real trigger — uniqValue derives from it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const canAdd = uniqValue.length < JOB_TAG_MAX_COUNT;

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: TOUCH_DELAY_MS, tolerance: TOUCH_TOLERANCE_PX },
    }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      if (!over || active.id === over.id) return;
      const oldIndex = uniqValue.indexOf(active.id as string);
      const newIndex = uniqValue.indexOf(over.id as string);
      if (oldIndex === -1 || newIndex === -1) return;
      onChange(arrayMove(uniqValue, oldIndex, newIndex));
    },
    [uniqValue, onChange],
  );

  const remove = (tag: string) => onChange(uniqValue.filter((t) => t !== tag));
  const edit = (oldTag: string, newTag: string) => {
    if (uniqValue.some((t) => t.toLowerCase() === newTag.toLowerCase() && t !== oldTag))
      return;
    onChange(uniqValue.map((t) => (t === oldTag ? newTag : t)));
  };

  return (
    <div>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={uniqValue} strategy={rectSortingStrategy}>
          <div className="flex flex-wrap items-center gap-1.5">
            {uniqValue.map((tag) => (
              <SortableTag
                key={tag}
                tag={tag}
                onRemove={() => remove(tag)}
                onEdit={(next) => edit(tag, next)}
              />
            ))}
            {canAdd && (
              <AddTagPill
                existing={uniqValue}
                onAdd={(tag) => onChange([...uniqValue, tag])}
              />
            )}
          </div>
        </SortableContext>
      </DndContext>
      <p className="mt-1.5 text-[11px] text-white/30">
        {t("common:tagHint", { max: JOB_TAG_MAX_COUNT })}
      </p>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}
