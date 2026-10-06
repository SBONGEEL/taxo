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

import {
  Children,
  Fragment,
  isValidElement,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import { EmptyNote, Spinner } from "@/components/ui/Feedback";
import { cn, digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** **خلايا الصفّ واحدةً واحدة** — `render` يردّ قطعةً (`<>…</>`) خلاياها بترتيب الأعمدة.
 *
 * **ولمَ تُفكّ**: على الهاتف يصير الصفُّ بطاقةً (AM02)، **وكلُّ خليّةٍ سطرٌ بعنوان عمودها** — فتُلفّ كلُّ خليّةٍ بغلافٍ يحمل اسمَ
 * عمودها (`data-label`). **وعلى الحاسوب الغلافُ `display: contents`** فلا يتغيّر من الشبكة شيء: الخليّةُ نفسُها عنصرُ الشبكة كما كانت.
 */
function cellsOf(node: ReactNode): ReactNode[] {
  if (isValidElement(node) && node.type === Fragment) {
    return Children.toArray((node.props as { children?: ReactNode }).children);
  }
  return Children.toArray(node);
}

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

/** عمودُ الاختيار — **الفرع ٣ من §39٫١٢، وبندٌ بحجمه لا فرعٌ يُقحم** (§50).
 *
 * ## ولمَ في `Table` لا في شاشةٍ واحدة
 *
 * **نصُّ §٤٧٫١١**: «يقتضي **عمودَ اختيارٍ في `Table.tsx`** يستعمله ٢٢ جدولاً
 * — **سطحٌ مشتركٌ يُلمس لأجل فعلٍ واحد**». فهو هنا مرّةً واحدة، **ولا شاشةَ
 * تخترع مربّعَ اختيارٍ لنفسها** فتفترق الأشكالُ أوّلَ تعديل.
 *
 * ## و**اختياريٌّ بالكامل**: الجداولُ الاثنان والعشرون لا يتغيّر فيها حرف
 *
 * **من لا يمرّر `selection` يبقى كما كان بايتاً**: لا عمودَ يُضاف إلى
 * `grid-template-columns`، ولا خليّةَ تُرسم، ولا شريطَ يظهر. **وهذا شرطُ
 * المالك: «لا تغيّر منطق عمل قائماً».**
 *
 * ## والعمودُ يُحقن في الشبكة ولا يُطلب من المستدعي
 *
 * **`columns` نصٌّ واحدٌ للرأس والصفوف معاً** — وهو الدرسُ المكتوب في رأس هذا
 * الملفّ. **فلو طُلب من كلِّ شاشةٍ أن تضيف `auto ` بيدها** لَنسيتها واحدةٌ
 * فانزاح رأسُها عن صفوفها، **وهو الخطأُ الذي وُجد `columns` ليمنعه**.
 *
 * ## و«الكلّ» تعني **المعروضَ الآن** — ولا تكذب
 *
 * **القوائمُ مرقَّمةُ الصفحات ومسقوفةٌ بخمسين**، فمربّعُ رأسٍ اسمُه «الكلّ»
 * يختار ما وصل لا ما في القاعدة. **ولذلك يقول الشريطُ العددَ صراحةً** —
 * «اختِرتَ N من M المعروضة» — **فلا يظنّ المشرفُ أنه لمس ألفَ صفٍّ وهو لمس
 * خمسين**. وهو درسُ «حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه» في ثوبِ زرّ.
 */
export interface TableSelection<T> {
  /** مفاتيحُ ما اختير — **من `keyOf` نفسِها** فلا مفتاحان لشيءٍ واحد. */
  selected: ReadonlySet<string>;
  /** **دالّةُ تحديثٍ لا قيمةٌ جاهزة** — `Dispatch<SetStateAction<…>>`.
   *
   * **والعلّةُ قِيست ٢٠٢٦-٠٩-٠٤ بالنقر لا بالقراءة**: ضغطتان في دفعةِ React
   * واحدةٍ كانتا تُسقطان إحداهما — `اختِرتَ 2 من 18` بعد ثلاث ضغطات.
   * **لأن الحسابَ كان يقرأ `selected` من الخاصّيّة**، وهي في مُعالِج الضغطة
   * الثانية **قيمةُ ما قبل الأولى**. فالثانيةُ تبني مجموعةً من قيمةٍ بائدةٍ
   * وتمحو ما أضافته الأولى.
   *
   * **ولا يقع هذا بإصبعِ إنسان** — بينهما إعادةُ رسم — **لكنه يقع بضغطةٍ
   * مزدوجةٍ أو نقرٍ سريعٍ على لمس**، **ولا يصيح شيء**: يبقى صفٌّ غيرُ مختارٍ
   * وقد ظنّ المشرفُ أنه اختاره. **والعلاجُ أن يُحسب من السابق لا من
   * الخاصّيّة.**
   */
  onChange: Dispatch<SetStateAction<ReadonlySet<string>>>;
  /** **صفٌّ لا يصلح للفعل** — يُعطَّل مربّعُه ولا يُخفى.
   *
   * **ولا يُخفى بقصد**: «زرٌّ يختفي يُقرأ عطباً في اللوحة» — قاعدةٌ مكتوبةٌ
   * في `Finance.tsx` منذ بُني. ومربّعٌ معطَّلٌ يقول «هذا الصفُّ ليس منه». */
  disabled?: (row: T) => boolean;
  /** الأفعالُ التي تظهر حين يُختار شيء — **ولا يظهر الشريطُ بلا فعل**. */
  actions?: (selected: ReadonlySet<string>, clear: () => void) => ReactNode;
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
  selection,
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
  /** **عمودُ الاختيار — وغيابُه يبقي الجدولَ كما كان بايتاً** (§50). */
  selection?: TableSelection<T>;
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

  // **العمودُ يُحقن هنا** — فلا يُطلب من اثنين وعشرين مستدعياً أن يتذكّروه،
  // ولا ينزاح رأسٌ عن صفوفه لأن أحدَهم نسيه
  const grid = selection ? `auto ${columns}` : columns;

  /** **ما يقبل الاختيارَ من المعروض الآن** — لا ما في القاعدة. */
  const selectable = selection
    ? (rows ?? []).filter((row) => !selection.disabled?.(row))
    : [];
  const selectableKeys = selectable.map(keyOf);
  const chosen = selection
    ? selectableKeys.filter((key) => selection.selected.has(key)).length
    : 0;
  // **ثلاثُ حالاتٍ لا اثنتان**: لا شيء · بعضٌ · الكلّ. **و«بعضٌ» تُرسم
  // بشَرطةٍ لا بعلامة** — مربّعٌ مؤشَّرٌ بالكامل وفيه صفٌّ غيرُ مختارٍ يكذب
  const allChosen = chosen > 0 && chosen === selectableKeys.length;
  const someChosen = chosen > 0 && !allChosen;

  // **يُحسب من السابق لا من الخاصّيّة** — انظر علّةَ `onChange` أعلاه
  function setAll(next: boolean) {
    selection?.onChange((prev) => {
      const value = new Set(prev);
      for (const key of selectableKeys) {
        if (next) value.add(key);
        else value.delete(key);
      }
      return value;
    });
  }

  function toggle(key: string) {
    selection?.onChange((prev) => {
      const value = new Set(prev);
      if (value.has(key)) value.delete(key);
      else value.add(key);
      return value;
    });
  }

  // **حدٌّ أدنى للعرض وتمريرٌ أفقيّ** (قِيس ٢٠٢٦-٠٩-٠٥): ثمانيةُ أعمدةٍ
  // كسريّةٍ في ٣٦٠px — ناقصاً حشوةً ٣٦ وفواصلَ ٧٠ — **تعطي كلَّ عمودٍ نحوَ
  // ٣٠px، وزرُّ «الملفّ» وحدَه ٢٧**. فالخليةُ لا تسع محتواها **ولو قُصَّ
  // الاسمُ إلى صفر**، فتفيض على جارتها — وقِيس تقاطعٌ ٨×١٧ في `/rides`.
  //
  // **والرأسُ والصفوفُ يأخذان الحدَّ نفسَه** ويتمرّران في حاويةٍ واحدة:
  // **حاويتان منفصلتان تُزيح الرأسَ عن صفوفه**، وهو الخطأُ الذي وُجد
  // `columns` ليمنعه. **وفوق ٧٠٤px لا يتغيّر شيء** — الحدُّ لا يُلمس.
  const head = (
    <div className="ad-table-head" style={{ gridTemplateColumns: grid }}>
      {selection ? (
        <span className="ad-table-pickcell">
          <SelectBox
            checked={allChosen}
            partial={someChosen}
            disabled={selectableKeys.length === 0}
            onChange={setAll}
            label={
              allChosen ? "ألغِ اختيارَ المعروض" : "اختَرِ المعروضَ في هذه الصفحة"
            }
          />
        </span>
      ) : null}
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
          <div key={index} className="ad-table-skel">
            <span />
          </div>
        ))}
        <div className="ad-table-skel-spin">
          <Spinner />
        </div>
      </div>
    ) : rows.length === 0 ? (
      searching && noResults ? (
        <EmptyNote title={noResults.title} hint={noResults.hint} />
      ) : (
        <EmptyNote title={empty.title} hint={empty.hint} />
      )
    ) : (
      rows.map((row) => {
        const key = keyOf(row);
        const off = selection?.disabled?.(row) ?? false;
        return (
          <div
            key={key}
            // **صفوفٌ متساويةُ الارتفاع**: ٦٠ هدفُ لمسٍ كامل، وصفٌّ يقصر بمحتواه يجعل المسافاتِ غيرَ منتظمةٍ فتتعب العين
            className="ad-table-row"
            style={{ gridTemplateColumns: grid }}
          >
            {selection ? (
              <span className="ad-table-pickcell">
                <SelectBox
                  checked={selection.selected.has(key)}
                  disabled={off}
                  onChange={() => toggle(key)}
                  label="اختَرْ هذا الصفّ"
                />
              </span>
            ) : null}
            {cellsOf(render(row)).map((cell, index) => (
              <div
                key={index}
                className={index === 0 ? "ad-cell ad-cell-title" : "ad-cell"}
                data-label={headers[index] ?? ""}
              >
                {cell}
              </div>
            ))}
          </div>
        );
      })
    );

  return (
    <div
      ref={ref}
      // **min-w-0 على البطاقة نفسِها**: صارت لها ابنةٌ حدُّها الأدنى ٧٠٤px، **فنمت البطاقةُ إلى محتواها** حين كان أبوها شبكةً
      // أو صفَّاً مرناً — ودفعت الصفحةَ إلى ٧٥٨ في شاشةٍ عرضُها ٤١٢. **والتمريرُ الأفقيُّ لا يعمل ما لم يُؤذَن للحاوية أن تضيق.**
      // **وعلى الهاتف بطاقاتٌ لا جدول** (AM02): الارتفاعُ يتبع المحتوى والصفحةُ هي ما يُمرَّر (`kit.css`)
      className={cn("ad-table", `ad-table-${mode}`)}
      style={mode === "viewport" && height ? { height } : undefined}
    >
      {toolbar ? <div className="ad-table-tools">{toolbar}</div> : null}
      {/* **شريطُ الاختيار فوق الرأس وثابتٌ معه** — لا ينزلق مع الصفوف:
          من اختار خمسةً ثمّ نزل يقرأ السادسَ يفقد زرَّ الفعل من الشاشة */}
      {selection && chosen > 0 ? (
        <div className="ad-table-chosen">
          <span className="ad-table-chosen-count">
            {/* **العددان معاً ولا يكذب أحدُهما**: «الكلّ» تعني المعروضَ في
                هذه الصفحة لا ما في القاعدة — والقائمةُ مسقوفةٌ بخمسين */}
            اختِرتَ {digits(chosen)} من {digits(selectableKeys.length)} المعروضة
          </span>
          <button
            type="button"
            onClick={() => setAll(false)}
            className="ad-table-chosen-clear"
          >
            ألغِ الاختيار
          </button>
          <span className="ad-table-chosen-actions">
            {selection.actions?.(selection.selected, () => setAll(false))}
          </span>
        </div>
      ) : null}
      {/* **حاويةٌ واحدةٌ للأفق تضمّ الرأسَ والصفوف** — فلا ينزاح أحدُهما
          عن الآخر. **والرأسيُّ يبقى داخلها للصفوف وحدَها** كما كان. */}
      <div className="ad-table-x">
        <div className="ad-table-headwrap">{head}</div>
        {/* **الصفوفُ وحدَها تنزلق رأسياً** — بشريطها لا بشريط الصفحة */}
        <div className="ad-table-body">{body}</div>
      </div>
    </div>
  );
}

