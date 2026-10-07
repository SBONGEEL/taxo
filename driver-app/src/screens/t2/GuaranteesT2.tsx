/** **الحجوزُ المضمونة** (SPEC §٦٣-ج/٣) — «القادمة» و«عروضٌ تنتظرك» في صفحةٍ واحدة، **في المظهرين** — لا لوحةَ لها:
 * مركّبةٌ من عُدّة TAXO 2.0 (الرأس · عنوانُ القسم · الشارة · الأزرار · البلاغ · الفراغ) **بالرموز وحدَها**.
 *
 * **«القادمة» أوّلاً**: فيها ما له أجل — سؤالُ «هل أنت في الطريق؟» يُسحب الحجزُ بعده بلا ردّ. **والعروضُ بعدها**.
 *
 * **والأفعالُ أبوابُ الخلفية بحرفها، ورسائلُها كما ردّتها**: قبولٌ سبقه غيرُه (٤٠٩ `guarantee_taken`)، ومحجوبٌ (٤٠٣
 * `guarantee_banned`)، وتأكيدٌ قبل نافذته (٤٠٩ بنصّ دقائقها) — **لا نصَّ يُخترع هنا مكانَ نصِّها**. **و«نعم» تعيد الرحلةَ نفسَها**
 * فتُسلَّم إلى سياق الرحلة وتُفتح الرئيسيةُ عليها — لا نداءَ ثانٍ ولا انتظارَ مقبس.
 *
 * **وما لم يُبنَ — بعلّته**: نصُّ تأكيد الإلغاء في شاشة الرحلة («اعتذارُك بعد التأكيد: يُؤخذ منك رسمُ الضمان…») — **`RideOut`
 * لا يحمل ما يقول إن الرحلةَ من حجزٍ مضمون** (`scheduled_for` يحمله كلُّ حجزٍ مجدول)، **فيُقال هنا قبل «نعم»** حيث يُعرف يقيناً.
 */

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  acceptGuarantee,
  confirmGuarantee,
  listGuaranteeOffers,
  listMyGuarantees,
  withdrawGuarantee,
} from "@/api/endpoints";
import type { GuaranteeOffer } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useGuarantees } from "@/lib/guarantees";
import { useRide } from "@/lib/ride";
import { CATEGORY_LABEL } from "@/lib/rideFormat";
import { currencyLabel, digits, DISPLAY_LOCALE } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./t2.css";
import "./guarantees.css";

/** **رفضٌ يُغلق البطاقةَ لا يُعاد بضغطةٍ ثانية** — سبقه كبتنٌ آخر، أو هو محجوب: الزرُّ بعدهما يَعِد بما لا يقع. */
const FINAL_CODES = new Set(["guarantee_taken", "guarantee_banned"]);

