/** **خدماتُك كلُّها** — «الكل» في رأس خدمات C04 (§٦٢-ج/٤٣)، **وشبكةُ البلاطات نفسُها** التي ترسمها الرئيسية (`ServiceGrid`).
 *
 * **الرئيسيةُ ستُّ بلاطاتٍ وهذه كلُّها**: الرئيسيةُ تقدّم ما يعمل وتقصّ إلى ستٍّ كما رُسمت (صفّان، `homeTiles`)، و«الكل» يظهر حين يزيد
 * العددُ عليها ويعرضها هنا **بترتيب اللوحة** حرفاً. **والبلاطةُ هي هي في الموضعين** — شارتُها ونقطتُها وقاعدةُ ضغطها من بيتٍ واحد.
 *
 * **ونقطةُ «الوثائق»** (C04): على البلاطة التي تفتح المركبةَ ووثائقَها (`/account/vehicle` — حيث يرفع الكبتنُ المعتمَدُ ما ينقصه)
 * حين ينقص مطلوبٌ أو يُطلب رفعٌ أو يُرفض مستندٌ أو تنقضي صلاحيتُه (`useDocumentsAttention`). **ولا بلاطةَ بهذا المقصد** (اللوحةُ
 * تملك البلاطات) **فلا نقطة** — ولا تُرسم على بلاطةٍ أخرى بالتخمين.
 */

import { useEffect, useState } from "react";
import { useNavigate, type NavigateFunction } from "react-router-dom";

import { getMyProgress, getMySubscription, getStorefront } from "@/api/endpoints";
import type { MyProgress, MySubscription, ServiceTile, Storefront } from "@/api/types";
import { tileOpenable } from "@/components/home/ServiceTiles";
import { Spinner } from "@/components/ui/Feedback";
import { useDocumentsAttention } from "@/lib/attention";
import { useGoBack } from "@/lib/back";
import { digits } from "@/lib/utils";
import { Icon, serviceIcon } from "@/taxo2";

import { countDays } from "./count";

import "./t2.css";
import "./ride.css";

/** عددُ بلاطات الرئيسية — **صفّان من ثلاث** كما رُسمت C04. */
export const HOME_TILES = 6;

/** **ستُّ الرئيسية**: ما يُفتح أوّلاً بترتيب اللوحة، ثمّ «قريباً» — فلا تحجب أربعُ بلاطاتٍ لا تعمل بلاطتين تعملان. */
export function homeTiles(tiles: ServiceTile[]): ServiceTile[] {
  const open = tiles.filter(tileOpenable);
  const rest = tiles.filter((tile) => !tileOpenable(tile));
  return [...open, ...rest].slice(0, HOME_TILES);
}

/** مقصدُ «المركبة ووثائقها» — حيث ترتفع نقطةُ «الوثائق». */
const DOCUMENTS_DESTINATION = "/account/vehicle";

/** **شبكةُ البلاطات** — البلاطاتُ من اللوحة (`GET /storefront`) بلغة C04، **وقاعدةُ الضغط من بيتها** (`tileOpenable`): «قريباً» تُقرأ
 *  ولا تُنقر. **وشارةُ البلاطة من بيانها**: «جديد» محسوبةٌ في الخلفية، والأيّامُ الباقيةُ من الاشتراك، والمهامُّ المنجزةُ
 *  من المستوى — **ولا رقمَ يُخترع لبلاطةٍ لا بيانَ معها**. */
