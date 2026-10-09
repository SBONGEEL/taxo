/** **خاتمةُ الرحلة** — TAXO 2.0 «R29 · R29b · R29c» (`design/t2-new/rider/R29-outcome-*.dc.html`)، **في المظهرين
 *  والنسائيّ**: الدفعُ بعد الإنهاء، وخبرٌ يُقرأ بعد الإلغاء أو حين لم يُوجد كبتن (SPEC القسم 5).
 *
 * **ورقةُ R06–R09 الملتصقةُ نفسُها** (`SheetT2`) — **ودائرةُ المعنى والعنوانُ من RW3**، **والأجرةُ النهائيةُ من R10**. **والمنطقُ هو
 * هو حرفاً** (كان `OutcomeSheet` داخل `screens/Home.tsx` بطرازٍ قديم): «الانتقال إلى الدفع» إلى صفحة الدفع، و«أقبل أي كبتن
 * متاح» **طلبٌ جديد بنفس النقطتين** لطلبٍ مجنَّسٍ لم يجد كبتنة، و«حسناً» أو «لاحقاً» تطويها.
 *
 * **وسببُ فشل «أقبل أي كبتن» يُقال تحت زرّه** (§٦٢/٢٠): كانت الرئيسيةُ تحفظه ولا ترسمه في هذا الطور.
 *
 * **ولطلب «كبتنة» الذي انتهى بلا كبتنة وجهُه «RW3»** (§٦٢-ج/٢٣، `WomenRideT2.tsx`) — حيث الخدمةُ مفتوحة: خياراتٌ تختارها هي، و«أقبل
 * أي كبتن» فيه هو هو. **وطلبُ «ذكور» يبقى هنا** كما كان: ليس الخدمةَ النسائية.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { Ride } from "@/api/types";
import { RIDE_STATUS_LABEL } from "@/lib/labels";
import { currencyLabel, formatMoney } from "@/lib/utils";
import { useWomenService } from "@/lib/women";
import { Icon } from "@/taxo2";

import { NoteT2 } from "./KitT2";
import { SheetT2 } from "./SheetT2";
import { WomenNoCaptainT2, isWomenRide } from "./WomenRideT2";
import "./t2.css";
import "./request.css";

/** دائرةُ المعنى: اكتملت بالنجاح · لم تُوجد كبتنةٌ بالبرقوق (RW3) · ألغاها الكبتنُ بالخطأ · وما عداه محايد. */
function markOf(ride: Ride): { icon: string; tone: string } {
  if (ride.status === "completed") return { icon: "check", tone: "t2-out-icon ok" };
  if (ride.status === "no_driver_found") {
    return { icon: "hourglass_top", tone: ride.gender_preference === "female" ? "t2-out-icon women" : "t2-out-icon" };
  }
  if (ride.status === "cancelled_by_driver") return { icon: "close", tone: "t2-out-icon danger" };
  return { icon: "close", tone: "t2-out-icon" };
}

