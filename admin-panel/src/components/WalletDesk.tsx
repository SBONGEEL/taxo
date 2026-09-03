/** تصحيحُ الدفتر والشحنُ الإداريّ — **بابان كانا بلا زرّ** (قرارُ المالك 2026-08-19).
 *
 * **وأخطرُهما التصحيح**: `wallet_transactions` عليها مُطلِقٌ في القاعدة يرفض
 * `UPDATE` و`DELETE` (هجرة `0006`) — فدفترٌ لا يُعدَّل بلا مخرجِ تصحيحٍ يعني
 * **قيداً خاطئاً يبقى أبداً**. والمخرجُ قيدٌ مضادٌّ لا محوٌ للتاريخ، وهو في
 * الخلفية منذ المرحلة ٥ ولم يصل إليه زرٌّ قط.
 *
 * والسببُ إلزاميٌّ في البابين ويدخل سجلَّ التدقيق: حركةُ مالٍ يقرّرها إنسانٌ بلا
 * «لماذا» صفٌّ نصفُه ناقص. **وقيمةُ المبلغ لا تدخل `details`** — أسماءُ الحقول
 * وحدَها (SPEC القسم ١٤)، والمبلغُ في القيد نفسِه.
 */

import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createStaffTopup,
  createWalletAdjustment,
  listUsers,
} from "@/api/endpoints";
import type { User, WalletOwnerType } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { SuccessNote } from "@/components/ui/Feedback";
import { MoneyField } from "@/components/ui/Inputs";
import { Picker, type PickerOption } from "@/components/ui/Picker";
import { useCountry } from "@/lib/country";
import { currencyOf } from "@/lib/format";
import { digits } from "@/lib/utils";

/** مبلغٌ نصّاً: المالُ لا يمرّ بـ`Number` (SPEC §14). والسالبُ مسموحٌ هنا وحدَه. */
function amountText(raw: string): string {
  const cleaned = raw.replace(/[^0-9.-]/g, "");
  const negative = cleaned.startsWith("-");
  return (negative ? "-" : "") + cleaned.replace(/-/g, "");
}

