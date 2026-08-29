/** **شحنُ محفظة الكبتن بكليك — يدوياً** (قرارُ المالك 2026-08-29).
 *
 * **ولمَ وُجدت أصلاً**: محفظةُ الكبتن **مصرفٌ لا صندوق** — تدخلها أجرتُه ولا
 * يشحنها. فالكبتنُ الجديدُ محفظتُه صفرٌ ولا يشترك، **والاشتراكُ شرطُ العمل**.
 * فهذا **بابُ دخولٍ مغلق** لا وسيلةٌ إضافية.
 *
 * **والبابُ هو بابُ الراكب نفسُه** (`POST /wallet/me/topups`) — لا ثانيَ له.
 * كان يقبل `CurrentUser` منذ نشأته، **والمانعُ كان هذه الشاشةَ الغائبة**.
 *
 * **والمحفظةُ مُعلَنةٌ في المسار** (`?wallet=driver`) لا مشتقّةٌ من دور: حاملُ
 * الدورين يعلن بسياق فعله (SPEC §22).
 *
 * **والحسابُ من الإعداد لا من نصٍّ مكتوبٍ هنا**: `cliq_alias` لكلِّ سوقٍ يُضبط
 * من اللوحة — **فتعديلُ حسابٍ يستقبل مالَ الناس لا يكون نشراً**. ومن لا حسابَ
 * لسوقه لا يصل هذه الشاشةَ أصلاً (الزرُّ لا يُرسم).
 *
 * **ولا رصيدَ يتغيّر هنا**: هذا طلبٌ ينتظر أن يقرأ المشرفُ كشفَه ويؤكّد
 * **بالمبلغ الذي وصل فعلاً** — ودعوى المستخدم تُقرأ ولا تُصرف. ولذلك تقول
 * الشاشةُ «بانتظار التأكيد» ولا تَعِد بشيء.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { createTopupRequest, listMyTopups } from "@/api/endpoints";
import type { TopupRequest } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useCountryConfig } from "@/lib/config";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const STATUS_TEXT: Record<TopupRequest["status"], string> = {
  pending: "بانتظار التأكيد",
  confirmed: "مؤكَّد",
  rejected: "مرفوض",
};

const STATUS_TONE: Record<TopupRequest["status"], string> = {
  pending: "text-warn",
  confirmed: "text-ok",
  rejected: "text-danger",
};

export function TopupScreen() {
  const goBack = useGoBack("/wallet");
  const { user } = useSession();
  const config = useCountryConfig(user?.country_code);
  const alias = config?.cliq_alias ?? null;

  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [rows, setRows] = useState<TopupRequest[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await listMyTopups());
  }, []);

  useEffect(() => {
    load().catch(() => setRows([]));
  }, [load]);

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">شحن المحفظة</h1>
      </div>
      {/* **الحسابُ أولاً**: هو ما يُنسخ ويُحوَّل إليه — فيُعرض كبيراً وبـ`ltr`
          كما يُكتب في تطبيق البنك، لا مدفوناً في نصّ */}
      {alias ? (
        <section className="mb-12 rounded-20 border border-line bg-surface p-20">
          <div className="text-12 text-muted">حوّل إلى حساب كليك</div>
          <div
            dir="ltr"
            className="mt-4 select-all text-24 font-bold leading-hero text-ink"
          >
            {alias}
          </div>
          <p className="mt-8 text-11.5 leading-note text-muted">
            حوّل المبلغ من تطبيق بنكك إلى هذا الحساب، ثم سجّل الطلب هنا بالمبلغ
            والمرجع. يُراجعه مشرفٌ ويؤكّده بعد أن يصل المال.
          </p>
        </section>
      ) : null}

      <section className="mb-12 rounded-20 border border-line bg-surface p-20">
        <Field
          label="المبلغ"
          name="amount"
          dir="ltr"
          inputMode="decimal"
          value={amount}
          onChange={(event) =>
            setAmount(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        <div className="mt-12">
          <Field
            label="مرجع التحويل"
            name="reference"
            dir="ltr"
            placeholder="رقمُ العملية في تطبيق بنكك"
            value={reference}
            maxLength={64}
            onChange={(event) => setReference(event.target.value)}
          />
        </div>
        {/* **المرجعُ هو كلُّ ما تملكه الإدارةُ للمطابقة** — فيُقال لمَ يُطلب،
            ولا يُترك حقلاً يُملأ بلا معنى */}
        <p className="mt-8 text-11 leading-note text-muted">
          المرجعُ هو ما يُطابَق به تحويلُك في كشف الحساب — بدونه لا يُؤكَّد
          الطلب.
        </p>

        <ErrorNote message={error} />
        <SuccessNote message={done} />

        <Button
          className="mt-16 w-full"
          loading={busy}
          disabled={Number(amount) <= 0 || reference.trim().length < 3}
          onClick={() => {
            setBusy(true);
            setError(null);
            setDone(null);
            createTopupRequest(amount.trim(), reference.trim())
              .then(() => {
                setAmount("");
                setReference("");
                setDone("سُجّل الطلب — بانتظار تأكيد المشرف بعد وصول المال");
                return load();
              })
              .catch((caught: unknown) =>
                setError(
                  caught instanceof ApiError
                    ? caught.message
                    : "تعذّر تسجيل الطلب",
                ),
              )
              .finally(() => setBusy(false));
          }}
        >
          سجّل الطلب
        </Button>
      </section>

      <section className="rounded-20 border border-line bg-surface p-20">
        <div className="mb-12 text-13.5 font-bold text-ink">طلباتك</div>
        {rows === null ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <p className="text-12 leading-note text-muted">
            لا طلباتِ شحنٍ بعد.
          </p>
        ) : (
          <ul className="flex flex-col gap-10">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex items-baseline justify-between border-b border-line pb-10 last:border-0 last:pb-0"
              >
                <span className="min-w-0">
                  <span className="block text-13.5 font-semibold text-ink">
                    {digits(row.amount)} {CURRENCY_LABEL[row.currency]}
                  </span>
                  <span dir="ltr" className="block text-11 text-muted">
                    {row.reference ?? "—"}
                  </span>
                </span>
                <span className={`text-11.5 font-semibold ${STATUS_TONE[row.status]}`}>
                  {STATUS_TEXT[row.status]}
                  {/* **المرفوضُ يقول لماذا** — رفضٌ بلا سببٍ يُقرأ عطباً
                      ويُعاد الطلبُ كما هو */}
                  {row.status === "rejected" && row.note ? (
                    <span className="mt-2 block text-11 font-normal text-muted">
                      {row.note}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
        {rows !== null && rows.length > 0 ? (
          <p className="mt-12 text-11 leading-note text-muted">
            المؤكَّدُ دخل رصيدَك، والمعلّقُ لم يدخل بعد —{" "}
            {digits(String(rows.filter((r) => r.status === "pending").length))}{" "}
            بانتظار التأكيد.
          </p>
        ) : null}
      </section>
    </div>
  );
}
