/** منتقي الأيقونات — **يقرأ القائمةَ من البابِ الذي يحرسها**.
 *
 * **ولا قائمةَ ثانيةٌ تُكتب هنا** (قرارُ المالك 2026-08-31): نسختان تفترقان
 * بحرفٍ يوماً، **فيعرض المنتقي ما يرفضه الباب** — والمشرفُ يختار من قائمةٍ
 * مرسومةٍ أمامه ثم يُرفض، ولا شيءَ في الشاشة يقول لمَ.
 *
 * **ولمَ منتقٍ لا حقلٌ حرّ**: اسمٌ مكتوبٌ خطأً كان يرسم `LayoutGrid`
 * **صامتاً** — لا خطأَ ولا تحذير — **فلا يعلم المشرفُ أنه أخطأ حتى يفتح
 * التطبيق**. وهو «بديلٌ يعمل ويخفي العطبَ الذي بُني له» بعينه.
 *
 * **والأيقونةُ تُرى لا تُقرأ**: اسمٌ في قائمةٍ منسدلة يُختار بالتخمين، **والرسمُ
 * نفسُه هو ما سيراه صاحبُ الهاتف** — فهذا هو الشيء الذي يُختار.
 */

import * as icons from "lucide-react";
import { useEffect, useState } from "react";

import { listServiceIcons } from "@/api/endpoints";
import { cn } from "@/lib/utils";

/** **الرسمُ باسمه kebab كما تنطقه lucide في التطبيقين** — والنسخةُ واحدة. */
export function Glyph({
  name,
  className,
}: {
  name: string | null;
  className: string;
}) {
  if (!name) return null;
  const key = name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  const table = icons as unknown as Record<
    string,
    ((props: { className?: string }) => JSX.Element) | undefined
  >;
  const Icon = table[key];
  return Icon ? <Icon className={className} /> : null;
}

export function IconPicker({
  value,
  onPick,
  /** **اللافتةُ قد تكون بلا أيقونة، والبلاطةُ لا** — عمودُها إلزاميّ. */
  clearable = false,
}: {
  value: string | null;
  onPick: (icon: string | null) => void;
  clearable?: boolean;
}) {
  const [names, setNames] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listServiceIcons()
      .then((list) => !cancelled && setNames(list))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  // **وغيابُ القائمة يوقف ولا يُقرأ «لا أيقونات»**: شبكةٌ فارغةٌ تُقرأ
  // «لا خيارَ لك»، وهي كذبٌ — الخيارُ موجودٌ ولم يصل
  if (failed) {
    return (
      <p className="rounded-12 border border-line bg-surface-2 px-12 py-10 text-11.5 text-muted">
        تعذّر تحميل قائمة الأيقونات — لا تُكتب باليد، أعد المحاولة.
      </p>
    );
  }

  return (
    <div>
      <div className="label">الأيقونة</div>
      <div className="mt-6 grid max-h-[196px] grid-cols-10 gap-4 overflow-y-auto rounded-12 border border-line bg-surface-2 p-8">
        {names.map((name) => (
          <button
            key={name}
            type="button"
            title={name}
            aria-label={name}
            aria-pressed={name === value}
            onClick={() => onPick(name)}
            className={cn(
              "flex items-center justify-center rounded-10 p-8",
              name === value
                ? "bg-accent text-accent-ink"
                : "text-muted hover:bg-surface",
            )}
          >
            <Glyph name={name} className="size-18" />
          </button>
        ))}
      </div>
      <div className="mt-6 flex items-center gap-8">
        <span className="text-11.5 text-muted">
          المختارة: {value ?? "بلا أيقونة"}
        </span>
        {clearable && value ? (
          <button
            type="button"
            className="text-11.5 font-semibold text-muted underline"
            onClick={() => onPick(null)}
          >
            انزعها
          </button>
        ) : null}
      </div>
    </div>
  );
}