/** مربّعُ اختيارٍ في خليّةِ جدول — **صغيرٌ بلا نصٍّ بجانبه**.
 *
 * **ولمَ لا `Checkbox` من `ui/Field`**: ذاك يفرض ابناً نصّياً بجانبه
 * (`children` مطلوب) و`w-full`، **وهو صحيحٌ في نموذجٍ وخاطئٌ في خليّةِ
 * جدول** — يمطّ العمودَ ويترك فراغاً لا نصَّ فيه.
 *
 * **ويبقى `role="checkbox"` لا `<input>`** للسبب المكتوب في `ARCHITECTURE.md`:
 * `accent-ink` يُحلّ إلى لون اللوحة فيطلي المربّعَ بلون الخلفية.
 *
 * **و«بعضٌ» تُرسم بشَرطة**: `aria-checked="mixed"` هو ما يقوله المعيار،
 * **ومربّعٌ مؤشَّرٌ بالكامل وتحته صفٌّ غيرُ مختارٍ يكذب على من يقرؤه.**
 */
function SelectBox({
  checked,
  partial = false,
  disabled = false,
  onChange,
  label,
}: {
  checked: boolean;
  partial?: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={partial ? "mixed" : checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        // **الصفُّ نفسُه قد يكون زرّاً** (سجلُّ الرحلات يفتح الرحلةَ بالنقر)،
        // **فبلا هذا يفتح النقرُ الاثنين معاً** — وهي قاعدةُ `OpenProfile`
        event.stopPropagation();
        onChange(!checked);
      }}
      className={checked || partial ? "ad-check on" : "ad-check"}
    >
      <Icon name={partial ? "remove" : "check"} />
    </button>
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
    <div className="ad-tsearch">
      <Icon name="search" className="ad-tsearch-icon" />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="fld"
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
    // **حبّاتُ الهوية** («الكل · مكتملة» في R12): المختارةُ ممتلئةٌ بلون النصّ، والباقي بحافّة. **و`aria-pressed`** يقول أيّها قائمٌ
    // لقارئ الشاشة لا اللونُ وحدَه (قرارُ المالك 2026-08-28). **وعلى الهاتف صفٌّ واحدٌ يُمرَّر** لا يلتفّ فيدفع الجدولَ إلى أسفل
    <div className="ad-pills">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          aria-pressed={value === option.key}
          onClick={() => onPick(option.key)}
          className={value === option.key ? "ad-pill on" : "ad-pill"}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
