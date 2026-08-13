/** طلبات السحب — SPEC القسم 9، وشكلُها من `DESIGN.md` §5.3.
 *
 * أربعُ حالاتٍ لا اثنتان، والفرقُ بينها فرقٌ في **أين المال الآن**:
 *
 * | الحال | ما يعنيه للكبتن |
 * |---|---|
 * | معلّق | حُجز المبلغ من المتاح، ولا قيد في الدفتر بعد |
 * | موافَق عليه | وافقت الإدارة، والمال لم يُحوَّل بعد — الحجز قائم |
 * | مدفوع | حُوِّل، **وهنا وحده يُكتب قيد `withdrawal`** في الدفتر |
 * | مرفوض | أُفرج عن المحجوز وعاد إلى المتاح |
 *
 * فالشاشةُ تقول ذلك صراحةً في حاشيتها: من يرى «موافَق عليه» ولا يرى المال في
 * بنكه يظن أن شيئاً ضاع، وهو في الطريق.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { listWithdrawals } from "@/api/endpoints";
import type { Withdrawal } from "@/api/types";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import {
  WITHDRAWAL_METHOD_LABEL,
  WITHDRAWAL_STATUS_LABEL,
  withdrawalTone,
} from "@/lib/walletFormat";
import { arabicDigits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

const PAGE_SIZE = 20;

/** لونُ الشريط الجانبي هو لونُ الحال نفسه — خلفيةً هنا ونصّاً هناك. */
const BAR_TONE: Record<Withdrawal["status"], string> = {
  pending: "bg-warn",
  approved: "bg-warn",
  paid: "bg-ok",
  rejected: "bg-danger",
};

export function WithdrawalsScreen() {
  const goBack = useGoBack();
  // العملةُ ليست حقلاً على طلب السحب — تُقرأ من دولة الكبتن كما يشتقّها
  // `currency_for_country` في الخلفية، ولا تُخمَّن ولا تُكتب في الواجهة
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);
  const currency = country ? CURRENCY_LABEL[country.currency] : "";
  const [requests, setRequests] = useState<Withdrawal[] | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (offset: number) => {
    setBusy(true);
    try {
      const page = await listWithdrawals(PAGE_SIZE, offset);
      setRequests((current) =>
        offset === 0 ? page : [...(current ?? []), ...page],
      );
      setMore(page.length === PAGE_SIZE);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الطلبات",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
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
        <h1 className="text-20 font-bold text-ink">طلبات السحب</h1>
      </div>

      <ErrorNote message={error} />

      {requests === null && !error ? <Spinner className="mx-auto" /> : null}

      {requests?.length === 0 ? (
        <EmptyNote
          title="لا طلبات سحب"
          hint="اطلب سحباً من المحفظة، وتتبّع حاله هنا حتى يصلك المال."
        />
      ) : null}

      <Stagger className="flex flex-col gap-9">
        {(requests ?? []).map((request) => (
          <StaggerItem
            key={request.id}
            className="flex items-center gap-12 rounded-15 border border-line bg-surface px-14 py-13"
          >
            <span
              className={cn(
                "block h-34 w-6 flex-none rounded-4",
                BAR_TONE[request.status],
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="text-14 font-bold text-ink">
                {arabicDigits(request.amount)} {currency}
              </div>
              <div className="text-11 text-muted">
                {formatWhen(request.created_at)} ·{" "}
                {WITHDRAWAL_METHOD_LABEL[request.method]}
              </div>
              {/* سببُ الرفض أو مرجعُ الحوالة — ما كتبته الإدارة على الصف */}
              {request.note ? (
                <div className="mt-3 text-11 leading-snug text-muted">
                  {request.note}
                </div>
              ) : null}
              {request.reference ? (
                <div className="mt-3 text-11 text-muted">
                  مرجع التحويل{" "}
                  <span dir="ltr" className="text-ink">
                    {request.reference}
                  </span>
                </div>
              ) : null}
            </div>
            <span
              className={cn(
                "text-11.5 font-bold",
                withdrawalTone(request.status),
              )}
            >
              {WITHDRAWAL_STATUS_LABEL[request.status]}
            </span>
          </StaggerItem>
        ))}
      </Stagger>

      {more ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void load(requests?.length ?? 0)}
          className="pressable mt-12 w-full rounded-14 border border-line py-13 text-center text-12.5 font-semibold text-muted disabled:opacity-60"
        >
          {busy ? "…" : "عرض المزيد"}
        </button>
      ) : null}

      <p className="mt-14 text-11.5 leading-note text-muted">
        الطلب المعلّق يحجز مبلغه من الرصيد المتاح، وقيد السحب يُكتب عند الدفع
        فقط.
      </p>
    </div>
  );
}
