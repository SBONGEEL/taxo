/** حدُّ الخطأ — **بديلٌ يقول ويسجّل، بدل بياضٍ صامت**.
 *
 * **وُجد لأن عطباً ماليّاً مرّ بلا أثر** (تجربةُ المرحلة ١٣): استثناءٌ من
 * `Slot` أسقط شجرةَ React كلَّها، فصارت شاشةُ الدفع بكليك **صفرَ نصٍّ
 * وعنصرين** — لا رسالةَ للمستخدم، ولا سطرَ في السجل، ولا شيءَ يقوله من يبلّغ
 * الدعم إلا «الشاشة بيضاء». وكان يمكن أن يبقى شهراً.
 *
 * **وثلاثُ قواعدَ فيه، كلُّها عن ما لا يفعله**:
 *
 * ١. **لا يبتلع**: يكتب الخطأَ وكومةَ المكوّنات في `console.error` قبل أن يرسم
 *    شيئاً. حدٌّ يخفي السببَ أسوأُ من انهيارٍ يُرى في الأدوات.
 * ٢. **ولا يَعِد بما لا يملك**: لا يقول «أُصلح» — يقول ما وقع، ويعطي بابين:
 *    إعادةُ المحاولة (تصفيرُ الحد) والعودةُ إلى الرئيسية.
 * ٣. **وليس شاشةَ الإقلاع**: تلك تملأ انتظاراً قبل أن يبدأ شيء، وهذا يقع
 *    **بعد** أن بدأ كلُّ شيء — فنصُّهما مختلفٌ ومكانُهما مختلف.
 *
 * وموضعُه حول المسارات داخل المزوّدين: خطأُ شاشةٍ يُستبدل بها وحدها، وتبقى
 * السِمةُ والجلسةُ والشريطُ السفليُّ حيّة. **ولا يلتقط أخطاءَ ما فوقه** — تلك
 * تحتاج حدّاً ثانياً، وهو ما لا يُبنى إلا إن وقع.
 */

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** يُعاد تعيينُ الحدِّ حين يتغيّر — المسارُ مثلاً، فلا تعلق الشاشةُ بعد تنقّل. */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // **يُسجَّل أولاً**: ما لا يُكتب لا يُشخَّص، ورسالةُ المستخدم لا تكفي أحداً
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  componentDidUpdate(previous: Props): void {
    if (previous.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex h-full flex-col items-center justify-center gap-14 bg-bg px-32 text-center">
        <h1 className="text-18 font-bold text-ink">حدث خطأ في هذه الشاشة</h1>
        <p className="text-12.5 leading-note text-muted">
          لم يقع شيءٌ على حسابك أو رحلتك — المشكلة في العرض وحده. أعد المحاولة،
          وإن تكررت أبلغ الدعم.
        </p>
        <div className="flex gap-10">
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="rounded-12 border border-line px-16 py-10 text-12.5 font-semibold text-ink"
          >
            أعد المحاولة
          </button>
          <button
            type="button"
            onClick={() => {
              window.location.replace("/");
            }}
            className="rounded-12 border border-line px-16 py-10 text-12.5 font-semibold text-muted"
          >
            العودة للرئيسية
          </button>
        </div>
      </div>
    );
  }
}