export function OutcomeSheetT2({
  ride,
  onDismiss,
  onAcceptAnyDriver,
  onScheduleAgain,
  onWidenSearch,
  error,
}: {
  ride: Ride;
  onDismiss: () => void;
  onAcceptAnyDriver: () => Promise<void>;
  /** **«جدولي الرحلة لوقت لاحق»** (RW3) — ورقةُ الطلب بمنتقي الموعد، من الرئيسية */
  onScheduleAgain?: () => void;
  /** **«انتظري، نوسّع البحث»** (RW3، §٦٤-ج/٤-٣) — الرحلةُ نفسُها بـ`widen_search`، من الرئيسية */
  onWidenSearch?: () => Promise<void>;
  /** **خطأُ «أقبل أي كبتن»** — من الرئيسية التي ترسل الطلب */
  error: string | null;
}) {
  const navigate = useNavigate();
  const [retrying, setRetrying] = useState(false);
  const women = useWomenService();
  // **RW3 — لا كبتنة قريبة** (§٦٢-ج/٢٣): لطلب «كبتنة» انتهى بلا كبتنة، حيث الخدمةُ مفتوحة — والخيارُ لها، ولا شيءَ آليّ
  if (ride.status === "no_driver_found" && isWomenRide(ride) && women.enabled) {
    return (
      <WomenNoCaptainT2
        onDismiss={onDismiss}
        onAcceptAnyDriver={onAcceptAnyDriver}
        onScheduleAgain={onScheduleAgain}
        onWidenSearch={onWidenSearch}
        error={error}
      />
    );
  }
  const completed = ride.status === "completed";
  // طلبٌ مجنَّس لم يجد كبتناً: هنا وحده يُعرض التنازل عن الشرط
  const missedGendered = ride.status === "no_driver_found" && ride.gender_preference !== "any";
  const mark = markOf(ride);

  const footer = completed ? (
    <div className="t2-out-actions">
      <button type="button" className="t2-button primary" onClick={() => navigate(`/rides/${ride.id}/pay`)}>
        الانتقال إلى الدفع
      </button>
      <button type="button" className="t2-out-later" onClick={onDismiss}>
        لاحقاً
      </button>
    </div>
  ) : missedGendered ? (
    <div className="t2-out-actions">
      <button
        type="button"
        className="t2-button primary"
        disabled={retrying}
        aria-busy={retrying}
        onClick={async () => {
          setRetrying(true);
          try {
            await onAcceptAnyDriver();
          } finally {
            setRetrying(false);
          }
        }}
      >
        أقبل أي كبتن متاح
      </button>
      {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
      <button type="button" className="t2-out-later" onClick={onDismiss}>
        حسناً
      </button>
    </div>
  ) : (
    <div className="t2-out-actions">
      <button type="button" className="t2-button primary" onClick={onDismiss}>
        حسناً
      </button>
    </div>
  );

  return (
    <SheetT2 footer={footer}>
      <div className="t2-out-head">
        <span className={mark.tone}>
          <Icon name={mark.icon} />
        </span>
        <h3 className="t2-out-title">{RIDE_STATUS_LABEL[ride.status]}</h3>
      </div>

      {completed ? (
        <div className="t2-out-fare">
          <div className="t2-out-fare-label">الأجرة النهائية</div>
          <div className="t2-out-fare-amount">
            <span dir="ltr" className="t2-num">
              {formatMoney(ride.final_fare ?? ride.rider_estimate)}
            </span>
            <span className="t2-out-fare-cur">{currencyLabel(ride.currency)}</span>
          </div>
        </div>
      ) : missedGendered ? (
        /* **تخييرٌ لا رفض**: الطلبُ سقط لأن الشرط لم يتحقق، والقرارُ في
           التنازل عنه قرارُها هي — ونعرضه مرةً هنا لا نطبّقه عنها.
           و«أنتظر كبتنة» ليس زراً بعد: لا مسارَ في الخلفية يواصل بحثاً
           انتهى، فوعدٌ بلا مسارٍ أسوأ من غيابه (`FUTURE-FEATURES`) */
        <p className="t2-out-text">
          {/* **و«ذكور» ليس طلبَ كبتنة** (§٦٢-ب/٤٧) — ويختاره الرجلُ في ملفّه أيضاً، فلا يُخاطَب بالمؤنّث */}
          {ride.gender_preference === "male"
            ? "لا كبتن من الذكور متاحٌ قريباً الآن. يمكنك طلب رحلةٍ جديدة بعد قليل، أو قبول أي كبتن متاح الآن — الاختيار لك."
            : "لا كبتنة متاحة قريبة الآن. يمكنك طلب رحلةٍ جديدة بعد قليل، أو قبول أي كبتن متاح الآن — الاختيار لكِ."}
        </p>
      ) : (
        <p className="t2-out-text">{ride.cancelled_reason ?? "يمكنك طلب رحلة جديدة الآن."}</p>
      )}
    </SheetT2>
  );
}
