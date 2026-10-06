/** صفحةُ المدفوعات — **مصمَّمةٌ للهاتف، لا مقصوصةٌ من شاشة حاسوب**
 *  (قرارُ المالك 2026-09-01).
 *
 * ## ما تعرضه
 *
 * **كلُّ من ضغط «تمّ الدفع» وينتظر**: اسمُه · رقمُه · المبلغ · المرجع ·
 * الغرض · وقتُ الضغط · وزرّان — تأكيدٌ ورفض.
 *
 * **والأقدمُ أوّلاً** لأنه أطولُ انتظاراً — وقائمةٌ ترتّب بالأحدث تدفن من
 * ينتظر منذ الصباح تحت من ضغط قبل دقيقة.
 *
 * ## ولمَ بطاقاتٌ لا جدول
 *
 * **الجدولُ يفترض عرضاً**. جداولُ اللوحة مبنيّةٌ على `columns` بأعمدةٍ
 * كسريّة، وستّةُ أعمدةٍ على شاشة هاتفٍ تصير ستّةَ أعمدةٍ **مقصوصة** — يُقرأ
 * منها الأوّلُ ويُخمَّن الباقي. **والبطاقةُ تنمو طولاً، والهاتفُ يمرّر
 * طولاً.**
 *
 * **وأهدافُ اللمس ٤٤ بكسلاً فأكثر**: زرٌّ بارتفاع ٢٨ يُضغط بالظفر لا
 * بالإصبع، **وخطأُ ضغطةٍ هنا يؤكّد مالاً لم يصل**.
 *
 * ## وكيف تُفصل — **مسارٌ في اللوحة بتخطيطٍ ثانٍ، لا مشروعٌ رابع**
 *
 * **ولا `<Shell>` هنا**: كلُّ شاشةٍ في اللوحة ترسم غلافَها بنفسها، **فالفصلُ
 * أن لا تُرسم** — بلا بنيةٍ جديدةٍ ولا شرطٍ في الغلاف.
 *
 * **وهو ما يقلّ افتراقاً بعد شهر**: المصدرُ واحدٌ والبناءُ واحدٌ والنشرُ
 * واحد. `api/endpoints.ts` نفسُه، والجلسةُ نفسُها، والصلاحياتُ نفسُها، وعقدُ
 * الأخطاء نفسُه، وسلّمُ التصميم نفسُه. **ومشروعٌ رابعٌ ينسخ هذه الخمسةَ —
 * وهي بعينها ما يفترق.**
 *
 * ## والتأكيدُ يفتح حقلَ المبلغ الذي وصل — كما بُني
 *
 * **ولا يُفترض أنه المطلوب**: `confirm_payment` في الخلفية **يرفض التفعيلَ
 * بأقلَّ من الثمن ويُبقي المطالبةَ بفرقها مكتوباً** — وشاشةٌ تُرسل المبلغَ
 * المطلوبَ دائماً تُلغي ذلك الحارسَ من حيث لا يُرى.
 *
 * ## وبلغة TAXO 2.0 (AM01 — `design/t2-new/admin/AM01-payments.dc.html`)
 *
 * بطاقاتُ الهوية على الإسفلت: الاسمُ والمبلغُ بخطّ Unbounded وعملتُه بعده بالخافت، والمرجعُ والغرضُ ووقتُ الضغط صفوفٌ يفصلها
 * خطّ، **والأزرارُ ٤٨ لا تُضغط بالظفر**. **والتدفّقُ كما كان حرفاً**: «راجِع» يفتح المبلغَ مملوءاً بالمطلوب قابلاً للتعديل، والسببَ،
 * و«أكّد» و«ارفض» و«تراجع».
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  confirmCliqClaim,
  listDeclaredClaims,
  rejectCliqClaim,
} from "@/api/endpoints";
import type { CliqClaim } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { currencyLabel, moment } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** **الغرضُ بالعربية** — والمشرفُ يقرأ «اشتراك» لا `subscription`. */
const PURPOSE: Record<string, string> = {
  subscription: "اشتراك",
  wallet_topup: "شحن محفظة",
  driver_debt: "سداد دَين",
  // **`debt` هو ما ترسله الخلفية** (`ProviderOrderPurpose.DEBT`) — وكان يُطبع «debt» خاماً على الهاتف
  debt: "سداد دَين",
  ride_payment: "أجرة رحلة",
};

