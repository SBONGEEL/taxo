/** بطاقةُ الخريطة — **وتوسيعُها زيادةٌ على التصميم بقرار المالك 2026-08-30**.
 *
 * **والتصميمُ لا يرسمه**: بطاقةُ `height:170px` فيها شارةٌ وزرٌّ في قاعها،
 * **ولا أيقونةَ توسيعٍ ولا شاشةٌ ثانية** — قِرئ الملفّان قبل البناء. فهذه
 * إضافةٌ مقصودة، وعلّتُها مكتوبةٌ في README مجلَّد التصميم كما كُتبت الثلاث.
 *
 * ## وأربعةٌ تحكم شكلَها (حسمُ المالك)
 *
 * 1. **شارةٌ ظاهرةٌ لا نقرٌ صامت**: نقرٌ وحدَه **لا يُعلَم إلا بالتجربة**،
 *    ومن لا يجرّب لا يعرف أن الميزةَ هناك — وهي «بابٌ بلا زرّ» بعينها.
 *    **فالشارةُ أيقونةٌ ومعها كلمة**، لا أيقونةً وحدَها.
 * 2. **الموسَّعةُ ملءُ الشاشة**.
 * 3. **وتُغلق بزرٍّ ظاهر** لا بإيماءةٍ وحدَها — **والإيماءةُ تبقى معه** (زرُّ
 *    الجهاز الخلفيّ)، فمن عرفها استعملها ومن لم يعرفها رأى الزرّ.
 * 4. **وزرُّ العمل يبقى في متناوله وهي موسَّعة**: **خريطةٌ تخفي زرَّ العمل
 *    تجعله يغلقها ليعمل** — فيصير التوسيعُ عبئاً لا ميزة.
 *
 * **وللراكب لا سطرَ حالٍ** كالذي للكبتن: **لا حالَ عملٍ له تُقرأ** — هو إمّا
 * في رحلةٍ (وحينها لا تُرسم هذه الشاشةُ أصلاً) أو ينظر. **وسطرٌ يُخترع له
 * ليُشبه شاشةَ الكبتن يقول ما لا معنى له.**
 *
 * ## والعقدةُ واحدةٌ لا تُبنى مرّتين
 *
 * الحاويةُ **هي هي** في الحالين، **ويتبدّل صنفُها لا موضعُها في الشجرة** —
 * فلا يُفكَّك `mapbox-gl` ويُبنى من جديدٍ عند كلِّ توسيع. **وثمنُ ذلك مدفوعٌ
 * في `MapView`**: مراقبُ مقاسٍ يعيد `resize()`، وبغيره تبقى اللوحةُ ١٧٠
 * بكسل داخل حاويةٍ ملءَ الشاشة.
 */

import { Maximize2, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

interface Props {
  /** الخريطةُ نفسُها — تُمرَّر كما هي. */
  children: ReactNode;
  /** شارةُ الحال في أعلى البطاقة — **في جهة البدء كما يرسمها التصميم**. */
  badge?: ReactNode;
  /** زرُّ العمل — **يبقى في القاع موسَّعةً كانت أو لا**. */
  action: ReactNode;
  /** سطرٌ يقول أين هو من العمل — **يظهر موسَّعةً وحدَها**، إذ هو في الرأس
   *  حين تكون بطاقة. */
  expandedStatus?: ReactNode;
}

export function MapCard({ children, badge, action, expandedStatus }: Props) {
  const [open, setOpen] = useState(false);

  // **زرُّ الجهاز الخلفيُّ يغلقها قبل أن يغادر الشاشة** — ومن ضغطه وهو يرى
  // خريطةً يقصد إغلاقَها لا الخروجَ من التطبيق
  useEffect(() => {
    if (!open) return;
    window.history.pushState({ map: true }, "");
    const back = () => setOpen(false);
    window.addEventListener("popstate", back);
    return () => {
      window.removeEventListener("popstate", back);
      // **ولا يبقى مدخلٌ ميتٌ في التاريخ** إن أُغلقت بالزرّ
      if (window.history.state?.map) window.history.back();
    };
  }, [open]);

  return (
    <div
      className={
        open
          ? "fixed inset-0 z-40 bg-bg"
          : "relative mb-10 h-170 overflow-hidden rounded-16 border border-line"
      }
    >
      {children}

      {/* الشارةُ في جهة البدء — كما في التصميم (`right` في نصٍّ عربيّ) */}
      {badge && !open ? (
        <div className="pointer-events-none absolute start-10 top-10">
          {badge}
        </div>
      ) : null}

      {/* **شارةُ التوسيع تقول ما يقع** — ولا تُترك نقرةً صامتة */}
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="pressable absolute end-10 top-10 flex items-center gap-5 rounded-full border border-line bg-surface px-9 py-5 text-10.5 font-semibold text-ink"
        >
          <Maximize2 className="size-12" />
          توسيع
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="إغلاق الخريطة"
          className="ctl absolute end-16 top-14 size-40"
        >
          <X className="size-20" />
        </button>
      )}

      {/* **حالُه مقروءةٌ وهي موسَّعة** — وفي البطاقة يقرؤها من الرأس */}
      {open && expandedStatus ? (
        <div className="pointer-events-none absolute inset-x-16 top-14 flex justify-start pe-52">
          {expandedStatus}
        </div>
      ) : null}

      {/* **زرُّ العمل في القاع في الحالين** — فلا يُغلقها ليعمل */}
      <div
        className={
          open ? "absolute inset-x-16 bottom-24" : "absolute inset-x-10 bottom-10"
        }
      >
        {action}
      </div>
    </div>
  );
}
