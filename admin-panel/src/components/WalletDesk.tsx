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

import { useState } from "react";

import { ApiError } from "@/api/client";
import {
  createStaffTopup,
  createWalletAdjustment,
  listUsers,
} from "@/api/endpoints";
import type { User } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { EmptyNote, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { digits } from "@/lib/utils";

/** مبلغٌ نصّاً: المالُ لا يمرّ بـ`Number` (SPEC §14). والسالبُ مسموحٌ هنا وحدَه. */
function amountText(raw: string): string {
  const cleaned = raw.replace(/[^0-9.-]/g, "");
  const negative = cleaned.startsWith("-");
  return (negative ? "-" : "") + cleaned.replace(/-/g, "");
}

export function WalletDesk({ onError }: { onError: (m: string) => void }) {
  const { country } = useCountry();
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<User[] | null>(null);
  const [picked, setPicked] = useState<User | null>(null);

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
        <div className="flex items-end gap-10">
          <Field
            className="flex-1"
            label="بحث"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setFound(null);
              setPicked(null);
              listUsers({ q: query.trim(), country_code: country, limit: 10 })
                .then(setFound)
                .catch((caught) => fail(caught, "تعذّر البحث"));
            }}
          >
            ابحث
          </Button>
        </div>

        {found?.length === 0 ? (
          <EmptyNote
            title="لا نتائج"
            hint="لا حسابَ بهذا الاسم أو الرقم في هذا السوق."
          />
        ) : null}
        {found && found.length > 0 ? (
          <ul className="mt-12 grid gap-6">
            {found.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => setPicked(row)}
                  className={
                    "flex w-full items-center justify-between rounded-12 border px-12 py-8 text-start " +
                    (picked?.id === row.id
                      ? "border-ink bg-surface-2"
                      : "border-line")
                  }
                >
                  <span className="text-12.5 text-ink">{row.name}</span>
                  <span className="text-11.5 text-muted" dir="ltr">
                    {digits(row.phone)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
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
              <Field
                label="المبلغ (بالسالب للخصم)"
                dir="ltr"
                value={adjustAmount}
                onChange={(event) =>
                  setAdjustAmount(amountText(event.target.value))
                }
              />
              <Field
                label="السبب (إلزاميّ — يدخل سجلّ التدقيق)"
                value={adjustReason}
                onChange={(event) => setAdjustReason(event.target.value)}
              />
              <Button
                size="sm"
                loading={busy === "adjust"}
                disabled={
                  adjustReason.trim().length < 3 ||
                  adjustAmount === "" ||
                  adjustAmount === "-"
                }
                onClick={() => {
                  setBusy("adjust");
                  setDone(null);
                  createWalletAdjustment(picked.id, {
                    amount: adjustAmount,
                    reason: adjustReason.trim(),
                  })
                    .then(() => {
                      setDone("كُتب قيدُ التصحيح");
                      setAdjustAmount("");
                      setAdjustReason("");
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
              <Field
                label="المبلغ"
                dir="ltr"
                value={topupAmount}
                onChange={(event) =>
                  setTopupAmount(event.target.value.replace(/[^0-9.]/g, ""))
                }
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
                      setDone("سُجّل الشحنُ وأُكِّد");
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
