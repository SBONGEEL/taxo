/** سجلُّ الرحلات — TAXO 2.0 «C16» (`design/t2-new/captain/C16-rides.dc.html`) — SPEC القسم 12/6، **في المظهرين والنسائيّ**.
 *
 * «للكبتن ما أُسند إليه» — الخلفية تفصل ذلك، والشاشة لا تفلتر بيدها.
 *
 * **الطلبُ هو هو**: `GET /rides/me?side=driver` بصفحاتٍ من عشرين و«عرض المزيد»، والنقرُ إلى `/rides/:id`. **وما تغيّر طبقةُ
 * العرض وحدَها**: العنوانُ الكبير، والتجميعُ بالشهر، وبطاقةُ «رحلاتي» R12 بلغة الإسفلت — الوقتُ والشاراتُ فوق، والنقطتان، ثمّ
 * الفئةُ والمسافةُ والقناةُ والأجرة. **والفئةُ والقناةُ من الصفّ نفسِه** (`vehicle_category` · `payment_methods`) — كانتا تصلان ولا تُرسمان.
 *
 * **وبابُ الاعتراض في السجلّ** (§٦١-ب/٣ — والسجلُّ «يبقى، ومعه زرُّ الاعتراض»): الصفُّ الذي ينتظر تأكيدَك (`settlement ===
 * "awaiting"`) يُرسم بالجمر الخافت وفي ذيله ما يُفعل — **والبطاقةُ كلُّها زرٌّ واحدٌ إلى التفاصيل** حيث «وصلتني» و«لم تصلني» معاً
 * (`RideDetails`)، أو «استلمت المبلغ كاش» للكاش. **ولا زرَّ «لم تصلني» وحدَه هنا**: شاشةٌ تعرض الاعتراضَ وحدَه تُملي على الكبتن
 * الجوابَ الذي لم يقله، والتأكيدُ فعلُ مالٍ لا يُنقل إلى صفٍّ عابر — **فمسارُ الاعتراض هو هو** (`/rides/:id` ← `/rides/:id/dispute`).
 *
 * **وشارةُ النزاع في القائمة** (`FUTURE-FEATURES` بند 19). كانت غائبةً لأن حالَ الدفع تعيش على `payments` و`GET /rides/me` لا
 * يحملها، وسؤالُ الخلفية عن دفعات كل صفٍّ عشرون نداءً لصفحةٍ واحدة. فصار المسارُ يضمّ الملخّصَ **في استعلامٍ ثانٍ لصفحةٍ كاملة**.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { RideListItem, RideStatus } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import {
  CATEGORY_LABEL,
  CURRENCY_LABEL,
  METHOD_LABEL,
  RIDE_STATUS_LABEL,
  statusTone,
  trimDistance,
} from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import { byMonth, startOfToday, whenParts } from "./t2/when";

import "./t2/rides.css";

/** حدُّ الخلفية 100، وصفحةٌ من عشرين تكفي شاشةً وتترك «المزيد» صادقاً. */
const PAGE_SIZE = 20;

/** **نبرةُ شارة الحال من قاعدتها الواحدة** (`statusTone`): المكتملةُ خضراء، والملغاةُ وما لم يُقبل حمراء، وما عداها كهرمان. */
const CHIP_TONE: Record<string, "ok" | "warn" | "danger"> = {
  "text-ok": "ok",
  "text-warn": "warn",
  "text-danger": "danger",
};
export function chipTone(status: RideStatus): "ok" | "warn" | "danger" {
  return CHIP_TONE[statusTone(status)] ?? "warn";
}

/** رحلةٌ لم تُخدَم — نقاطُها خافتة، **ولا أجرةَ عليها** كما في R12. */
function unserved(status: RideStatus): boolean {
  return status.startsWith("cancelled") || status === "no_driver_found";
}

