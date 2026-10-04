/** **ما فوق الخريطة في أطوار الطلب** — TAXO 2.0، في المظهر النهاريّ المرسوم وحدَه.
 *
 * الرأسُ وزرُّ الموقع والدبوسُ وورقتا «حرّك الخريطة» و«إلى أين؟» — **بأفعال الشاشة القائمة نفسِها** تمرّرها
 * `screens/Home.tsx` كما تمرّرها للوجه القائم.
 *
 * **والرأسُ كما رسمته «R06»** — سهمُ رجوعٍ في جهة البدء — **ومعه ما في الرأس القائم ولم يُرسم**: الجرسُ بنقطته،
 * **ومبدّلُ السِمة** (قرارُ المالك ٢٥: «من يبدّلها لأن الشمس على الشاشة يبدّلها وهو ينظر إلى الخريطة»)، وحرفُ الحساب
 * حيث لا سهم. **والدبوسُ** بلغة خريطة الهوية: دائرةٌ للانطلاق ومربّعٌ للوجهة («لغة الخريطة» في الهوية).
 */

import type { SavedPlace } from "@/api/types";

import { SheetT2 } from "./SheetT2";
import "@/taxo2";
import "./t2.css";

export function MapHeaderT2({
  initial,
  unread,
  dark,
  onBack,
  onOpenAccount,
  onOpenNotifications,
  onToggleTheme,
}: {
  initial: string;
  unread: boolean;
  dark: boolean;
  /** في ورقة الطلب وحدَها — «رجوع» من اللوحة. */
  onBack: (() => void) | null;
  onOpenAccount: () => void;
  onOpenNotifications: () => void;
  onToggleTheme: () => void;
}) {
  return (
    <div className="t2 t2-maphead">
      {onBack ? (
        <button type="button" className="t2-mapbtn" onClick={onBack} aria-label="رجوع">
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
      ) : (
        <button type="button" className="t2-avatar sm t2-mapbtn-avatar" onClick={onOpenAccount} aria-label="حسابي">
          {initial}
        </button>
      )}
      <span className="t2-maphead-gap" />
      <button type="button" className="t2-mapbtn" onClick={onOpenNotifications} aria-label="الإشعارات">
        <span className="t2-icon" aria-hidden="true">notifications</span>
        {unread ? <span className="t2-home-dot" /> : null}
      </button>
      <button
        type="button"
        className="t2-mapbtn"
        onClick={onToggleTheme}
        aria-label={dark ? "الوضع النهاري" : "الوضع الليلي"}
      >
        <span className="t2-icon" aria-hidden="true">{dark ? "light_mode" : "dark_mode"}</span>
      </button>
    </div>
  );
}

export function LocateButtonT2({ onLocate }: { onLocate: () => void }) {
  return (
    <button type="button" className="t2 t2-mapbtn t2-locate" onClick={onLocate} aria-label="موقعي الحالي">
      <span className="t2-icon" aria-hidden="true">my_location</span>
    </button>
  );
}

/** دبوسُ المركز — الخريطةُ تتحرّك تحته لا هو فوقها. */
export function PinT2({ target }: { target: "pickup" | "dropoff" }) {
  return (
    <div className="t2 t2-pin-wrap" aria-hidden="true">
      <span className={target === "pickup" ? "t2-pin from" : "t2-pin to"} />
      <span className="t2-pin-stem" />
    </div>
  );
}

export function PickingSheetT2({
  targetLabel,
  address,
  loading,
  onConfirm,
  onCancel,
}: {
  targetLabel: string;
  address: string | null;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <SheetT2>
      <p className="t2-picking-hint">حرّك الخريطة حتى يقف الدبوس على {targetLabel}</p>
      {/* **العنوانُ المعكوس** — تأكيدُ نقطةٍ بلا اسمها تأكيدٌ على العمى، كالورقة القائمة */}
      <p className="t2-picking-address">{loading ? "نقرأ العنوان…" : (address ?? "حرّك الخريطة لقراءة العنوان")}</p>
      <div className="t2-picking-actions">
        <button type="button" className="t2-button primary" onClick={onConfirm}>
          تأكيد الموقع
        </button>
        <button type="button" className="t2-button secondary" onClick={onCancel}>
          إلغاء
        </button>
      </div>
    </SheetT2>
  );
}

/** «إلى أين؟» فوق الخريطة — **حين لا تُعرف نقطةُ الانطلاق** (موقعٌ لم يُسمح به): الحقلُ والمكانان والانطلاقُ «تغيير». */
export function WhereToSheetT2({
  places,
  pickupLabel,
  onSearch,
  onPickPlace,
  onChangePickup,
}: {
  places: SavedPlace[];
  pickupLabel: string;
  onSearch: () => void;
  onPickPlace: (place: SavedPlace) => void;
  onChangePickup: () => void;
}) {
  return (
    <SheetT2>
      <p className="t2-whereto-title">إلى أين؟</p>
      <button type="button" className="t2-whereto-field" onClick={onSearch}>
        <span className="t2-icon" aria-hidden="true">search</span>
        <span>ابحث عن وجهتك أو حدّدها بالدبوس</span>
      </button>
      {places.length > 0 ? (
        <div className="t2-home-places">
          {places.slice(0, 2).map((place) => (
            <button key={place.id} type="button" className="t2-home-chip" onClick={() => onPickPlace(place)}>
              <span className="t2-icon" aria-hidden="true">star</span>
              <span>{place.label}</span>
            </button>
          ))}
        </div>
      ) : null}
      <button type="button" className="t2-whereto-pickup" onClick={onChangePickup}>
        <span className="t2-icon fill" aria-hidden="true">location_on</span>
        <span className="t2-whereto-pickup-main">
          <span className="t2-route-label">نقطة الانطلاق</span>
          <span className="t2-route-value">{pickupLabel}</span>
        </span>
        <span className="t2-whereto-change">تغيير</span>
      </button>
    </SheetT2>
  );
}
