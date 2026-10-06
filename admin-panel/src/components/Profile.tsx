/** الملفُّ الشخصيُّ الكامل — **أقسامٌ في الدرج القائم لا درجٌ ثانٍ**
 *  (البند ١، قرارُ المالك 2026-09-02، SPEC §37).
 *
 * **العلّةُ**: كلُّ ما تعرفه المنصةُ عن شخصٍ واحد كان موزَّعاً على ستِّ
 * شاشات — رحلاتُه في «الرحلات»، ورصيدُه في درجه، وسلفتُه تحت قائمة الكباتن،
 * ورسمُ إلغائه في صفحةٍ ثالثة. **فمن سأل «من هذا؟» فتح ستّاً وترجم بينها
 * بمعرِّف**، وأوّلُ ما يسقط في ذلك ليس الوقتَ بل الربط: مشرفٌ يرى دَيناً ولا
 * يرى أن صاحبَه أوقف نفسَه أمس.
 *
 * ## ولا بابَ جامعٌ في الخلفية — **بقرارٍ لا بسهو**
 *
 * §5-ج يقول بنصِّه إن **شاشةَ لوحةٍ ليست مساراً حرجاً**، و«لها أن تسأل عدّةَ
 * أبوابٍ إن كان كلٌّ منها مصدرَ مفهومه الواحد»؛ **والقاعدةُ هناك «الصفحةُ
 * تقرأ ولا تحسب من جديد»**. فبابٌ واحدٌ يجمع الرصيدَ والسلفَ والرحلاتِ يصير
 * **مصدراً ثانياً** لِما له مصدر — ويفترق عنه أوّلَ ما يتغيّر أحدُهما.
 *
 * **فكلُّ قسمٍ ينادي بابَ مفهومه، مرشَّحاً بمعرِّف صاحبه لا باسمه**: اسمان
 * متشابهان يخلطان ملفَّي شخصين، **والخطأُ هنا يُقرأ حقيقةً عن إنسان**.
 *
 * ## والأقسامُ تُفتح بطلبٍ لا عند فتح الدرج
 *
 * **وهو ما تفعله معاينةُ الوثيقة أصلاً** في `Drivers.tsx`: «درجٌ فيه تسعُ
 * وثائقَ يجلبها كلَّها عند الفتح يحمّل تسعَ صورٍ لا ينظر المشرفُ إلى أكثرها».
 * **وسبعةُ نداءاتٍ عند كلِّ فتحةِ درجٍ أثقلُ منها**: المشرفُ يفتح خمسين درجاً
 * في جلسة مراجعة، وأكثرُها لا يُقرأ منه إلا الوثائق.
 *
 * **والأقسامُ لا تُغلق بعد فتحها**: من فتح «الرحلات» ثمّ «المحفظة» يقارن
 * بينهما، **وقسمٌ يطوي أخاه يجعل المقارنةَ ذهاباً وإياباً**.
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import type { Tone } from "@/components/ui/Badge";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** قسمٌ يُطوى ويُفتح، **ويقرأ بابَه عند أوّل فتحةٍ لا قبلها**.
 *
 * **والحالُ ثلاثٌ لا اثنتان**: لم يُفتح بعد · يُقرأ الآن · وصل. **وخلطُ
 * الأولى بالثالثة** يجعل قسماً لم يُسأل يُقرأ «لا شيء فيه» — وهي «لا نتائج»
 * التي ليست «لا بيانات» بعينها (§36).
 */
export function ProfileSection<T>({
  title,
  icon,
  hint,
  load,
  children,
  /** سطرٌ يظهر على الرأس بلا فتحٍ — لِما يجب أن يُرى قبل أن يُسأل عنه. */
  badge,
  /** يُفتح من أوّل رسمة — للقسم الذي هو سببُ فتح الدرج. */
  open: initiallyOpen = false,
}: {
  title: string;
  /** **أيقونةُ القسم** في مربّعها الغائر (A09) — زينةٌ بجانب العنوان، والمعنى في العنوان. */
  icon?: string;
  hint?: string;
  load: () => Promise<T>;
  children: (data: T, reload: () => void) => ReactNode;
  badge?: ReactNode;
  open?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  // **مفتاحٌ يزيد ليُعاد النداء** — وقراءةٌ ثانيةٌ بعد فعلٍ في القسم نفسِه
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setError(null);
    load()
      .then((found) => {
        if (alive) setData(found);
      })
      .catch((caught) => {
        if (!alive) return;
        setError(
          caught instanceof ApiError ? caught.message : "تعذّرت قراءة هذا القسم",
        );
      });
    return () => {
      alive = false;
    };
    // `load` تُمرَّر من الشاشة ملفوفةً بـ`useCallback` — وبلا ذلك يُعاد
    // النداءُ عند كلِّ رسمة
  }, [open, load, round]);

  return (
    // **بطاقةٌ تُطوى وتُفتح** (A09): رأسُها صفُّ قائمةٍ بأيقونته وسهمه، وجسدُها في البطاقة نفسِها
    <section className={open ? "ad-sec open" : "ad-sec"}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="ad-sec-head"
      >
        {icon ? (
          <span className="ad-tile">
            <Icon name={icon} />
          </span>
        ) : null}
        <span className="ad-sec-title">{title}</span>
        {badge}
        <Icon name="expand_more" className="ad-sec-chev" />
      </button>

      {open ? (
        <div className="ad-sec-body">
          {hint ? <p className="ad-sec-hint">{hint}</p> : null}
          <ErrorNote message={error} />
          {error ? null : data === null ? (
            <div className="ad-sec-loading">
              <Spinner />
            </div>
          ) : (
            children(data, () => setRound((n) => n + 1))
          )}
        </div>
      ) : null}
    </section>
  );
}

