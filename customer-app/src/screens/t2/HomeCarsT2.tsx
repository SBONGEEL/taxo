/** **رئيسيّةُ الراكب الجديدة** (أمرُ المالك ٢٠٢٦-١١-٢١ الثاني، `design/OWNER-2026-11-21-HOME-REDESIGN.md`، SPEC §١١١) — خلف `home_cars`
 * لكلِّ دولة («سيارات الرئيسية» في اللوحة)، **ومطفأً تعود الرئيسيّةُ كما كانت قبل سيارات الرئيسيّة حرفاً**.
 *
 * * **«إلى أين؟» عنصرٌ مستقلٌّ تحت الرأس** (`HomeSearchT2`) بفعل الزرّ القديم نفسِه (`onWhereTo`)، وتحته **شرائحُ أماكنَ حقيقيّةٍ وحدَها**
 *   (`quickChips`): منزلُه وعملُه المحفوظان، وأقربُ مطارٍ من مطارات السوق (`nearestAirport`)، ووجهتُه الأخيرة — **وما لا وجودَ له لا شريحةَ له**.
 * * **بطاقةُ الفئات دوّارٌ يُسحب** (`HomeCategoriesT2`): بطاقةٌ كبيرةٌ لكلِّ فئةٍ مشتعلةٍ في دولته (`vehicle_categories` من `/config`)، سيارتُها
 *   على مدينةٍ ناعمة، واسمُها كما في كلِّ شاشة (`VEHICLE_LABEL`) وسطرُها (`VEHICLE_HINT`) ومقاعدُها من صفِّ الفئة، **والدقائقُ حين يعرفها
 *   بابُ أقرب كبتن وحدَه**، **والسعرُ يُقال إنه بعد الوجهة** — فلا وجهةَ في الرئيسيّة ولا سعرَ يُخترع. نقاطُ صفحاتٍ تحتها والتاليةُ تطلّ،
 *   ولمسُ البطاقة يختارها للطلب التالي (`onPick`). **سحبٌ أصليٌّ بـ`scroll-snap` ولا تشغيلَ تلقائيّ** — لا مؤقّتَ يستنزف البطّاريّة.
 *
 * والصورُ بمقاسها (`srcset` ١٦٠/٣٢٠/٦٤٠) ونهاريّةٌ وليليّةٌ يُظهر الـCSS إحداهما، **ولا حركةَ إلا انزلاقَ التمرير نفسِه**.
 */
import { useEffect, useRef, useState } from "react";

import type { VehicleCategory } from "@/api/types";
import type { CategoryMinutes } from "@/lib/arrival";
import { carouselIndex, quickChips, shownCategories, type ChipPlace, type QuickChip } from "@/lib/home-cars-core";
import { tr } from "@/lib/i18n";
import { CATEGORY_ICON, VEHICLE_HINT, VEHICLE_LABEL } from "@/lib/labels";
import { Icon } from "@/taxo2";
import { carKey, carSrc, carSrcSet } from "@/taxo2/cars";

export { quickChips, shownCategories };
export type { ChipPlace, QuickChip };

import "./home-cars.css";

const SCENE = `${import.meta.env.BASE_URL}home/`;
const NEXT = "taxo.homeCars.next";

/** **فئةُ الطلب التالي** كما لمسها في دوّار الرئيسيّة — في هذا الهاتف وحدَه؛ وورقةُ الطلب تبدأ بها إن كانت في فئات دولته. */
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

function Car({ category, sizes, eager = false }: { category: VehicleCategory; sizes: string; eager?: boolean }) {
  const key = carKey(CATEGORY_ICON[category] ?? "local_taxi", category);
  const loading = eager ? "eager" : "lazy";
  return (
    <span className="hc-car" aria-hidden="true">
      <img className="d" src={carSrc(key, false)} srcSet={carSrcSet(key, false)} sizes={sizes} alt="" decoding="async" loading={loading} />
      <img className="n" src={carSrc(key, true)} srcSet={carSrcSet(key, true)} sizes={sizes} alt="" decoding="async" loading={loading} />
    </span>
  );
}

const CHIP_ICON: Record<QuickChip["kind"], string> = { home: "home", work: "work", airport: "flight_takeoff", last: "schedule" };