/** «اليوم 18:30» · «غداً 09:15» · «الخميس 12 أكتوبر 07:00» — **الساعةُ بخاناتٍ لاتينية** (§20)، والمعرَّفُ بيومه أوّلاً. */
function slot(iso: string): { day: string; time: string } {
  const at = new Date(iso);
  const time = digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false }));
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  if (at.toDateString() === today.toDateString()) return { day: "اليوم", time };
  if (at.toDateString() === tomorrow.toDateString()) return { day: "غداً", time };
  return { day: digits(at.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long", day: "numeric", month: "long" })), time };
}

interface Lists {
  offers: GuaranteeOffer[];
  mine: GuaranteeOffer[];
}

export function GuaranteesT2Screen() {
  const enabled = useGuarantees();
  const navigate = useNavigate();
  const goBack = useGoBack("/");
  const { setRide } = useRide();
  const [lists, setLists] = useState<Lists | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // **رفضُ كلِّ بطاقةٍ تحتها** لا في رأس الصفحة — من ضغط «اقبل» على الثالثة يقرأ سببَ رفضها حيث ضغط
  const [cardError, setCardError] = useState<Record<string, { message: string; final: boolean }>>({});

  const load = useCallback(async () => {
    const [offers, mine] = await Promise.all([listGuaranteeOffers(), listMyGuarantees()]);
    setLists({ offers, mine });
  }, []);

  useEffect(() => {
    if (!enabled) return;
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الحجوز المضمونة"));
  }, [enabled, load]);

  if (!enabled) return <Navigate to="/" replace />;

  async function act(bookingId: string, action: () => Promise<string | null>) {
    setBusy(bookingId);
    setDone(null);
    setCardError((current) => {
      const next = { ...current };
      delete next[bookingId];
      return next;
    });
    try {
      const message = await action();
      if (message !== null) {
        setDone(message);
        await load();
      }
    } catch (caught) {
      setCardError((current) => ({
        ...current,
        [bookingId]: {
          message: caught instanceof ApiError ? caught.message : "تعذّر الإرسال — حاول ثانية",
          final: caught instanceof ApiError && FINAL_CODES.has(caught.code),
        },
      }));
    } finally {
      setBusy(null);
    }
  }

  const accept = (booking: GuaranteeOffer) =>
    void act(booking.id, async () => {
      await acceptGuarantee(booking.id);
      return "قبلتَ الحجز — تجده في «القادمة»، ونسألك قبل موعده: هل أنت في الطريق؟";
    });

  const withdraw = (booking: GuaranteeOffer) =>
    void act(booking.id, async () => {
      await withdrawGuarantee(booking.id);
      return "اعتذرتَ عن الحجز قبل تأكيده — عاد لغيرك، بلا أثرٍ عليك.";
    });

  // **«نعم» تعيد الرحلةَ نفسَها**: تُسلَّم إلى سياق الرحلة وتُفتح الرئيسيةُ عليها — والقائمةُ لا تُعاد قراءتُها (`null`)
  const confirm = (booking: GuaranteeOffer) =>
    void act(booking.id, async () => {
      setRide(await confirmGuarantee(booking.id));
      navigate("/", { replace: true });
      return null;
    });

  return (
    <div className="t2 t2-gu">
      <div className="t2-gu-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">الحجوز المضمونة</h1>
        </div>
        <p className="t2-gu-lede">
          تقبل رحلةً مجدولةً قبل موعدها، وتؤكّد قبله بساعة. <b>ورسمُ الضمان لك كاملاً</b> حين تتمّ الرحلةُ معك في وقتها.
        </p>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}
        {done ? (
          <p className="t2-note t2-gu-done" role="status">
            <Icon name="check_circle" />
            {done}
          </p>
        ) : null}

        {lists === null ? (
          error ? null : (
            <div className="t2-gu-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : (
          <>
            {lists.mine.length > 0 ? (
              <section>
                <div className="t2-section">
                  القادمة
                  <span className="t2-section-aside" dir="ltr">
                    {digits(String(lists.mine.length))}
                  </span>
                </div>
                {lists.mine.map((booking) => (
                  <GuaranteeCard key={booking.id} booking={booking} error={cardError[booking.id]}>
                    <Upcoming
                      booking={booking}
                      busy={busy === booking.id}
                      locked={busy !== null}
                      onConfirm={() => confirm(booking)}
                      onWithdraw={() => withdraw(booking)}
                    />
                  </GuaranteeCard>
                ))}
              </section>
            ) : null}

            <section>
              <div className="t2-section">عروضٌ تنتظرك</div>
              {lists.offers.length === 0 ? (
                // **الفراغُ يقول أسبابَه كلَّها** — الخلفيةُ تردّ فارغةً لمن حُجب أو بلا اشتراك أيضاً، فلا يُقرأ «لا طلبَ في السوق» وحدَه
                <p className="t2-empty">
                  لا عروضَ الآن. تظهر هنا الحجوزُ المضمونةُ في فئة مركبتك قبل موعدها بيومٍ تقريباً.
                </p>
              ) : (
                lists.offers.map((booking) => {
                  const failed = cardError[booking.id];
                  return (
                    <GuaranteeCard key={booking.id} booking={booking} error={failed}>
                      <button
                        type="button"
                        className="t2-button action t2-gu-go"
                        disabled={busy !== null || failed?.final === true}
                        aria-busy={busy === booking.id}
                        onClick={() => accept(booking)}
                      >
                        {busy === booking.id ? "نرسل…" : "اقبل الحجز"}
                      </button>
                    </GuaranteeCard>
                  );
                })
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

/** **بطاقةُ الحجز** — الموعدُ والفئة، والمسارُ بنقطتيه، **والمالُ سطران**: تقديرُ الأجرة (لا أجرة)، ورسمُ الضمان له كاملاً.
 *  **ولا يُجمع الرقمان** (§14): هما شيئان يُدفع كلٌّ بقناته. */
function GuaranteeCard({
  booking,
  error,
  children,
}: {
  booking: GuaranteeOffer;
  error?: { message: string };
  children: ReactNode;
}) {
  const when = slot(booking.scheduled_at);
  const cur = currencyLabel(booking.currency);
  return (
    <article className={booking.confirm_requested ? "t2-gu-card asking" : "t2-gu-card"}>
      <div className="t2-gu-top">
        <span className="t2-gu-when">
          <Icon name="event_upcoming" />
          {when.day}{" "}
          <span dir="ltr" className="t2-gu-time">
            {when.time}
          </span>
        </span>
        <span className="t2-chip">{CATEGORY_LABEL[booking.vehicle_category]}</span>
      </div>
      <div className="t2-gu-route">
        <span className="t2-gu-dot" aria-hidden="true" />
        <span className="t2-gu-place">{booking.pickup_address ?? "نقطة على الخريطة"}</span>
        <span className="t2-gu-dot to" aria-hidden="true" />
        <span className="t2-gu-place strong">{booking.dropoff_address ?? "نقطة على الخريطة"}</span>
      </div>
      <div className="t2-gu-money">
        <span>
          {booking.estimated_fare_at_booking ? (
            <>
              أجرةٌ تقديراً{" "}
              <b dir="ltr">{digits(booking.estimated_fare_at_booking)}</b> {cur}
            </>
          ) : (
            "الأجرةُ تُحسب عند التنفيذ"
          )}
        </span>
        <span className="t2-gu-fee">
          + ضمان <b dir="ltr">{digits(booking.guarantee_fee)}</b> {cur} لك كاملاً
        </span>
      </div>
      {children}
      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" />
          {error.message}
        </p>
      ) : null}
    </article>
  );
}

/** **ما قبله**: «أكّد: في الطريق» يُفتح حين يُسأل (`confirm_requested`)، و«اعتذر» بلا أثرٍ قبل التأكيد — **وثمنُ الاعتذار بعده
 *  يُقال هنا قبل «نعم»**: بعدها صار رحلةً، وإلغاؤها من شاشتها لا يعرف أنها مضمونة. */
function Upcoming({
  booking,
  busy,
  locked,
  onConfirm,
  onWithdraw,
}: {
  booking: GuaranteeOffer;
  busy: boolean;
  locked: boolean;
  onConfirm: () => void;
  onWithdraw: () => void;
}) {
  return (
    <>
      {booking.confirm_requested ? (
        <div className="t2-callout t2-gu-ask" role="status">
          <Icon name="schedule" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">هل أنت في الطريق؟</p>
            <p className="t2-callout-body">
              أكّد الآن، وإلا عاد الحجزُ لغيرك بعد دقائق — بلا أثرٍ عليك. <b>وبعد التأكيد يصير اعتذارُك إلغاءً للرحلة</b>:
              يُؤخذ منك رسمُ الضمان للراكب ويُسجَّل إنذار.
            </p>
          </div>
        </div>
      ) : (
        <p className="t2-gu-hint">يُفتح التأكيدُ قبل الموعد بساعة — نسألك حينها: هل أنت في الطريق؟</p>
      )}
      <div className="t2-gu-actions">
        <button
          type="button"
          className="t2-button action"
          disabled={!booking.confirm_requested || locked}
          aria-busy={busy}
          onClick={onConfirm}
        >
          {busy ? "نرسل…" : "أكّد: في الطريق"}
        </button>
        <button type="button" className="t2-button secondary" disabled={locked} onClick={onWithdraw}>
          اعتذر
        </button>
      </div>
      <p className="t2-gu-hint center">«اعتذر» بلا أثرٍ عليك قبل التأكيد.</p>
    </>
  );
}