export function WalletDesk({ onError }: { onError: (m: string) => void }) {
  const { country } = useCountry();
  const [picked, setPicked] = useState<User | null>(null);

  /** **صفوفُ آخر بحثٍ بمعرّفها** — `Picker` يردّ سطرَ عرضٍ (معرّفٌ واسمٌ
   *  وتمييز)، **وهذه الشاشةُ تحتاج الصفَّ كلَّه**: `roles` هي ما يقرّر
   *  أبمحفظتين هو أم بواحدة، **ونداءٌ ثانٍ يقرأ الحسابَ بمعرّفه كان يضيف
   *  رحلةً على السلك بلا خبرٍ جديد**. */
  const rowsById = useRef(new Map<string, User>());

  // **`useCallback` لأن `Picker` يضعها في تبعيّات `useEffect`.**
  const findUsers = useCallback(
    (query: string) =>
      listUsers({ q: query, country_code: country, limit: 10 }).then((rows) => {
        rowsById.current = new Map(rows.map((row) => [row.id, row]));
        return rows.map((row) => ({
          id: row.id,
          label: row.name,
          hint: digits(row.phone),
        }));
      }),
    [country],
  );

  /** **أيَّ محفظةٍ يصحّح** — يُسأل عنها **فقط** لحاملِ الدورين. وصاحبُ دورٍ
   *  واحدٍ لا محفظةَ ثانيةَ له، فالسؤالُ احتكاكٌ بلا قرار. */
  const [adjustWallet, setAdjustWallet] = useState<WalletOwnerType | "">("");

  function pick(option: PickerOption | null) {
    setPicked(option ? (rowsById.current.get(option.id) ?? null) : null);
    // **وحالُ المحفظة تُصفَّر مع كلِّ تبديلِ حساب**: اختيارٌ بقي من حسابٍ سابقٍ
    // يكتب قيداً على محفظةٍ لم يقصدها المشرف
    setAdjustWallet("");
  }

  /** **بمحفظتين أم بواحدة** — تُقرأ من الأدوار المنشورة لا من `role` وحدَه:
   *  العمودُ القديمُ يقول دوراً واحداً حتى لمن يحمل اثنين (نموذجُ الأدوار §21). */
  const dualWallet =
    (picked?.roles ?? []).includes("rider") &&
    (picked?.roles ?? []).includes("driver");

  const [adjustAmount, setAdjustAmount] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const [topupAmount, setTopupAmount] = useState("");
  const [topupReference, setTopupReference] = useState("");
  const [busy, setBusy] = useState<"adjust" | "topup" | null>(null);
  const [done, setDone] = useState<string | null>(null);

  function fail(caught: unknown, fallback: string) {
    onError(caught instanceof ApiError ? caught.message : fallback);
  }

  return (
    <div className="grid gap-16">
      <section className="rounded-16 border border-line bg-surface p-16">
        <h3 className="mb-4 text-13.5 font-bold text-ink">اختر صاحبَ المحفظة</h3>
        <p className="mb-10 text-11.5 leading-note text-muted">
          بالاسم أو الرقم، وداخل السوق المعروض وحدَه.
        </p>
        <Picker
          label="بحث"
          value={
            picked
              ? { id: picked.id, label: picked.name, hint: digits(picked.phone) }
              : null
          }
          onPick={pick}
          search={findUsers}
          emptyText="لا حسابَ بهذا الاسم أو الرقم في هذا السوق."
        />
      </section>

      {done ? <SuccessNote message={done} /> : null}

      {picked ? (
        <div className="grid gap-16 md:grid-cols-2">
          <section className="rounded-16 border border-line bg-surface p-16">
            <h3 className="mb-4 text-13.5 font-bold text-ink">قيدُ تصحيح</h3>
            <p className="mb-10 text-11.5 leading-note text-muted">
              موجبٌ أو سالب. <b className="text-ink">والدفترُ لا يُعدَّل</b>: هذا
              قيدٌ جديدٌ مضادّ لا محوٌ لما سبق. وسالبٌ يتجاوز الرصيد يُرفض —
              الرصيدُ لا يقلّ عن صفرٍ بقيدٍ في القاعدة نفسِها.
            </p>
            <div className="grid gap-10">
              <MoneyField
                label="المبلغ (بالسالب للخصم)"
                value={adjustAmount}
                // **والمصفاةُ باقيةٌ كما كانت**: `MoneyField` يعرض العملةَ
                // ويصوغ الصفرَ، **ولا يمنع حرفاً** — ونزعُ `amountText` كان
                // يفتح باباً لنصٍّ يصل الخلفيةَ رقماً مالياً
                onChange={(next) => setAdjustAmount(amountText(next))}
                currency={currencyOf(country)}
              />
              <Field
                label="السبب (إلزاميّ — يدخل سجلّ التدقيق)"
                value={adjustReason}
                onChange={(event) => setAdjustReason(event.target.value)}
              />
              {dualWallet ? (
                <Select
                  label="المحفظة (الحساب يحمل الدورين)"
                  value={adjustWallet}
                  onChange={(event) =>
                    setAdjustWallet(event.target.value as WalletOwnerType | "")
                  }
                >
                  <option value="">اختر المحفظة…</option>
                  <option value="driver">محفظة الكبتن — أرباحٌ وسلَفٌ وعمولة</option>
                  <option value="rider">محفظة الراكب — ما شحنه لرحلاته</option>
                </Select>
              ) : null}
              {dualWallet ? (
                <p className="text-11 leading-note text-muted">
                  <b className="text-ink">لهذا الحساب محفظتان</b>، والقيدُ لا
                  يُمحى — فاختيارُها قرارُك لا استنتاجُ النظام.
                </p>
              ) : null}
              <Button
                size="sm"
                loading={busy === "adjust"}
                disabled={
                  adjustReason.trim().length < 3 ||
                  adjustAmount === "" ||
                  adjustAmount === "-" ||
                  (dualWallet && adjustWallet === "")
                }
                onClick={() => {
                  setBusy("adjust");
                  setDone(null);
                  createWalletAdjustment(picked.id, {
                    amount: adjustAmount,
                    reason: adjustReason.trim(),
                    // **لا تُرسل لصاحب الدور الواحد**: الخلفيةُ تشتقّها،
                    // وإرسالُ قيمةٍ لا يملكها الحسابُ يرتدّ بحقّ
                    ...(dualWallet && adjustWallet
                      ? { wallet: adjustWallet }
                      : {}),
                  })
                    .then(() => {
                      // **يقول ماذا وقع بالضبط** (§39٫١٢٫٥): قيدٌ مضادٌّ لمن،
                      // **ولا محوَ لما سبق** — وهو ما يخطئ فيه من يقرأ «تمّ»
                      setDone(
                        `كُتب قيدُ تصحيحٍ على حساب ${picked.name} — قيدٌ مضادٌّ لا محوٌ لما سبق`,
                      );
                      setAdjustAmount("");
                      setAdjustReason("");
                      setAdjustWallet("");
                    })
                    .catch((caught) => fail(caught, "تعذّر القيد"))
                    .finally(() => setBusy(null));
                }}
              >
                اكتب القيد
              </Button>
            </div>
          </section>

          <section className="rounded-16 border border-line bg-surface p-16">
            <h3 className="mb-4 text-13.5 font-bold text-ink">شحنٌ إداريّ (كاش)</h3>
            <p className="mb-10 text-11.5 leading-note text-muted">
              من نقطةٍ معتمدةٍ قُبض فيها المالُ بيدٍ سلفاً —{" "}
              <b className="text-ink">يُنشأ ويُؤكَّد معاً</b>، فالرصيدُ يتحرك الآن.
              والمرجعُ إلزاميٌّ لأنه ما يُطابَق به الإيصالُ الورقيُّ بعد شهر.
            </p>
            <div className="grid gap-10">
              <MoneyField
                label="المبلغ"
                value={topupAmount}
                // **موجبٌ وحدَه هنا** — الشحنُ لا يخصم، والمصفاةُ كما كانت
                onChange={(next) => setTopupAmount(next.replace(/[^0-9.]/g, ""))}
                currency={currencyOf(country)}
              />
              <Field
                label="مرجعُ الإيصال (إلزاميّ)"
                value={topupReference}
                onChange={(event) => setTopupReference(event.target.value)}
              />
              <Button
                size="sm"
                loading={busy === "topup"}
                disabled={topupAmount === "" || topupReference.trim().length < 3}
                onClick={() => {
                  setBusy("topup");
                  setDone(null);
                  createStaffTopup(picked.id, {
                    amount: topupAmount,
                    reference: topupReference.trim(),
                  })
                    .then(() => {
                      setDone(
                        `شُحنت محفظةُ ${picked.name} وأُكِّدت — الرصيدُ تحرّك الآن`,
                      );
                      setTopupAmount("");
                      setTopupReference("");
                    })
                    .catch((caught) => fail(caught, "تعذّر الشحن"))
                    .finally(() => setBusy(null));
                }}
              >
                اشحن وأكِّد
              </Button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
