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
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { money, moment } from "@/lib/format";

/** **الغرضُ بالعربية** — والمشرفُ يقرأ «اشتراك» لا `subscription`. */
const PURPOSE: Record<string, string> = {
  subscription: "اشتراك",
  wallet_topup: "شحن محفظة",
  driver_debt: "سداد دَين",
  ride_payment: "أجرة رحلة",
};

export function MobilePayments() {
  const { country } = useCountry();
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
    <div className="mx-auto w-full max-w-paper px-14 py-16">
      <h1 className="text-17 font-bold text-ink">المدفوعات</h1>
      <p className="mt-4 text-12 leading-note text-muted">
        من ضغط «تمّ الدفع» في تطبيقه وينتظر تأكيدك — الأقدم أوّلاً.
      </p>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {rows === null ? (
        <p className="mt-16 text-12 text-muted">…يُحمَّل</p>
      ) : rows.length === 0 ? (
        <div className="mt-16 rounded-16 border border-line bg-surface-2 p-20 text-center">
          <p className="text-13 font-bold text-ink">لا مدفوعات تنتظر</p>
          <p className="mt-4 text-11.5 leading-note text-muted">
            حين يضغط أحدُهم «تمّ الدفع» يظهر هنا ويصلك إشعار.
          </p>
        </div>
      ) : (
        <ul className="mt-14 space-y-12">
          {rows.map((row) => (
            <li
              key={row.id}
              className="rounded-16 border border-line bg-surface p-14"
            >
              <div className="flex items-baseline justify-between gap-10">
                <span className="text-14 font-bold text-ink">
                  {row.payer_name ?? "—"}
                </span>
                <span className="text-16 font-bold text-ink">
                  {money(row.amount, row.currency)}
                </span>
              </div>

              <div dir="ltr" className="mt-2 text-start text-12 text-muted">
                {row.payer_phone ?? "—"}
              </div>

              <dl className="mt-10 space-y-6 border-t border-line pt-10">
                <div className="flex items-baseline justify-between gap-10">
                  <dt className="text-11.5 text-muted">المرجع</dt>
                  <dd
                    dir="ltr"
                    className="select-all break-all text-start text-12 font-bold text-ink"
                  >
                    {row.cart_id}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-10">
                  <dt className="text-11.5 text-muted">الغرض</dt>
                  <dd className="text-12 text-ink">
                    {PURPOSE[row.purpose] ?? row.purpose}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-10">
                  <dt className="text-11.5 text-muted">وقت الضغط</dt>
                  <dd className="text-12 text-ink">
                    {row.declared_paid_at ? moment(row.declared_paid_at) : "—"}
                  </dd>
                </div>
              </dl>

              {open === row.id ? (
                <div className="mt-12 space-y-10 border-t border-line pt-12">
                  <Field
                    name="amount"
                    label="المبلغ الذي وصلك فعلاً"
                    inputMode="decimal"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                  />
                  <p className="text-11 leading-note text-muted">
                    ناقصٌ عن المطلوب يُبقي الطلب معلّقاً بفرقه مكتوباً، ولا
                    يُفعَّل شيء.
                  </p>
                  <Field
                    name="reason"
                    label="أو سبب الرفض — يُعرض على صاحبه"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                  <div className="flex gap-8">
                    <Button
                      className="flex-1"
                      loading={busy}
                      disabled={!amount.trim()}
                      onClick={() => void act("confirm", row)}
                    >
                      أكّد
                    </Button>
                    <Button
                      className="flex-1"
                      variant="danger"
                      loading={busy}
                      disabled={reason.trim().length < 8}
                      onClick={() => void act("reject", row)}
                    >
                      ارفض
                    </Button>
                  </div>
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => setOpen(null)}
                  >
                    تراجع
                  </Button>
                </div>
              ) : (
                <Button
                  className="mt-12 w-full"
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

      <p className="mt-16 text-11 leading-note text-muted">
        الأرقام لاتينية عمداً: المرجع يُطابَق حرفاً بحرف مع كشف حسابك،
        وتحويلُ خاناته يجعلك تقارن نصّاً بشكلٍ آخر.
      </p>
    </div>
  );
}
