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
import { allServices, captainServices, type HomeTile } from "@/lib/captain-services";
import { useFeature } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { useGarage } from "@/lib/garage";
import { recordUse } from "@/lib/service-usage";
import { useGoBack } from "@/lib/back";
import { digits } from "@/lib/utils";
import { Icon, serviceIcon } from "@/taxo2";

import { countDays } from "./count";

import "./t2.css";
import "./ride.css"; import { tr } from "@/lib/i18n";

// **ستُّ الرئيسية وترتيبُها** (§١٠٩-د: الأكثرُ استعمالاً أوّلاً، والمطفأُ لا يظهر) — من بيتها الخالص المختبَر
export { HOME_TILES, homeTiles } from "@/lib/service-usage";

/** **عناوينُ خدمات الكبتن بالترجمة** — حرفيّاتُ `tr` هنا ليقرأها جردُ النصوص (`ar-inventory.json`) ويترجمها `fr.json`. */
function captainTitle(text: string): string {
  const titles: Record<string, string> = {
    "الاشتراك": tr("الاشتراك"),
    "المحفظة": tr("المحفظة"),
    "الأرباح": tr("الأرباح"),
    "المركبة والوثائق": tr("المركبة والوثائق"),
    "مهامّي": tr("مهامّي"),
    "الدعم": tr("الدعم"),
    "السلفة": tr("السلفة"),
    "المتجر والكراج": tr("المتجر والكراج"),
    "أحِل صديقك": tr("أحِل صديقك"),
    "المستحقّات": tr("المستحقّات"),
  };
  return titles[text] ?? text;
}

/** **خدماتُ الكبتن ثمّ بلاطاتُ اللوحة** (§١٠٩-د) — المفاتيحُ من بيوتها التي يسألها «حسابي» نفسُه، فلا تَعِد الرئيسيّةُ ببابٍ أغلقه. */
export function useHomeServices(panelTiles: readonly ServiceTile[]): HomeTile[] {
  const { profile } = useDriver();
  const country = profile?.user.country_code;
  const levels = useFeature(country, "driver_levels_enabled");
  const advances = useFeature(country, "driver_advances_enabled");
  const { enabled: garage } = useGarage();
  return allServices(captainServices({ levels, advances, garage }, captainTitle), panelTiles.filter(tileOpenable));
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
  tiles: HomeTile[];
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
        const tag = tileTag(tile, subscription, progress, covered);
        const ok = tile.destination === "/subscription" && covered;
        const dot = attention && tile.destination === DOCUMENTS_DESTINATION;
        const body = (
          <>
            <span className="t2-hm-tile-top">
              <span className={`t2-hm-tile-icon${ok ? " ok" : ""}`}>
                <Icon name={tile.glyph ?? serviceIcon(tile.icon)} fill />
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
            onClick={() => {
              // **«الأكثرُ استعمالاً أوّلاً»** (§١٠٩-د) — عدٌّ في هذا الهاتف وحدَه
              recordUse(tile.id);
              navigate(tile.destination!);
            }}
            // **النقطةُ تُقال لقارئ الشاشة** — هي معنًى لا زينة
            aria-label={dot ? tr("{0} — وثائق تحتاج انتباهك", { 0: tile.title }) : undefined}
          >
            {body}
          </button>
        ) : (
          <button key={tile.id} type="button" className="t2-hm-tile" onClick={() => setNotice(tr("{0} — قريباً", { 0: tile.title }))}>
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
  covered: boolean,
): { text: string; tone: string; ltr?: boolean } | null {
  if (tile.status === "soon") return { text: tr("قريباً"), tone: "soon" };
  if (tile.is_new) return { text: tr("جديد"), tone: "new" };
  if (tile.destination === "/subscription" && subscription?.is_active) {
    // **«سفير TAXO»**: دائمٌ لا عدّاد
    if (subscription.ambassador) return { text: tr("دائم"), tone: "ok" };
    return { text: countDays(subscription.days_remaining), tone: "ok" };
  }
  // **«جدّد» حين لا يغطّيه اشتراكٌ فعلاً** — بعد أن يُقرأ اشتراكُه لا قبل (فلا تومض الشارةُ لحظةَ التحميل)
  if (tile.destination === "/subscription" && subscription !== null && !covered) {
    return { text: tr("جدّد"), tone: "warn" };
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
  // **خدماتُ الكبتن لا تنتظر اللوحة**: تُرسم فوراً، وبلاطاتُ اللوحة تُلحق حين تصل
  const services = useHomeServices(storefront?.tiles ?? []);

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
          <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">{tr("كل الخدمات")}</h1>
        </div>
        <ServiceGrid
          tiles={services}
          subscription={subscription}
          progress={progress}
          covered={subscription?.is_active === true}
          attention={attention}
          navigate={navigate}
        />
        {storefront === null ? (
          failed ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" />
              {tr("تعذّر قراءة الخدمات")}
            </p>
          ) : (
            <div className="t2-svc-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : null}
      </div>
    </div>
  );
}
