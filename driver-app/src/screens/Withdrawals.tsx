/** طلبات السحب — TAXO 2.0 «C20» (`design/t2-new/captain/C20-withdrawals.dc.html`) — SPEC القسم 9، **في المظهرين والنسائيّ**.
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
 * فالشاشةُ تقول ذلك صراحةً في حاشيتها: من يرى «موافَق عليه» ولا يرى المال في بنكه يظن أن شيئاً ضاع، وهو في الطريق.
 *
 * **والطلبُ هو هو** (`GET /wallet/me/withdrawals` بصفحاتٍ من عشرين و«عرض المزيد»). **وما تغيّر طبقةُ العرض**: صفُّ الوثائق C12 —
 * **ولونُ الحال في مربّع الأيقونة وشارتِه** بدل الشريط الجانبيّ، بالنبرة نفسِها (`withdrawalTone`): الكهرمانُ لما يحجز، والأخضرُ لما
 * دُفع، والأحمرُ لما رُفض.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listWithdrawals } from "@/api/endpoints";
import type { Withdrawal } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import {
  WITHDRAWAL_METHOD_LABEL,
  WITHDRAWAL_STATUS_LABEL,
  withdrawalTone,
} from "@/lib/walletFormat";
import { digits } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import { startOfToday, whenParts } from "./t2/when";

import "./t2/money.css";

const PAGE_SIZE = 20;

/** **نبرةُ الحال من قاعدتها الواحدة** (`withdrawalTone`) — لونُ الشارة ومربّعِ الأيقونة. */
const TONE: Record<string, "ok" | "warn" | "danger"> = {
  "text-ok": "ok",
  "text-warn": "warn",
  "text-danger": "danger",
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

  const today = startOfToday();

  return (
    <div className="t2 t2-wdl scr">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => goBack()}
        >
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">طلبات السحب</h1>
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}

      {requests === null && !error ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : null}

      {requests?.length === 0 ? (
        <div className="t2-empty t2-money-empty">
          <b>لا طلبات سحب</b>
          <span>اطلب سحباً من المحفظة، وتتبّع حاله هنا حتى يصلك المال.</span>
        </div>
      ) : null}

      {requests && requests.length > 0 ? (
        <div className="t2-wdl-list">
          {requests.map((request) => {
            const tone = TONE[withdrawalTone(request.status)] ?? "warn";
            const when = whenParts(request.created_at, today);
            return (
              <div key={request.id} className="t2-wdl-card">
                <div className="t2-wdl-row">
                  <span className={`t2-wdl-icon ${tone}`} aria-hidden="true">
                    <Icon name="south_west" />
                  </span>
                  <span className="t2-wdl-main">
                    <span className="t2-wdl-amount">
                      <span dir="ltr">{digits(request.amount)}</span> {currency}
                    </span>
                    <span className="t2-wdl-sub">
                      {digits(when.day)} ·{" "}
                      <span dir="ltr">{digits(when.time)}</span> ·{" "}
                      {WITHDRAWAL_METHOD_LABEL[request.method]}
                    </span>
                  </span>
                  <span className={`t2-chip ${tone}`}>
                    {WITHDRAWAL_STATUS_LABEL[request.status]}
                  </span>
                </div>
                {/* سببُ الرفض أو مرجعُ الحوالة — ما كتبته الإدارة على الصف */}
                {request.note ? (
                  <p className="t2-wdl-note">{request.note}</p>
                ) : null}
                {request.reference ? (
                  <p className="t2-wdl-ref">
                    مرجع التحويل{" "}
                    <span dir="ltr" className="t2-wdl-ref-code">
                      {request.reference}
                    </span>
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {more ? (
        <button
          type="button"
          className="t2-more t2-money-more"
          disabled={busy}
          onClick={() => void load(requests?.length ?? 0)}
        >
          {busy ? "…" : "عرض المزيد"}
        </button>
      ) : null}

      <p className="t2-wdl-fine">
        الطلب المعلّق يحجز مبلغه من الرصيد المتاح، وقيد السحب يُكتب عند الدفع
        فقط.
      </p>
    </div>
  );
}
