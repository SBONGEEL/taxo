/** **سياراتُ TAXO في الرئيسيّة** (أمرُ المالك ٢٠٢٦-١١-٢١، SPEC §١١١، `design/OWNER-2026-11-21-HOME-CARS.md`) — خلف `home_cars` لكلِّ دولة.
 *
 * **البطاقةُ البطلة** مكانَ زرِّ «إلى أين؟» نفسِه وبفعله نفسِه (`onWhereTo`): سيارةُ TAXO كبيرةٌ على مدينةٍ ناعمة، «اطلب مشوارك الآن» و«بكل
 * سهولة وأمان»، **وحقلُ «إلى أين؟»**؛ وتحته سطرُ «اقتصادي يصل خلال 3 د» **حين يقوله بابُ أقرب كبتن وحدَه**. **وتنطوي بسحبةٍ إلى الأسفل**
 * (أو بمقبضها) إلى الحقل وحدَه فتظهر الخريطةُ أكثر، وتنبسط بسحبةٍ إلى الأعلى — **ولا تغطّي الخريطةَ في أيِّ حال**: هي في مجرى الصفحة.
 *
 * **وصفُّ الفئات** تحتها: **فئاتُ دولته المشتعلةُ وحدَها** (`vehicle_categories` من `/config` — القائمةُ نفسُها التي في ورقة الطلب)، بسيارتها
 * واسمِها كما في كلِّ شاشة (`VEHICLE_LABEL`)، **والدقائقُ حين يعرفها بابُها وحدَه**، **ولا سعرَ هنا**: السعرُ التقديريُّ يظهر في ورقة الطلب
 * بعد الوجهة من باب التسعير القائم — فيُقال ذلك بسطرٍ صادق. **ولمسُ الفئة يختارها للطلب التالي** (`onPick`).
 *
 * **والدخولُ مرّةً واحدةً في الجلسة** — انزلاقٌ قصيرٌ ومسحةُ ضوءٍ بـ`transform`/`opacity` وحدَهما، **ولا شيءَ عند `prefers-reduced-motion`**،
 * ولا تكرار. والصورُ بمقاسها (`srcset` ١٦٠/٣٢٠/٦٤٠) ونهاريّةٌ وليليّةٌ يُظهر الـCSS إحداهما.
 */
import { useEffect, useRef, useState } from "react";

import type { VehicleCategory } from "@/api/types";
import type { CategoryMinutes } from "@/lib/arrival";
import { tr } from "@/lib/i18n";
import { CATEGORY_ICON, VEHICLE_LABEL } from "@/lib/labels";
import { Icon, Wordmark } from "@/taxo2";
import { carKey, carSrc, carSrcSet } from "@/taxo2/cars";
import { shownCategories, swipeIntent } from "@/lib/home-cars-core";

export { shownCategories };

import "./home-cars.css";

const SCENE = `${import.meta.env.BASE_URL}home/`;
const ENTERED = "taxo.homeCars.entered";
const FOLDED = "taxo.homeCars.folded";

const NEXT = "taxo.homeCars.next";

/** **فئةُ الطلب التالي** كما لمسها في صفِّ الرئيسيّة — في هذا الهاتف وحدَه؛ وورقةُ الطلب تبدأ بها إن كانت في فئات دولته. */
export function readNextCategory(): VehicleCategory | null {
  try {
    return (window.localStorage.getItem(NEXT) as VehicleCategory | null) || null;
  } catch {
    return null;
  }
}

export function writeNextCategory(category: VehicleCategory): void {
  try {
    window.localStorage.setItem(NEXT, category);
  } catch {
    // تخزينٌ ممنوع — تبقى للفتحة وحدَها
  }
}

