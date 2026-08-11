/** الجدول — `DESIGN.md` §3.3، وهو الشكل الذي تتكرر عليه كل صفحات اللوحة.
 *
 * بطاقةٌ تحوي رأس أعمدةٍ على `--sur2` وصفوفاً بنفس الشبكة. والشبكةُ نصٌّ واحد
 * يمرره المستدعي (`columns`) فلا يفترق الرأسُ عن الصفوف — وهو الخطأ الذي
 * يقع حين تُكتب `grid-template-columns` مرتين.
 */

import type { ReactNode } from "react";

import { EmptyNote, Spinner } from "@/components/ui/Feedback";
import { cn } from "@/lib/utils";

export function Table<T>({
  columns,
  headers,
  rows,
  keyOf,
  render,
  empty,
}: {
  /** قيمةُ `grid-template-columns` — واحدةٌ للرأس والصفوف معاً. */
  columns: string;
  headers: string[];
  rows: T[] | null;
  keyOf: (row: T) => string;
  render: (row: T) => ReactNode;
  empty: { title: string; hint: string };
}) {
  return (
    <div className="overflow-hidden rounded-16 border border-line bg-surface">
      <div
        className="grid gap-10 bg-surface-2 px-18 py-10 text-11 font-semibold text-muted"
        style={{ gridTemplateColumns: columns }}
      >
        {headers.map((header, index) => (
          <span key={index}>{header}</span>
        ))}
      </div>

      {rows === null ? (
        <div className="p-24">
          <Spinner className="mx-auto" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyNote title={empty.title} hint={empty.hint} />
      ) : (
        rows.map((row) => (
          <div
            key={keyOf(row)}
            className="grid items-center gap-10 border-t border-line px-18 py-12 text-12.5"
            style={{ gridTemplateColumns: columns }}
          >
            {render(row)}
          </div>
        ))
      )}
    </div>
  );
}

/** حبّاتُ الفلترة فوق الجدول — «الكل» أولاً دائماً. */
export function Pills<T extends string>({
  value,
  options,
  onPick,
}: {
  value: T | "all";
  options: { key: T | "all"; label: string }[];
  onPick: (key: T | "all") => void;
}) {
  return (
    <div className="mb-14 flex flex-wrap gap-8">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onPick(option.key)}
          className={cn(
            "rounded-full border px-14 py-7 text-12 font-semibold",
            value === option.key
              ? "border-ink text-ink"
              : "border-line text-muted",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
