/** **«سيارتك» ومدخلُ متجر المركبات في رئيسيّة الكبتن** (أمرُ المالك ٢٠٢٦-١١-٢١، SPEC §١١١) — خلف `home_cars` لكلِّ دولة.
 *
 * **تحت الخريطة وزرِّ الاستقبال لا فوقهما** — في مجرى الصفحة، فلا تغطّي الخريطةَ ولا زرَّ الاتّصال ولا عرضَ رحلة (العرضُ ورقةٌ فوق الكلّ).
 *
 * * **السيارةُ سيارةُ TAXO لفئته** (`vehicles.category`) **بلون مركبته** (`vehicles.color` ← `paintFor`، وما لا يُعرف يبقى أبيض)، مع لوحتها
 *   واسمِ الفئة كما في كلِّ شاشة، **وحالِ اشتراكه من الباب الذي ترسم منه الرئيسيّةُ زرَّ الاستقبال** (`covered`)، **ومستواه** حين تكون
 *   المهامُّ مشغَّلة. ولمسُها يفتح «مركبتي».
 * * **ومركبتُه المفعَّلةُ من المتجر** إن كانت مميّزةً أو نادرةً أو أسطوريّة — **بصورتها من الخلفيّة كما هي** (النادرةُ والأسطوريّةُ يرفعها
 *   المالك ولا تُمسّ) وشارةِ ندرتها.
 * * **ومدخلُ المتجر** بمعاينةٍ من رسوم المتجر نفسِه (`GET /skins/store`، مرّةً في الجلسة)، حيث المتجرُ مشتعلٌ وحدَه.
 *
 * **لا رقمَ مخترع**: ما لم يصل لا يُرسم، ولا سعرَ هنا.
 */
import { useEffect, useState } from "react";

import { getSkinStore } from "@/api/endpoints";
import type { Rarity, Vehicle, VehicleSkin } from "@/api/types";
import { paintFor } from "@/lib/car-paint";
import { tr } from "@/lib/i18n";
import { CATEGORY_LABEL } from "@/lib/rideFormat";
import { RARITY_LABEL, skinAssetUrl } from "@/lib/skins";
import { digits } from "@/lib/utils";
import { LEVEL_LABEL } from "@/screens/Missions";
import { Icon } from "@/taxo2";
import { carKey, carSrc, carSrcSet } from "@/taxo2/cars";

import "./home-kit.css";
import "./your-car.css";

const BASE = `${import.meta.env.BASE_URL}cars/`;
/** **المدينةُ الناعمة** خلف السيارة — الصورتان نفسُهما في رئيسيّة الراكب (نظامُ الرئيسيّة المشترك، أمرُ المالك ٢١/١١ الثاني) */
const SCENE = `${import.meta.env.BASE_URL}home/`;

function PaintedCar({ category, color }: { category: string; color: string }) {
  const key = carKey("local_taxi", category);
  const paint = paintFor(key, color);
  return (
    <span className="yc-car" aria-hidden="true">
      {(["day", "night"] as const).map((t) => (
        <span key={t} className={t === "day" ? "yc-layer d" : "yc-layer n"}>
          <img src={carSrc(key, t === "night")} srcSet={carSrcSet(key, t === "night")} sizes="200px" alt="" decoding="async" />
          {paint ? (
            <span
              className="yc-paint"
              style={{
                background: paint,
                WebkitMaskImage: `url(${BASE}${key}-paint-${t}.webp)`,
                maskImage: `url(${BASE}${key}-paint-${t}.webp)`,
              }}
            />
          ) : null}
        </span>
      ))}
    </span>
  );
}

/** **معاينةُ المتجر مرّةً في الجلسة** — لا نداءَ مع كلِّ فتحٍ للرئيسيّة. */
let storePreview: Promise<VehicleSkin[]> | null = null;
function loadStorePreview(): Promise<VehicleSkin[]> {
  storePreview ??= getSkinStore(6, 0)
    .then((store) => store.skins.slice(0, 3))
    .catch(() => {
      storePreview = null;
      return [];
    });
  return storePreview;
}

