/** الجدول — `DESIGN.md` §3.3، وهو الشكل الذي تتكرر عليه كل صفحات اللوحة.
 *
 * بطاقةٌ تحوي رأس أعمدةٍ على `--sur2` وصفوفاً بنفس الشبكة. والشبكةُ نصٌّ واحد
 * يمرره المستدعي (`columns`) فلا يفترق الرأسُ عن الصفوف — وهو الخطأ الذي
 * يقع حين تُكتب `grid-template-columns` مرتين.
 *
 * ---
 *
 * ## ارتفاعٌ ثابتٌ لا يتبع عددَ الصفوف (قرارُ المالك 2026-09-01)
 *
 * **العلّةُ في اليد والعين لا في الجمال**: قائمةٌ تمتدّ بطول محتواها تجعل
 * **الصفحةَ نفسَها يتغيّر طولُها بتغيّر البيانات** — فلا يستقرّ موضعُ زرٍّ
 * تحت الإصبع، ومن حفظ موضعَ «راجِع» في صفٍّ وجده في مكانٍ آخر بعد تحديث.
 *
 * **فالرأسُ وشريطُ الأدوات ثابتان، والصفوفُ وحدَها تنزلق** — بشريطِ تمريرٍ
 * خاصٍّ بها لا بشريط الصفحة.
 *
 * **والارتفاعُ يُشتقّ من النافذة لا يُكتب بيد**: يُقاس **موضعُ الإطار نفسِه**
 * (`getBoundingClientRect().top`) ويُطرح من ارتفاع النافذة. **ورقمٌ مكتوبٌ
 * بيدٍ يصلح لشاشةٍ واحدةٍ** — على شاشةٍ صغيرةٍ يقصّ، وعلى كبيرةٍ يترك فراغاً.
 *
 * **ويُعاد القياسُ عند تغيّر النافذة وعند تحرّك الإطار**: `ResizeObserver`
 * على الإطار نفسِه يمسك ما لا يمسكه `resize` — فتحُ لوحةِ فلترةٍ فوقه يزيحه
 * لأسفل، **والارتفاعُ المحسوبُ مرّةً يصير كاذباً بعدها**.
 *
 * ## وحالتان مكتوبتان لا واحدة
 *
 * **«لا نتائج لبحثك» ليست «لا بيانات بعد»**: الأولى تقول «غيّر بحثك»
 * والثانية تقول «ابدأ بإضافة». **وخلطُهما يُنتج مشرفاً يظنّ الجدولَ فارغاً
 * وفيه ألفُ صفٍّ** لأنه كتب حرفاً في البحث ونسيه.
 *
 * ## وحالُ تحميلٍ لا تقفز فيها الصفحة
 *
 * **الهيكلُ بارتفاع الصفوف نفسِه**: دوّارةٌ في فراغٍ ترتفع ثمّ تهبط حين تصل
 * البيانات، **فتقفز الصفحةُ تحت المؤشّر**.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { EmptyNote, Spinner } from "@/components/ui/Feedback";
import { cn } from "@/lib/utils";

/** ما يبقى تحت الجدول من هامش الصفحة — **مسافةٌ من السلّم لا رقمٌ حرّ**. */
const BOTTOM_GUTTER = 24;
/** أدنى ارتفاعٍ يبقى للصفوف مهما ضاقت النافذة — أربعةُ صفوفٍ تقريباً. */
const MIN_VIEWPORT = 180;

/** يقيس كم يتبقّى من النافذة تحت عنصرٍ بعينه — **ويُعاد القياسُ حين يتحرّك**.
 *
 * **ولمَ `ResizeObserver` على الأب لا `resize` وحدَه**: `resize` يمسك تغيّرَ
 * النافذة ولا يمسك **تحرّكَ العنصر نفسِه** — سطرُ خطأٍ يظهر فوقه أو حبّاتُ
 * فلترةٍ تنفتح تزيحه لأسفل، فيصير المقيسُ قبلها أطولَ من الواقع بمقدار ما
 * أُزيح، **وتخرج آخرُ الصفوف تحت حافّة الشاشة**.
 */
function useViewportHeight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [height, setHeight] = useState<number | null>(null);

  const measure = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    const top = node.getBoundingClientRect().top;
    setHeight(Math.max(MIN_VIEWPORT, window.innerHeight - top - BOTTOM_GUTTER));
  }, []);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    const observer = new ResizeObserver(measure);
    // **يُراقَب جسدُ الصفحة لا الإطارُ وحدَه**: ما يزيح الإطارَ يقع فوقه لا
    // فيه، فمراقبةُ الإطار نفسِه لا ترى الإزاحة
    if (document.body) observer.observe(document.body);
    return () => {
      window.removeEventListener("resize", measure);
      observer.disconnect();
    };
  }, [measure]);

  return { ref, height };
}

export interface TableEmpty {
  title: string;
  hint: string;
}