/** حقائقُ الحساب — **شبكةُ مفتاحٍ وقيمة، لا فقرةُ نثر**.
 *
 * **والقيمةُ الغائبةُ تُكتب «—» ولا يُحذف سطرُها**: سطرٌ يختفي يجعل المشرفَ
 * يعدّ ما يراه ويظنّ أن الحقلَ غيرُ موجودٍ في النظام، **لا أنه فارغٌ لهذا
 * الشخص**.
 */
export function Facts({
  rows,
}: {
  rows: { label: string; value: ReactNode; ltr?: boolean }[];
}) {
  return (
    <dl className="ad-facts">
      {rows.map((row) => (
        <div key={row.label} className="min-w-0">
          <dt>{row.label}</dt>
          <dd dir={row.ltr ? "ltr" : undefined}>
            {row.value === null || row.value === undefined || row.value === ""
              ? "—"
              : row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** قائمةٌ قصيرةٌ داخل قسمٍ من الملفّ — **لا `Table`**.
 *
 * **والفرقُ ليس شكلاً**: `Table` يملك ارتفاعَ الصفحة أو سقفاً من السلّم
 * (§36)، **وهذا يعيش داخل درجٍ له شريطُ تمريرٍ واحد** — فجدولٌ بشريطه داخل
 * درجٍ بشريطه شريطان يتنازعان الإصبع.
 */
export function MiniList<T>({
  rows,
  keyOf,
  render,
  empty,
}: {
  rows: T[];
  keyOf: (row: T) => string;
  render: (row: T) => ReactNode;
  empty: string;
}) {
  if (rows.length === 0) {
    return <p className="ad-mini-empty">{empty}</p>;
  }
  // **صفوفٌ يفصلها خطٌّ في بطاقة القسم** (كقوائم الهوية) — لا صندوقٌ لكلِّ صفّ
  return (
    <ul className="ad-mini">
      {rows.map((row) => (
        <li key={keyOf(row)}>{render(row)}</li>
      ))}
    </ul>
  );
}

/** سطرٌ في `MiniList`: عنوانٌ وتحته وقتُه، وقيمةٌ في الطرف. */
export function MiniRow({
  title,
  at,
  value,
  tone,
  note,
}: {
  title: ReactNode;
  at?: string | null;
  value?: ReactNode;
  tone?: Tone;
  note?: ReactNode;
}) {
  return (
    <>
      <div className="ad-mini-row">
        <span className="ad-mini-main">
          <span className="ad-mini-title">{title}</span>
          {at ? <span className="ad-mini-at">{moment(at)}</span> : null}
        </span>
        {value ? (
          tone ? (
            <Badge tone={tone}>{value}</Badge>
          ) : (
            <span className="ad-mini-value">{value}</span>
          )
        ) : null}
      </div>
      {note ? <p className="ad-mini-note">{note}</p> : null}
    </>
  );
}

/** «آخرُ ما وصل، وقد يكون أكثر» — **سطرٌ يقول إن القائمةَ مقصوصة**.
 *
 * **وبلاه تُقرأ خمسةُ صفوفٍ على أنها كلُّ ما للشخص**: من رأى «٥ رحلات» في
 * ملفٍّ اسمُه الكامل قرأ رقماً كاذباً — **والملفُّ يعرض آخرَها لا يعدّها**.
 */
export function CappedNote({ shown, cap }: { shown: number; cap: number }) {
  if (shown < cap) return null;
  return (
    <p className="ad-capped">
      يُعرض آخرُ {digits(String(cap))} — وهذا ليس عددَها. القائمةُ الكاملةُ في
      شاشتها.
    </p>
  );
}

/** خطّافٌ يثبّت دالّةَ القراءة على معرِّفٍ واحد — **فلا يُعاد النداء بلا سبب**.
 *
 * **ولمَ هنا لا في كلِّ قسم**: `ProfileSection` تعتمد على ثباتِ `load`، وسبعةُ
 * أقسامٍ تكتب `useCallback` بيدها **يَنسى أحدُها الاعتماديةَ فيدور بلا نهاية**.
 */
export function useLoader<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
): () => Promise<T> {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useCallback(fetcher, deps);
}
