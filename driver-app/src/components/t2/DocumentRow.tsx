/** صفُّ وثيقةٍ في «الوثائق» — **C02 كما رُسمت**: صورةٌ مخطّطةٌ و«مرفوعة ✓» لما رُفع، وإطارٌ أحمرُ و«أعد الرفع» لما رُفض،
 * وإطارٌ متقطّعٌ وبئرُ رفعٍ لما لم يُرفع. **عرضٌ وحدَه**: الرفعُ وحالُه وسببُ الرفض من الشاشة (`RegisterDocuments`).
 *
 * **والصفُّ كلُّه زرٌّ يفتح الملفّات** كما كان — وما تحته (سببُ الرفض، الرفعُ الجاري، إعادةُ ما تعثّر، تاريخُ الانتهاء) يصل
 * أبناءً (`children`).
 */
import type { ReactNode } from "react";

import { Icon } from "@/taxo2";

/** حالُ الصفّ في العرض — **أسماءُ واجهةٍ لا مرآةُ تعداد**: `uploaded` له صفٌّ لم يُرفض (منتظِرٌ أو معتمَد)، و`refused` رُفض
 *  ويُعاد رفعُه، و`missing` لا صفَّ له. ولا تقابل `DocumentReviewStatus` عمداً — فلا يُقرأ «لم يُرفع» حالاً من القاعدة. */
export type DocumentState = "uploaded" | "refused" | "missing";

export function DocumentRow({
  label,
  tag,
  sub,
  shrunk,
  state,
  percent,
  disabled,
  onOpen,
  children,
}: {
  label: string;
  /** « · اختياري» أو « · مطلوب» — **من قائمة الخلفية لا من نسخةٍ هنا**. */
  tag?: string | null;
  /** ما يُقرأ تحت الاسم: ما المطلوبُ في الصورة، أو ما يُقبل رفعُه. */
  sub?: string | null;
  /** ما صُغِّر قبل الرفع — يُقال بعد نجاحه لا قبله (`describeShrink`). */
  shrunk?: string | null;
  state: DocumentState;
  /** نسبةُ الرفع إن كانت هذه الوثيقةُ تُرفع الآن — و`null` لغيرها. */
  percent: number | null;
  disabled: boolean;
  onOpen: () => void;
  children?: ReactNode;
}) {
  const classes = ["cap-doc", state, percent !== null ? "busy" : null].filter(Boolean).join(" ");
  return (
    <div className="cap-doc-item">
      <button type="button" className={classes} disabled={disabled} onClick={onOpen}>
        {state === "missing" ? (
          <span className="cap-doc-up" aria-hidden="true">
            <Icon name="upload" />
          </span>
        ) : (
          <span className="cap-doc-thumb" aria-hidden="true" />
        )}
        <span className="cap-doc-main">
          <span className="cap-doc-title">
            {label}
            {tag ? <span className="cap-doc-tag">{tag}</span> : null}
          </span>
          {sub ? <span className="cap-doc-sub">{sub}</span> : null}
          {shrunk ? <span className="cap-doc-sub ok">{shrunk}</span> : null}
        </span>
        {percent !== null ? (
          <span className="cap-doc-pct">{`${percent}٪`}</span>
        ) : state === "uploaded" ? (
          <span className="cap-doc-done">
            <Icon name="check_circle" fill />
            مرفوعة
          </span>
        ) : state === "refused" ? (
          <span className="cap-doc-redo">أعد الرفع</span>
        ) : null}
      </button>
      {children}
    </div>
  );
}