/** **«إلى أين؟» وشرائحُه** — الحقلُ زرٌّ بفعل الزرّ القديم، والشرائحُ تختار الوجهةَ كما يختارها «أماكني». */
export function HomeSearchT2({
  onWhereTo,
  eta,
  chips,
  onChip,
  suggestion,
}: {
  onWhereTo: () => void;
  /** «اقتصادي يصل خلال 3 د» — من باب أقرب كبتن، و`null` حين لا يُعرف. */
  eta: { category: VehicleCategory; minutes: number } | null;
  chips: QuickChip[];
  onChip: (chip: QuickChip) => void;
  /** **اقتراحُ الوجهة الذكيّ** (SPEC §١٠٣ C/35) — شريحةٌ أولى حين يكون. */
  suggestion: { address: string; onPick: () => void } | null;
}) {
  return (
    <section className="hc-search" aria-label={tr("إلى أين؟")}>
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
      {chips.length > 0 || suggestion ? (
        <div className="hc-chips">
          {suggestion ? (
            <button type="button" className="hc-chip smart" onClick={suggestion.onPick}>
              <Icon name="auto_awesome" />
              <span className="hc-chip-text">{tr("إلى {0}؟", { 0: suggestion.address })}</span>
            </button>
          ) : null}
          {chips.map((chip) => (
            <button key={`${chip.kind}:${chip.place.id}`} type="button" className="hc-chip" onClick={() => onChip(chip)} title={chip.place.name}>
              <Icon name={CHIP_ICON[chip.kind]} />
              <span className="hc-chip-text">{chip.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/** **بطاقةُ الفئات** — دوّارٌ بـ`scroll-snap` أصليّ (خفيفٌ على الهاتف الضعيف: لا مكتبةَ ولا مؤقّت)، ونقاطٌ تتبع التمرير بإطارٍ واحدٍ لكلِّ رسم. */
export function HomeCategoriesT2({
  categories,
  selected,
  eta,
  seats,
  onPick,
}: {
  categories: VehicleCategory[];
  selected: VehicleCategory;
  eta: CategoryMinutes | null;
  /** مقاعدُ كلِّ فئةٍ من صفّها في `/config` (`ride_categories`) — وما لم يصل لا يُكتب. */
  seats: Partial<Record<VehicleCategory, number>>;
  onPick: (category: VehicleCategory) => void;
}) {
  const track = useRef<HTMLDivElement | null>(null);
  const [active, setActive] = useState(() => Math.max(0, categories.indexOf(selected)));
  const frame = useRef<number | null>(null);

  // **تبدأ عند المختارة** — بلا حركة، مرّةً عند التركيب
  useEffect(() => {
    const el = track.current;
    const index = categories.indexOf(selected);
    if (!el || index <= 0) return;
    const card = el.children[index] as HTMLElement | undefined;
    card?.scrollIntoView({ block: "nearest", inline: "start", behavior: "instant" as ScrollBehavior });
    // مرّةً عند التركيب وحدَها — اختيارٌ لاحقٌ يمرّر في `pick`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);

  if (categories.length === 0) return null;

  function onScroll() {
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      const el = track.current;
      const first = el?.children[0] as HTMLElement | undefined;
      const second = el?.children[1] as HTMLElement | undefined;
      if (!el || !first) return;
      const step = second ? Math.abs(second.offsetLeft - first.offsetLeft) : first.offsetWidth;
      setActive(carouselIndex(el.scrollLeft, step, categories.length));
    });
  }

  function go(index: number) {
    const card = track.current?.children[index] as HTMLElement | undefined;
    card?.scrollIntoView({ block: "nearest", inline: "start", behavior: "smooth" });
  }

  function pick(key: VehicleCategory, index: number) {
    onPick(key);
    go(index);
  }

  return (
    <section className="hc-cats" aria-label={tr("فئات المركبات")}>
      <div className="hc-track" ref={track} onScroll={onScroll} role="radiogroup" aria-label={tr("فئة الطلب التالي")}>
        {categories.map((key, index) => {
          const minutes = eta?.[key];
          const on = key === selected;
          const count = seats[key];
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "hc-cat on" : "hc-cat"}
              onClick={() => pick(key, index)}
            >
              <span className="hc-scene" aria-hidden="true">
                <img className="d" src={`${SCENE}scene-day.webp`} alt="" decoding="async" />
                <img className="n" src={`${SCENE}scene-night.webp`} alt="" decoding="async" />
              </span>
              <span className="hc-cat-text">
                <span className="hc-cat-name">{VEHICLE_LABEL[key] ?? key}</span>
                {VEHICLE_HINT[key] ? <span className="hc-cat-hint">{VEHICLE_HINT[key]}</span> : null}
                <span className="hc-cat-meta">
                  {typeof count === "number" && count > 0 ? (
                    <span className="hc-pill">
                      <Icon name="person" />
                      <span>
                        <b className="hc-pill-num" dir="ltr">
                          {count}
                        </b>{" "}
                        {tr("مقاعد")}
                      </span>
                    </span>
                  ) : null}
                  {typeof minutes === "number" ? (
                    <span className="hc-pill">
                      <Icon name="schedule" />
                      <span>
                        {tr("يصل خلال")}{" "}
                        <b className="hc-pill-num" dir="ltr">
                          {minutes}
                        </b>{" "}
                        {tr("د")}
                      </span>
                    </span>
                  ) : null}
                </span>
                <span className="hc-cat-price">{tr("السعر بعد اختيار الوجهة")}</span>
              </span>
              <span className="hc-cat-car">
                <Car category={key} sizes="(max-width: 380px) 170px, 200px" eager={index === 0} />
              </span>
              {on ? (
                <span className="hc-cat-on">
                  <Icon name="check" />
                  {tr("مختارة")}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      {categories.length > 1 ? (
        <div className="hc-dots" role="tablist" aria-label={tr("فئات المركبات")}>
          {categories.map((key, index) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={index === active}
              aria-label={VEHICLE_LABEL[key] ?? key}
              className={index === active ? "hc-dot on" : "hc-dot"}
              onClick={() => go(index)}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