export function RidesScreen() {
  const navigate = useNavigate();
  const [rides, setRides] = useState<RideListItem[] | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (offset: number) => {
    setBusy(true);
    try {
      const page = await listMyRides(PAGE_SIZE, offset);
      setRides((current) =>
        offset === 0 ? page : [...(current ?? []), ...page],
      );
      // صفحةٌ ممتلئةٌ تماماً تعني «قد يكون بعدها المزيد» — والسؤالُ التالي
      // وحده يحسم، فالخلفية لا تردّ عدداً كلياً
      setMore(page.length === PAGE_SIZE);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة السجل",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  const today = startOfToday();
  const months = byMonth(rides ?? [], (item) => item.ride.created_at);

  return (
    <div className="t2 t2-log scr">
      <h1 className="t2-h1">سجل الرحلات</h1>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}

      {rides === null && !error ? (
        <div className="t2-log-wait">
          <Spinner />
        </div>
      ) : null}

      {rides?.length === 0 ? (
        <div className="t2-empty t2-log-empty">
          <b>لا رحلات بعد</b>
          <span>ستظهر هنا كل رحلةٍ أنهيتَها، بأجرتها وتفصيلها.</span>
        </div>
      ) : null}

      {months.map((month) => (
        <section key={month.label} className="t2-log-month">
          <h2 className="t2-log-month-title">{digits(month.label)}</h2>
          <div className="t2-log-cards">
            {month.items.map((item) => (
              <RideCard
                key={item.ride.id}
                item={item}
                today={today}
                onOpen={() => navigate(`/rides/${item.ride.id}`)}
              />
            ))}
          </div>
        </section>
      ))}

      {more ? (
        <button
          type="button"
          className="t2-more t2-log-more"
          disabled={busy}
          onClick={() => void load(rides?.length ?? 0)}
        >
          {busy ? "…" : "عرض المزيد"}
        </button>
      ) : null}
    </div>
  );
}

function RideCard({
  item,
  today,
  onOpen,
}: {
  item: RideListItem;
  today: number;
  onOpen: () => void;
}) {
  const { ride, has_open_dispute, payment_methods, settlement } = item;
  const when = whenParts(ride.created_at, today);
  const off = unserved(ride.status);
  // **مالٌ لم يُقفل بعد** — كشفته تجربةُ المرحلة ١٣: بعد إعادة فتح التطبيق يختفي كلُّ ما يدلّ على رحلةٍ تنتظر تأكيدَه، فيبقى
  // المالُ في يده والدفعةُ `pending` بلا أن يعرف. **والحكمُ يصل محسوباً** (`settlement`) من `services/settlement.py`
  const awaiting = settlement === "awaiting";
  // **ما ينتظره كليك أم كاش** — من قنوات الصفّ كما وصلت: النزاعُ على كليك وحدها (`dispute_by_driver`)، والكاشُ يُؤكَّد ولا يُعترض عليه
  const viaCliq = payment_methods.includes("cliq");
  // «نسائية» مكانَ الفئة كما في R12 — **وصفٌ للطلب لا لصاحبته**
  const kind =
    ride.gender_preference === "female"
      ? "نسائية"
      : CATEGORY_LABEL[ride.vehicle_category];
  const meta = [
    kind,
    `${trimDistance(ride.actual_distance_km ?? ride.distance_km)} كم`,
    payment_methods.length > 0
      ? payment_methods.map((method) => METHOD_LABEL[method]).join(" + ")
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      className={awaiting ? "t2-log-card awaiting" : "t2-log-card"}
      onClick={onOpen}
    >
      <span className="t2-log-top">
        <span className="t2-log-when">
          {digits(when.day)} · <span dir="ltr">{digits(when.time)}</span>
        </span>
        <span className="t2-log-chips">
          {settlement === "due" || awaiting ? (
            // **«بانتظار تأكيدك» غيرُ «لم تُدفع»**: الأولى صفُّ دفعةٍ ينتظر ضغطتَه هو، والثانيةُ راكبٌ لم يختر بعد —
            // وعليه في الأولى عملٌ وليس عليه في الثانية شيء. وخلطُهما يجعله يفتش عن زرٍّ لا وجودَ له
            <span className="t2-chip warn">
              {awaiting ? "بانتظار تأكيدك" : "لم تُدفع"}
            </span>
          ) : null}
          {has_open_dispute ? (
            <span className="t2-chip warn">نزاع</span>
          ) : null}
          <span className={`t2-chip ${chipTone(ride.status)}`}>
            {RIDE_STATUS_LABEL[ride.status]}
          </span>
        </span>
      </span>

      <span className={off ? "t2-log-route off" : "t2-log-route"}>
        <span className="t2-log-dot" aria-hidden="true" />
        <span className="t2-log-place">
          {ride.pickup_address ?? "نقطة الانطلاق"}
        </span>
        <span className="t2-log-dot to" aria-hidden="true" />
        <span className="t2-log-place">{ride.dropoff_address ?? "الوجهة"}</span>
      </span>

      <span className="t2-log-foot">
        <span>{meta}</span>
        {/* **ولا أجرةَ على رحلةٍ لم تُخدَم** كما في R12 — وما لم تُقفل أجرتُه بعدُ «—» كما كان */}
        {off ? null : (
          <span className="t2-log-fare">
            {ride.final_fare ? (
              <>
                <span dir="ltr">{digits(ride.final_fare)}</span>{" "}
                {CURRENCY_LABEL[ride.currency]}
              </>
            ) : (
              "—"
            )}
          </span>
        )}
      </span>

      {awaiting ? (
        <span className="t2-log-act">
          <Icon name={viaCliq ? "balance" : "payments"} />
          <span className="t2-log-act-text">
            {viaCliq
              ? "وصلتك الحوالة؟ أكّد أو اعترض"
              : "استلمتَ المبلغ كاش؟ أكّد استلامه"}
          </span>
          <Icon name="chevron_left" />
        </span>
      ) : null}
    </button>
  );
}