export function MobilePayments() {
  const { country } = useCountry();
  const { pushState } = useSession();
  const [rows, setRows] = useState<CliqClaim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    listDeclaredClaims(country)
      .then(setRows)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [country]);

  useEffect(load, [load]);

  async function act(kind: "confirm" | "reject", row: CliqClaim) {
    setBusy(true);
    setError(null);
    try {
      if (kind === "confirm") await confirmCliqClaim(row.id, amount);
      else await rejectCliqClaim(row.id, reason);
      setDone(
        kind === "confirm"
          ? "أُكّد الدفع"
          : "رُفض الطلب — وسببُه يصل صاحبَه",
      );
      setOpen(null);
      setReason("");
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    // **عرضٌ مقيَّدٌ ومركَّز**: على الهاتف يملأ الشاشة، وعلى الحاسوب لا يتمدّد
    // سطراً بعرض المكتب — **والقراءةُ تسقط بعد ٧٥ محرفاً**
    <div className="ad-mpay">
      <h1 className="ad-mpay-title">المدفوعات</h1>
      <p className="ad-mpay-lede">
        من ضغط «تمّ الدفع» في تطبيقه وينتظر تأكيدك — الأقدم أوّلاً.
      </p>

      {/* **الحالُ الرابعة تُقال صراحةً** (من `driver-app/src/lib/push.ts`):
          من رفض الإذن **لا يصله شيءٌ وهو خارج التطبيق** — والصمتُ عنده
          يُقرأ «لا مدفوعات اليوم». **والجملةُ لا تتجاوز الحقيقة**: القائمةُ
          تتحدّث حين تُفتح، فالنقصُ في الإيقاظ لا في الوصول. */}
      {pushState === "denied" ? (
        <div className="ad-note warn" role="status">
          <Icon name="notifications_off" fill />
          <span>
            إذن الإشعارات مرفوض — لن يوقظك شيء وأنت خارج التطبيق. افتح هذه
            الصفحة بنفسك، أو امنح الإذن من إعدادات النظام.
          </span>
        </div>
      ) : null}

      {error || done ? (
        <div className="ad-stack mb-12">
          <ErrorNote message={error} />
          <SuccessNote message={done} />
        </div>
      ) : null}

      {rows === null ? (
        <div className="ad-mpay-loading">
          <Spinner />
        </div>
      ) : rows.length === 0 ? (
        <div className="ad-mpay-empty">
          <p className="ad-mpay-empty-title">لا مدفوعات تنتظر</p>
          <p className="ad-mpay-empty-hint">
            حين يضغط أحدُهم «تمّ الدفع» يظهر هنا ويصلك إشعار.
          </p>
        </div>
      ) : (
        <ul className="ad-mpay-list">
          {rows.map((row) => (
            <li key={row.id} className="ad-claim">
              <div className="ad-claim-top">
                <span className="ad-claim-name">{row.payer_name ?? "—"}</span>
                <span className="ad-amount">
                  <span className="ad-num">{digits(row.amount)}</span>
                  <span className="ad-cur">{currencyLabel(row.currency)}</span>
                </span>
              </div>

              <div dir="ltr" className="ad-claim-phone ad-ltr">
                {row.payer_phone ?? "—"}
              </div>

              <dl className="ad-claim-dl">
                <div>
                  <dt>المرجع</dt>
                  <dd dir="ltr" className="ad-claim-ref">
                    {row.cart_id}
                  </dd>
                </div>
                <div>
                  <dt>الغرض</dt>
                  <dd>{PURPOSE[row.purpose] ?? row.purpose}</dd>
                </div>
                <div>
                  <dt>وقت الضغط</dt>
                  <dd>{row.declared_paid_at ? moment(row.declared_paid_at) : "—"}</dd>
                </div>
              </dl>

              {open === row.id ? (
                <div className="ad-claim-review">
                  <Field
                    name="amount"
                    label="المبلغ الذي وصلك فعلاً"
                    inputMode="decimal"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                  />
                  <p className="ad-hint">
                    ناقصٌ عن المطلوب يُبقي الطلب معلّقاً بفرقه مكتوباً، ولا
                    يُفعَّل شيء.
                  </p>
                  <Field
                    name="reason"
                    label="أو سبب الرفض — يُعرض على صاحبه"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                  <div className="ad-claim-buttons">
                    <Button
                      size="md"
                      loading={busy}
                      disabled={!amount.trim()}
                      onClick={() => void act("confirm", row)}
                    >
                      أكّد
                    </Button>
                    <Button
                      size="md"
                      variant="danger"
                      loading={busy}
                      disabled={reason.trim().length < 8}
                      onClick={() => void act("reject", row)}
                    >
                      ارفض
                    </Button>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setOpen(null)}>
                    تراجع
                  </Button>
                </div>
              ) : (
                <Button
                  size="md"
                  className="mt-12"
                  onClick={() => {
                    setOpen(row.id);
                    // **يُملأ بالمطلوب ويبقى قابلاً للتعديل** — فالأغلبُ أن
                    // يصل المطلوبُ كاملاً، **والحارسُ يبقى قائماً لمن نقص**
                    setAmount(row.amount);
                    setReason("");
                  }}
                >
                  راجِع
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="ad-mpay-foot">
        الأرقام لاتينية عمداً: المرجع يُطابَق حرفاً بحرف مع كشف حسابك،
        وتحويلُ خاناته يجعلك تقارن نصّاً بشكلٍ آخر.
      </p>
    </div>
  );
}