export function ServiceGrid({
  tiles,
  subscription,
  progress,
  covered,
  attention,
  navigate,
}: {
  tiles: ServiceTile[];
  subscription: MySubscription | null;
  progress: MyProgress | null;
  covered: boolean;
  /** **وثائقُ تحتاج فعلاً** — نقطةٌ على بلاطة المركبة ووثائقها. */
  attention: boolean;
  navigate: NavigateFunction;
}) {
  // **«قريباً» تُنقر فتقول «قريباً» ولا شيءَ غيرَه** (أمرُ المالك ٢٠٢٦-١٠-١٠، §٧٢-هـ) — وتختفي وحدَها
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2_500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  return (
    <div className="t2-hm-tiles">
      {tiles.map((tile) => {
        const tag = tileTag(tile, subscription, progress);
        const ok = tile.destination === "/subscription" && covered;
        const dot = attention && tile.destination === DOCUMENTS_DESTINATION;
        const body = (
          <>
            <span className="t2-hm-tile-top">
              <span className={`t2-hm-tile-icon${ok ? " ok" : ""}`}>
                <Icon name={serviceIcon(tile.icon)} fill />
                {dot ? <span className="t2-hm-tile-dot" aria-hidden="true" /> : null}
              </span>
              {tag ? (
                <span className={`t2-hm-tile-tag ${tag.tone}`} dir={tag.ltr ? "ltr" : undefined}>
                  {tag.text}
                </span>
              ) : null}
            </span>
            <span>
              <span className="t2-hm-tile-title">{tile.title}</span>
              {tile.subtitle && tile.status !== "soon" && !tile.is_new ? (
                <span className="t2-hm-tile-sub">{tile.subtitle}</span>
              ) : null}
            </span>
          </>
        );
        return tileOpenable(tile) ? (
          <button
            key={tile.id}
            type="button"
            className="t2-hm-tile"
            onClick={() => navigate(tile.destination!)}
            // **النقطةُ تُقال لقارئ الشاشة** — هي معنًى لا زينة
            aria-label={dot ? `${tile.title} — وثائق تحتاج انتباهك` : undefined}
          >
            {body}
          </button>
        ) : (
          <button key={tile.id} type="button" className="t2-hm-tile" onClick={() => setNotice(`${tile.title} — قريباً`)}>
            {body}
          </button>
        );
      })}
      {notice ? (
        <div className="t2-toast" role="status" aria-live="polite">
          {notice}
        </div>
      ) : null}
    </div>
  );
}

function tileTag(
  tile: ServiceTile,
  subscription: MySubscription | null,
  progress: MyProgress | null,
): { text: string; tone: string; ltr?: boolean } | null {
  if (tile.status === "soon") return { text: "قريباً", tone: "soon" };
  if (tile.is_new) return { text: "جديد", tone: "new" };
  if (tile.destination === "/subscription" && subscription?.is_active) {
    return { text: countDays(subscription.days_remaining), tone: "ok" };
  }
  if (tile.destination === "/account/missions" && progress?.enabled && progress.missions_total > 0) {
    return {
      text: `${digits(String(progress.missions_done))}/${digits(String(progress.missions_total))}`,
      tone: "",
      ltr: true,
    };
  }
  return null;
}

/** صفحةُ «الكل» — **الطلباتُ طلباتُ الرئيسية بعينها** (البلاطاتُ والاشتراكُ والمستوى) لا بابٌ ثانٍ. */
export function ServicesT2Screen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/");
  const attention = useDocumentsAttention();
  const [storefront, setStorefront] = useState<Storefront | null>(null);
  const [subscription, setSubscription] = useState<MySubscription | null>(null);
  const [progress, setProgress] = useState<MyProgress | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getStorefront()
      .then(setStorefront)
      .catch(() => setFailed(true));
    getMySubscription()
      .then(setSubscription)
      .catch(() => undefined);
    getMyProgress()
      .then(setProgress)
      .catch(() => undefined);
  }, []);

  return (
    <div className="t2 t2-svc">
      <div className="t2-svc-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <span className="t2-icon" aria-hidden="true">
              arrow_forward
            </span>
          </button>
          <h1 className="t2-title">خدماتك</h1>
        </div>
        {storefront === null ? (
          failed ? (
            <p className="t2-note danger" role="alert">
              <span className="t2-icon" aria-hidden="true">
                error
              </span>
              تعذّر قراءة الخدمات
            </p>
          ) : (
            <div className="t2-svc-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : storefront.tiles.length === 0 ? (
          <p className="t2-empty">لا خدمات معروضة في سوقك الآن.</p>
        ) : (
          <ServiceGrid
            tiles={storefront.tiles}
            subscription={subscription}
            progress={progress}
            covered={subscription?.is_active === true}
            attention={attention}
            navigate={navigate}
          />
        )}
      </div>
    </div>
  );
}