export function YourCarT2({
  vehicle,
  skin,
  covered,
  daysRemaining,
  level,
  storeOn,
  onOpenVehicle,
  onOpenStore,
}: {
  vehicle: Vehicle | null;
  /** المركبةُ المفعَّلةُ من المتجر — تُرسم هنا إن لم تكن «عاديّة». */
  skin: VehicleSkin | null;
  covered: boolean;
  daysRemaining: number | null;
  level: number | null;
  storeOn: boolean;
  onOpenVehicle: () => void;
  onOpenStore: () => void;
}) {
  const [preview, setPreview] = useState<VehicleSkin[]>([]);
  useEffect(() => {
    if (!storeOn) return;
    let alive = true;
    void loadStorePreview().then((skins) => {
      if (alive) setPreview(skins);
    });
    return () => {
      alive = false;
    };
  }, [storeOn]);

  const special = skin && skin.rarity !== "common" ? skin : null;
  if (!vehicle && !storeOn) return null;
  return (
    <div className="yc">
      {vehicle ? (
        <button type="button" className="yc-card" onClick={onOpenVehicle}>
          <span className="yc-scene" aria-hidden="true">
            <img className="d" src={`${SCENE}scene-day.webp`} alt="" decoding="async" />
            <img className="n" src={`${SCENE}scene-night.webp`} alt="" decoding="async" />
          </span>
          <span className="yc-top">
            <span className="yc-title">{tr("سيارتك")}</span>
            {level !== null ? (
              <span className="yc-level">
                <Icon name="workspace_premium" fill />
                {LEVEL_LABEL[level] ?? tr("المستوى {0}", { 0: digits(String(level)) })}
              </span>
            ) : null}
            <Icon name="chevron_left" className="yc-go" />
          </span>
          <span className="yc-body">
            <span className="yc-info">
              <span className="yc-cat">{CATEGORY_LABEL[vehicle.category] ?? vehicle.category}</span>
              <span className="yc-model">
                {vehicle.make} {vehicle.model}
              </span>
              <span className="yc-plate" dir="ltr">
                {digits(vehicle.plate_number)}
              </span>
              <span className="yc-color">{vehicle.color}</span>
            </span>
            {special ? (
              <span className="yc-skin">
                <img src={skinAssetUrl(special.store_image_url)} alt="" decoding="async" />
                <RarityBadge rarity={special.rarity} />
              </span>
            ) : (
              <PaintedCar category={vehicle.category} color={vehicle.color} />
            )}
          </span>
          <span className={covered ? "yc-sub ok" : "yc-sub off"}>
            <span className="yc-dot" />
            {covered
              ? daysRemaining !== null && daysRemaining <= 5
                ? tr("اشتراكك ساري — يتبقّى {0} أيام", { 0: digits(String(daysRemaining)) })
                : tr("اشتراكك ساري")
              : tr("لا اشتراك ساري")}
          </span>
        </button>
      ) : null}
      {storeOn ? (
        <button type="button" className="yc-store" onClick={onOpenStore}>
          <span className="yc-store-thumbs" aria-hidden="true">
            {preview.map((item) => (
              <img key={item.id} src={skinAssetUrl(item.store_image_url)} alt="" decoding="async" loading="lazy" />
            ))}
          </span>
          <span className="yc-store-text">
            <span className="yc-store-title">{tr("متجر المركبات")}</span>
            <span className="yc-store-sub">{tr("أشكالٌ جديدة لمركبتك")}</span>
          </span>
          <Icon name="chevron_left" className="yc-go" />
        </button>
      ) : null}
    </div>
  );
}

function RarityBadge({ rarity }: { rarity: Rarity }) {
  return <span className={`yc-badge r-${rarity}`}>{RARITY_LABEL[rarity]}</span>;
}