export function Table<T>({
  columns,
  headers,
  rows,
  keyOf,
  render,
  empty,
  noResults,
  searching = false,
  toolbar,
  height: mode = "viewport",
}: {
  /** قيمةُ `grid-template-columns` — واحدةٌ للرأس والصفوف معاً. */
  columns: string;
  headers: string[];
  rows: T[] | null;
  keyOf: (row: T) => string;
  render: (row: T) => ReactNode;
  /** **«لا بيانات بعد»** — الجدولُ فارغٌ ولا بحثَ قائم. */
  empty: TableEmpty;
  /** **«لا نتائج لبحثك»** — بحثٌ قائمٌ ولم يُطابق شيئاً. */
  noResults?: TableEmpty;
  /** أثمّة بحثٌ أو ترشيحٌ قائمٌ الآن؟ — **منه تُختار الحالُ الفارغة**. */
  searching?: boolean;
  /** شريطُ الأدوات — يثبت فوق الرأس ولا ينزلق مع الصفوف. */
  toolbar?: ReactNode;
  /** **ثلاثةُ أوضاع، والفرقُ بينها مَن يملك الصفحة**:
   *
   * - `viewport` (الافتراض) — **جدولُ الصفحة الرئيس**: يأخذ ما تبقّى من
   *   النافذة، فيثبت طولُ الصفحة مهما تغيّرت البيانات.
   * - `compact` — **جدولٌ تابعٌ تحته**: صفحةٌ فيها أربعةُ جداولَ لا تُعطى
   *   أربعَ نوافذ، **وجدولٌ تابعٌ يمتدّ بمحتواه يُعيد العلّةَ من بابها**.
   *   فسقفٌ من السلّم وشريطُ تمريرٍ خاصّ.
   * - `auto` — يمتدّ بمحتواه: لبطاقةٍ من ثلاثة صفوفٍ داخل شبكة. */
  height?: "viewport" | "compact" | "auto";
}) {
  const { ref, height } = useViewportHeight<HTMLDivElement>();

  const head = (
    <div
      className="grid gap-10 bg-surface-2 px-18 py-10 text-11 font-semibold text-muted"
      style={{ gridTemplateColumns: columns }}
    >
      {headers.map((header, index) => (
        <span key={index}>{header}</span>
      ))}
    </div>
  );

  const body =
    rows === null ? (
      // **هيكلٌ بارتفاع الصفوف** — لا دوّارةٌ في فراغٍ تجعل الصفحةَ تقفز
      <div>
        {[0, 1, 2, 3, 4].map((index) => (
          <div
            key={index}
            className="flex min-h-44 items-center border-t border-line px-18"
          >
            <span className="h-10 w-full rounded-full bg-surface-2" />
          </div>
        ))}
        <div className="border-t border-line p-16">
          <Spinner className="mx-auto" />
        </div>
      </div>
    ) : rows.length === 0 ? (
      searching && noResults ? (
        <EmptyNote title={noResults.title} hint={noResults.hint} />
      ) : (
        <EmptyNote title={empty.title} hint={empty.hint} />
      )
    ) : (
      rows.map((row) => (
        <div
          key={keyOf(row)}
          // **صفوفٌ متساويةُ الارتفاع**: `min-h-44` هدفُ لمسٍ كامل، وصفٌّ
          // يقصر بمحتواه يجعل المسافاتِ غيرَ منتظمةٍ فتتعب العين
          className="grid min-h-44 items-center gap-10 border-t border-line px-18 py-12 text-12.5"
          style={{ gridTemplateColumns: columns }}
        >
          {render(row)}
        </div>
      ))
    );

  return (
    <div
      ref={ref}
      className="flex flex-col overflow-hidden rounded-16 border border-line bg-surface"
      style={mode === "viewport" && height ? { height } : undefined}
    >
      {toolbar ? (
        <div className="shrink-0 border-b border-line px-14 py-10">{toolbar}</div>
      ) : null}
      <div className="shrink-0">{head}</div>
      {/* **الصفوفُ وحدَها تنزلق** — بشريطها لا بشريط الصفحة */}
      <div
        className={cn(
          "min-h-0",
          mode === "viewport" && "flex-1 overflow-y-auto",
          mode === "compact" && "max-h-list overflow-y-auto",
        )}
      >
        {body}
      </div>
    </div>
  );
}

/** حقلُ بحثِ القائمة — **واحدٌ لكلِّ جدول، في شريط أدواته**.
 *
 * **ولا يُصفّي في المتصفح إن كانت القائمةُ مرقَّمةَ الصفحات**: بحثٌ يقرأ
 * الصفحةَ الحاليةَ وحدَها يبدو معطوباً لمن يعرف أن الصفَّ موجود — والمشرفُ
 * يعرف. **فالمرقَّمةُ تصفّي من الخادم** (`q`)، والقصيرةُ الكاملةُ تصفّي هنا.
 */
export function TableSearch({
  value,
  onChange,
  placeholder = "ابحث…",
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-10 border border-line bg-surface-2 px-12 py-8 text-12.5 text-ink placeholder:text-muted focus:border-ink focus:outline-none"
      />
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
