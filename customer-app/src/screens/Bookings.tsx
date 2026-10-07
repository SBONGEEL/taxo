/** رحلاتي المجدولة — TAXO 2.0 «R26» (`design/t2-new/rider/R26-bookings.dc.html` · `R26b-…`)، **في المظهرين والنسائيّ** —
 *  بطاقةُ «مجدولة» في R12 بعينها لما ينتظر موعده، والبيضاءُ بشارة حالها لما مضى (SPEC القسم 5.11، المرحلة 12-ط).
 *
 * **وجملةُ الحال تُبنى هنا من حقيقتين**: حالِ الحجز وحالِ رحلته. فلا عمودَ
 * `fulfilled` في الخلفية يقول ذلك — ما جرى بعد التسليم تقوله الرحلةُ نفسُها،
 * وعمودٌ يكرّره يفترق عنه أولَ مرةٍ تُلغى فيها رحلةٌ وُجد لها كبتن.
 *
 * **والإلغاءُ من هنا لحجزٍ منتظرٍ وحده**: بعد التسليم صارت له رحلةٌ تُلغى من
 * شاشتها وبرسمها — وزرٌّ هنا يُلغي رحلةً يجعل رسمَ الإلغاء يُخصم من مكانٍ لا
 * يذكره صاحبُه.
 *
 * **والطلبان همـا هما** (`GET /me/bookings` · `DELETE /me/bookings/:id`). **وعلى البطاقة ما تحمله بطاقةُ «مجدولة» في «رحلاتي»
 * من الحجز نفسِه** (`RidesT2`): الانطلاقُ والوجهةُ والفئة — **والأجرةُ تقديرٌ لا أجرة**، تُحسب عند التنفيذ.
 *
 * **والحجزُ المضمون** (§٦٣-ج/٣) — لا لوحةَ له: شارةُ «مضمون»، **واسمُ كبتنه** حين قبله أحد (وعدُ الضمان أن يُعرف قبل
 * الموعد)، **وأين رسمُه** بالمبلغ المجمَّد: محفوظ · دُفع للكبتن · رُدّ إليه. **والحالُ من الخلفية لا من حسابٍ هنا**، ومطفأً
 * لا يُرسم شيءٌ منه — **والدفترُ يبقى يسمّي قيودَه** في المحفظة.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { cancelBooking, listBookings } from "@/api/endpoints";
import type { Booking } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { VEHICLE_LABEL } from "@/lib/labels";
import { formatMoney, DISPLAY_LOCALE, digits } from "@/lib/utils";
import { BlankT2, LoaderT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** أوّلُ حقيقةٍ تحكم: الحجزُ ثم رحلتُه — لا سردٌ للاثنين. والنبرةُ شارةُ الهوية: نجاحٌ · تنبيهٌ · خطأٌ · محايدةٌ · منتظَر. */
function stateOf(booking: Booking): { text: string; tone: "plain" | "warn" | "live" | "danger" | "ok" } {
  if (booking.status === "cancelled") {
    return { text: "أُلغي", tone: "plain" };
  }
  if (booking.status === "missed") {
    return { text: "لم يُنفَّذ — كنتَ في رحلةٍ حينها", tone: "warn" };
  }
  if (booking.status === "pending") {
    return { text: "بانتظار موعده", tone: "live" };
  }
  // سُلّم للتوزيع: الرحلةُ تقول الباقي
  switch (booking.ride_status) {
    case "no_driver_found":
      return { text: "لم نجد كبتناً", tone: "danger" };
    case "completed":
      return { text: "اكتملت", tone: "ok" };
    case "cancelled_by_rider":
    case "cancelled_by_driver":
      return { text: "أُلغيت الرحلة", tone: "plain" };
    case null:
    case undefined:
      return { text: "طُلبت الرحلة", tone: "ok" };
    default:
      return { text: "رحلتك جارية", tone: "ok" };
  }
}

const CHIP: Record<ReturnType<typeof stateOf>["tone"], string> = {
  plain: "t2-chip",
  warn: "t2-chip warn",
  live: "t2-chip t2-live",
  danger: "t2-chip danger",
  ok: "t2-chip ok",
};

/** **أين رسمُ الضمان** — نصُّ كلِّ حالٍ ونبرتُه: المحفوظُ محايد، والواصلُ للكبتن حبر، والعائدُ إليه أخضر. */
const GUARANTEE_FEE: Record<NonNullable<Booking["guarantee_state"]>, { text: string; tone: string }> = {
  held: { text: "محفوظ", tone: "t2-bkg-fee" },
  paid: { text: "دُفع للكبتن", tone: "t2-bkg-fee paid" },
  refunded: { text: "رُدّ إلى محفظتك", tone: "t2-bkg-fee ok" },
};