function readFlag(storage: "local" | "session", key: string): boolean {
  try {
    return (storage === "local" ? window.localStorage : window.sessionStorage).getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(storage: "local" | "session", key: string, on: boolean): void {
  try {
    const s = storage === "local" ? window.localStorage : window.sessionStorage;
    if (on) s.setItem(key, "1");
    else s.removeItem(key);
  } catch {
    // تخزينٌ ممنوع — يبقى الحالُ لهذه الفتحة وحدَها
  }
}

function Car({ category, width }: { category: VehicleCategory; width: string }) {
  const key = carKey(CATEGORY_ICON[category] ?? "local_taxi", category);
  return (
    <span className="hc-car" aria-hidden="true">
      <img className="d" src={carSrc(key, false)} srcSet={carSrcSet(key, false)} sizes={width} alt="" decoding="async" />
      <img className="n" src={carSrc(key, true)} srcSet={carSrcSet(key, true)} sizes={width} alt="" decoding="async" />
    </span>
  );
}

export function HomeCarsHeroT2({
  onWhereTo,
  category,
  eta,
}: {
  onWhereTo: () => void;
  /** سيارةُ البطاقة: الفئةُ المختارةُ للطلب التالي، أو الأولى في الدولة. */
  category: VehicleCategory;
  /** «اقتصادي يصل خلال 3 د» — من باب أقرب كبتن، و`null` حين لا يُعرف. */
  eta: { category: VehicleCategory; minutes: number } | null;
}) {
  const [folded, setFolded] = useState(() => readFlag("local", FOLDED));
  // **مرّةً واحدةً في الجلسة** — يُقرأ قبل الرسم فلا يومض
  const [enter] = useState(() => !readFlag("session", ENTERED));
  useEffect(() => {
    if (enter) writeFlag("session", ENTERED, true);
  }, [enter]);
  const start = useRef<{ x: number; y: number } | null>(null);

  function fold(next: boolean) {
    setFolded(next);
    writeFlag("local", FOLDED, next);
  }

  return (
    <section
      className={["hc-hero", folded ? "folded" : null, enter && !folded ? "enter" : null].filter(Boolean).join(" ")}
      aria-label={tr("اطلب مشوارك الآن")}
      onTouchStart={(event) => {
        const t = event.touches[0];
        start.current = t ? { x: t.clientX, y: t.clientY } : null;
      }}
      onTouchEnd={(event) => {
        const t = event.changedTouches[0];
        const s = start.current;
        start.current = null;
        if (!t || !s) return;
        const intent = swipeIntent(t.clientY - s.y, t.clientX - s.x);
        if (intent === "fold" && !folded) fold(true);
        if (intent === "open" && folded) fold(false);
      }}
    >
      <button
        type="button"
        className="hc-grip"
        onClick={() => fold(!folded)}
        aria-label={folded ? tr("إظهار البطاقة") : tr("طيّ البطاقة")}
        aria-expanded={!folded}
      >
        <span />
      </button>
      {folded ? null : (
        <>
          <span className="hc-scene" aria-hidden="true">
            <img className="d" src={`${SCENE}scene-day.webp`} alt="" decoding="async" />
            <img className="n" src={`${SCENE}scene-night.webp`} alt="" decoding="async" />
          </span>
          <div className="hc-hero-top">
            <div className="hc-hero-text">
              <Wordmark size={14} />
              <h2 className="hc-title">{tr("اطلب مشوارك الآن")}</h2>
              <p className="hc-sub">{tr("بكل سهولة وأمان")}</p>
            </div>
            <span className="hc-hero-car">
              <Car category={category} width="(max-width: 400px) 190px, 220px" />
              <span className="hc-sweep" aria-hidden="true" />
            </span>
          </div>
        </>
      )}
      <button type="button" className="hc-field" onClick={onWhereTo}>
        <Icon name="search" className="hc-field-icon" />
        <span className="hc-field-text">
          <span className="hc-field-title">{tr("إلى أين؟")}</span>
          {eta ? (
            <span className="hc-field-sub">
              {VEHICLE_LABEL[eta.category]}{" "}{tr("يصل خلال")}{" "}
              <b className="hc-num" dir="ltr">
                {eta.minutes}
              </b>{" "}
              {tr("د")}
            </span>
          ) : null}
        </span>
        <span className="hc-field-go" aria-hidden="true">
          <Icon name="arrow_back" />
        </span>
      </button>
    </section>
  );
}

export function HomeCarsRowT2({
  categories,
  selected,
  eta,
  onPick,
}: {
  categories: VehicleCategory[];
  selected: VehicleCategory;
  eta: CategoryMinutes | null;
  onPick: (category: VehicleCategory) => void;
}) {
  if (categories.length === 0) return null;
  return (
    <section className="hc-row-wrap" aria-label={tr("فئات المركبات")}>
      <div className="hc-row" role="radiogroup" aria-label={tr("فئة الطلب التالي")}>
        {categories.map((key) => {
          const minutes = eta?.[key];
          const on = key === selected;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "hc-cat on" : "hc-cat"}
              onClick={() => onPick(key)}
            >
              <Car category={key} width="96px" />
              <span className="hc-cat-name">{VEHICLE_LABEL[key] ?? key}</span>
              {typeof minutes === "number" ? (
                <span className="hc-cat-eta">
                  <b className="hc-num" dir="ltr">
                    {minutes}
                  </b>{" "}
                  {tr("د")}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <p className="hc-row-note">{tr("السعرُ التقديريُّ يظهر بعد اختيار الوجهة")}</p>
    </section>
  );
}
