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
 *
 * ## وبابٌ ثالثٌ أُضيف (2026-09-20)
 *
 * **«أعد المحاولة» و«العودة للرئيسية» يعالجان صاحبَ الشاشة ولا يقولان لنا
 * شيئاً.** فصار معهما بابان: **تقريرٌ تلقائيٌّ** يُرسَل بلا سؤال (`reportBoundary`)،
 * **وزرٌّ يكتب به صاحبُه جملةً** — وهي أندرُ ما يصلنا وأغلاه، لأنها الوحيدةُ
 * التي تقول **ما كان يحاول أن يفعل**، وذاك ما لا يقوله أثرُ مكدَّسٍ أبداً.
 *
 * **والتنبيهُ تحت الحقل شرطٌ لا زينة**: الجملةُ تُنظَّف في الخادم، ومن يكتب
 * رقمَه يستحقّ أن يعرف ذلك **قبل** أن يكتبه لا بعده.
 */

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

import { reportBoundary, sendUserReport } from "@/lib/crash-reports";

interface Props {
  children: ReactNode;
  /** يُعاد تعيينُ الحدِّ حين يتغيّر — المسارُ مثلاً، فلا تعلق الشاشةُ بعد تنقّل. */
  resetKey?: string;
}

interface State {
  error: Error | null;
  componentStack: string | null;
  noteOpen: boolean;
  note: string;
  sending: boolean;
  sent: "yes" | "queued" | null;
}

const EMPTY: State = {
  error: null,
  componentStack: null,
  noteOpen: false,
  note: "",
  sending: false,
  sent: null,
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = EMPTY;

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // **يُسجَّل أولاً**: ما لا يُكتب لا يُشخَّص، ورسالةُ المستخدم لا تكفي أحداً
    console.error("[ErrorBoundary]", error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? null });
    // **ولا يُنتظر**: الإرسالُ لا يؤخّر رسمَ البديل، وسقوطُه لا يُسقط شيئاً
    reportBoundary(error, info.componentStack ?? null);
  }

  componentDidUpdate(previous: Props): void {
    if (previous.resetKey !== this.props.resetKey && this.state.error) {
      this.setState(EMPTY);
    }
  }

  private submit = async (): Promise<void> => {
    if (this.state.sending) return;
    this.setState({ sending: true });
    const ok = await sendUserReport(
      this.state.error,
      this.state.componentStack,
      this.state.note,
    );
    this.setState({ sending: false, sent: ok ? "yes" : "queued" });
  };

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex h-full flex-col items-center justify-center gap-14 bg-bg px-32 text-center">
        <h1 className="text-18 font-bold text-ink">حدث خطأ في هذه الشاشة</h1>
        <p className="text-12.5 leading-note text-muted">
          لم يقع شيءٌ على حسابك أو رحلتك — المشكلة في العرض وحده. أعد المحاولة،
          وإن تكررت أبلغ الدعم.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-10">
          <button
            type="button"
            onClick={() => this.setState({ ...EMPTY })}
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
          {this.state.sent === null && !this.state.noteOpen && (
            <button
              type="button"
              onClick={() => this.setState({ noteOpen: true })}
              className="rounded-12 border border-line px-16 py-10 text-12.5 font-semibold text-muted"
            >
              أرسل تقريراً
            </button>
          )}
        </div>

        {this.state.noteOpen && this.state.sent === null && (
          <div className="flex w-full max-w-modal flex-col gap-8">
            <textarea
              value={this.state.note}
              onChange={(event) => this.setState({ note: event.target.value })}
              maxLength={500}
              rows={3}
              placeholder="ماذا كنت تفعل حين توقفت الشاشة؟"
              className="w-full rounded-12 border border-line bg-bg p-12 text-12.5 text-ink"
            />
            {/* **يُقال قبل الكتابة لا بعدها** — الجملةُ تُنظَّف في الخادم */}
            <p className="text-11 leading-note text-muted">
              لا تكتب رقمك أو رمز التحقق — تُحجب هذه تلقائياً قبل الحفظ.
            </p>
            <button
              type="button"
              onClick={() => void this.submit()}
              disabled={this.state.sending}
              className="rounded-12 border border-line px-16 py-10 text-12.5 font-semibold text-ink disabled:opacity-50"
            >
              {this.state.sending ? "يُرسل…" : "إرسال"}
            </button>
          </div>
        )}

        {this.state.sent !== null && (
          <p className="text-12.5 leading-note text-muted">
            {this.state.sent === "yes"
              ? "وصل التقرير — شكراً لك."
              : "سيُرسل التقرير حين تعود الشبكة."}
          </p>
        )}
      </div>
    );
  }
}