/** سطرُ الكبتن: **اسمُه حين قبله أحد**، و«نبحث…» ما دام الحجزُ ينتظر — وبعد التسليم بلا كبتنٍ لا سطر: الرحلةُ تقول الباقي. */
function captainLine(booking: Booking): string | null {
  if (booking.captain_name) return `كبتنُك: ${booking.captain_name}`;
  return booking.status === "pending" ? "نبحث عن كبتنٍ يضمن حجزك" : null;
}

function when(iso: string): string {
  const date = new Date(iso);
  return digits(date.toLocaleString(DISPLAY_LOCALE, {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }));
}

export function BookingsScreen() {
  const goBack = useGoBack("/account");
  const [rows, setRows] = useState<Booking[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await listBookings());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الحجوزات"),
    );
  }, [load]);

  async function drop(bookingId: string) {
    setBusy(bookingId);
    setError(null);
    try {
      await cancelBooking(bookingId);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الإلغاء");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="رحلاتي المجدولة" onBack={goBack} />

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}
      {rows === null && !error ? <LoaderT2 /> : null}
      {rows?.length === 0 ? (
        <BlankT2 icon="event_upcoming" title="لا حجوزَ بعد" hint="حدّد موعداً من شاشة تأكيد الرحلة." />
      ) : null}

      {(rows ?? []).map((booking) => {
        const state = stateOf(booking);
        const pending = booking.status === "pending";
        // «نسائية» مكانَ الفئة كما في بطاقة «مجدولة» في «رحلاتي» — **وصفٌ للطلب لا لصاحبته**
        const kind = booking.gender_preference === "female" ? "نسائية" : VEHICLE_LABEL[booking.vehicle_category];
        return (
          <article key={booking.id} className={pending ? "t2-bk pending" : "t2-bk"}>
            <div className="t2-bk-top">
              <span className="t2-bk-when">
                <Icon name="event_upcoming" />
                {when(booking.scheduled_at)}
              </span>
              <span className={CHIP[state.tone]}>{state.text}</span>
            </div>
            <div className="t2-route">
              <span className="t2-dot" />
              <span className="t2-place">{booking.pickup_address ?? "نقطة على الخريطة"}</span>
              <span className="t2-dot to" />
              <span className="t2-place strong">{booking.dropoff_address ?? "نقطة على الخريطة"}</span>
            </div>
            {/* **حجزٌ مضمونٌ يُرى ضمانُه ولو أُطفئت الخدمةُ بعده** — رسمُه محفوظٌ في محفظة صاحبه، فحالُ مالِه تُقال (§٦٣-ج/٣) */}
            {booking.guaranteed ? <GuaranteeBlock booking={booking} /> : null}
            <div className="t2-bk-foot">
              <span>
                {kind} ·{" "}
                {/* **تقديرٌ لا أجرة** — والسعرُ يُحسب عند التنفيذ */}
                {booking.estimated_fare_at_booking
                  ? `تقديراً ${formatMoney(booking.estimated_fare_at_booking, booking.currency)}`
                  : "بلا تقدير"}
              </span>
              {/* **«ألغِ الحجز» بالحبر** كفعل بطاقة «مجدولة» في R12 («تعديل») — والأحمرُ على الجمر الخافت دون ٤٫٥:١ (٤٫٤٧) */}
              {pending ? (
                <button
                  type="button"
                  className="t2-tlink"
                  disabled={busy === booking.id}
                  aria-busy={busy === booking.id}
                  onClick={() => void drop(booking.id)}
                >
                  ألغِ الحجز
                </button>
              ) : booking.ride_id ? (
                <Link to={`/rides/${booking.ride_id}`} className="t2-tlink">
                  تفاصيل الرحلة
                </Link>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}

/** **ما يزيده الضمانُ على البطاقة** (§٦٣-ج/٣): الشارة · الكبتن · الرسم. **والمبلغُ هو المجمَّدُ على الحجز** كما ردّته الخلفية —
 *  لا يُقرأ من إعداد السوق اليوم: رفعُ الرسم بعد الحجز لا يمسّه. */
function GuaranteeBlock({ booking }: { booking: Booking }) {
  const captain = captainLine(booking);
  const fee = booking.guarantee_state ? GUARANTEE_FEE[booking.guarantee_state] : null;
  return (
    <div className="t2-bkg">
      <div className="t2-bkg-head">
        <span className="t2-chip t2-bkg-chip">
          <Icon name="verified_user" />
          مضمون
        </span>
        {captain ? (
          <span className={booking.captain_name ? "t2-bkg-captain named" : "t2-bkg-captain"}>{captain}</span>
        ) : null}
      </div>
      {fee ? (
        <p className={fee.tone}>
          رسمُ الضمان{" "}
          {booking.guarantee_fee ? <span className="t2-bkg-amount">{formatMoney(booking.guarantee_fee, booking.currency)}</span> : null}{" "}
          {fee.text}
        </p>
      ) : null}
    </div>
  );
}
