/** **العودةُ من صفحة البطاقة إلى TAXO دائماً** (أمرُ المالك ٢٠٢٦-١٠-٢٧، SPEC §٨٤) — لا Google ولا صفحةٌ بيضاء.
 *
 * **ما قِيس**: الغلافُ يفتح صفحةَ Chargily في المتصفّح (لا `allowNavigation` له)، وصفحةُ بريد الجزائر (`epay.poste.dz`) حين تفشل
 * تعود «إلى الوراء» — **وفي لسانٍ فتحه التطبيق ليس وراءه إلا صفحةُ بداية المتصفّح: Google**. وعنوانُ العودة (`/wallet/pay/return`)
 * إن وصلها يُفتح في المتصفّح موقعاً بلا جلسة. **فالحقيقةُ لا تصل صاحبَها من أيِّ الطريقين.**
 *
 * **ثلاثةُ أبوابٍ تعيده، أيُّها وقع أوّلاً**:
 * 1. **عودتُه إلى التطبيق بنفسه** — بأيِّ طريق: `rememberCheckout` يحفظ الطلبَ عند فتح الصفحة، و`PayReturnLinks` يأخذه إلى
 *    «نتيجة الدفع» داخل التطبيق حين يعود ظاهراً — **وهي تسأل الخادمَ عن الحال الحقيقيّة** (`refresh`).
 * 2. **رابطُ التطبيق** `taxo-driver://pay?r=…` · `taxo-rider://pay?r=…` (`AndroidManifest.xml`) — من زرّ صفحة العودة في المتصفّح.
 * 3. **صفحةُ العودة في المتصفّح بلا جلسة** (`PublicPayReturn`): «افتح التطبيق لترى النتيجة» وزرُّه — **ولا حالَ تُعرض هنا**: الحالُ
 *    لصاحب الطلب وحدَه، والمتصفّحُ لا يعرف صاحبَه.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين، متطابقةٌ بايتاً** — والتطبيقُ يُمرَّر لا يُكتب فيها.
 */
import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { tr } from "@/lib/i18n";
import { removeBootFrame } from "@/lib/splash";
import { Icon } from "@/taxo2";
import "@/taxo2";
import "./update-gate.css";

type AppName = "rider" | "driver";

const KEY = "taxo.pay.open";
const RETURN = "/wallet/pay/return";
/** **صفحةُ البطاقة تعيش نحو خمسِ دقائقَ من فتح الدفعة** — قِيس على Edahabia (فُتحت 16:34:34 وقالت الصفحةُ «تنتهي 16:39») */
export const CARD_PAGE_MINUTES = 5;
/** **أقلُّ من هذا ليس عودة** — الصفحةُ لم تُفتح بعدُ والتطبيقُ ما زال ظاهراً */
const MIN_AWAY_MS = 2000;
/** **وأقدمُ من هذا لا يُعاد إليه** — فتحةٌ بعد أيّامٍ لا تُستقبل بنتيجة دفعةٍ نُسيت */
const MAX_AWAY_MS = 60 * 60 * 1000;

const SCHEME: Record<AppName, string> = { rider: "taxo-rider", driver: "taxo-driver" };
const PACKAGE: Record<AppName, string> = { rider: "ly.tajora.rider", driver: "ly.tajora.driver" };
const TOKEN: Record<AppName, string> = { rider: "taxo.access_token", driver: "taxo.driver.access_token" };

interface Open {
  id: string;
  at: number;
}

function read(): Open | null {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "null") as Open | null;
    return value && typeof value.id === "string" && typeof value.at === "number" ? value : null;
  } catch {
    return null;
  }
}

function forget(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* تخزينٌ محجوب — لا شيءَ يُنسى */
  }
}

/** **يُنادى بدل `window.location.assign(checkout_url)`** — يحفظ الطلبَ ثمّ يفتح صفحةَ الوسيط. */
export function goToCheckout(requestId: string, url: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ id: requestId, at: Date.now() } satisfies Open));
  } catch {
    /* تخزينٌ محجوب — يبقى رابطُ العودة وزرُّها */
  }
  window.location.assign(url);
}

/** «نتيجة الدفع» تنادي هذا حين تُفتح — **وصلها صاحبُها فلا يُعاد إليها ثانية**. */
export function settledReturn(): void {
  forget();
}

function requestOf(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.host === "pay" ? parsed.searchParams.get("r") : null;
  } catch {
    return null;
  }
}

/** **تحت الموجّه** — يأخذ صاحبَ الدفعة إلى «نتيجة الدفع» حين يعود إلى التطبيق أو يفتحه رابطُ `…://pay?r=`. */
export function PayReturnLinks() {
  const navigate = useNavigate();
  useEffect(() => {
    const show = (id: string) => {
      forget();
      navigate(`${RETURN}?r=${encodeURIComponent(id)}`, { replace: true });
    };
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      const open = read();
      if (!open) return;
      const away = Date.now() - open.at;
      if (away > MAX_AWAY_MS) forget();
      else if (away >= MIN_AWAY_MS) show(open.id);
    };
    document.addEventListener("visibilitychange", onVisible);
    // **و`resume` من الغلاف** — بعضُ أجهزة أندرويد لا تُطلق `visibilitychange` حين يعود التطبيقُ من المتصفّح
    const resumed = App.addListener("resume", onVisible).catch(() => null);
    const listener = App.addListener("appUrlOpen", ({ url }) => {
      const id = requestOf(url);
      if (id) show(id);
    }).catch(() => null);
    // **الإقلاعُ الباردُ يُسأل صراحةً** — كما في `handoff-listener.ts`
    void App.getLaunchUrl()
      .then((launch) => {
        const id = launch?.url ? requestOf(launch.url) : null;
        if (id) show(id);
      })
      .catch(() => undefined);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      void listener.then((handle) => handle?.remove());
      void resumed.then((handle) => handle?.remove());
    };
  }, [navigate]);
  return null;
}

/** **صفحةُ العودة في متصفّحٍ بلا جلسة** — المتصفّحُ الذي فتحه التطبيقُ لصفحة البطاقة. */
export function isPublicPayReturn(app: AppName, pathname: string): boolean {
  if (Capacitor.isNativePlatform() || pathname.replace(/\/$/, "") !== RETURN) return false;
  try {
    return !localStorage.getItem(TOKEN[app]);
  } catch {
    return true;
  }
}

export function PublicPayReturn({ app }: { app: AppName }) {
  // **إطارُ الإقلاع يُزال هنا** — هذه الصفحةُ لا تمرّ بالترحيب الذي يزيله (قِيس على المحاكي: النصُّ في الصفحة والشاشةُ مُعتِمة)
  useEffect(() => removeBootFrame(), []);
  const id = new URLSearchParams(window.location.search).get("r") ?? "";
  // **داخل إطار التطبيق** (`sofizpay-cvv.tsx`): الأبُ يسمع ويذهب إلى «نتيجة الدفع» — ولا يُستورد من هناك (دورٌ في الاستيراد)
  useEffect(() => {
    if (!id || window.parent === window) return;
    try {
      window.parent.postMessage({ type: "taxo.pay.return", r: id }, window.location.origin);
    } catch {
      /* أصلٌ مختلف */
    }
  }, [id]);
  const open = `intent://pay?r=${encodeURIComponent(id)}#Intent;scheme=${SCHEME[app]};package=${PACKAGE[app]};end`;
  return (
    <div className="t2 t2-update" role="main">
      <div className="t2-update-card">
        <div className="t2-update-scroll">
          <span className="t2-update-mark" aria-hidden="true">
            <Icon name="receipt_long" />
          </span>
          <h1 className="t2-update-title">{tr("عُدتَ من صفحة الدفع")}</h1>
          <p className="t2-update-text">
            {tr("افتح تطبيق TAXO لترى نتيجة دفعتك. لا تدفع مرّةً ثانية قبل أن تراها — ولا يُخصم شيءٌ لم يكتمل.")}
          </p>
        </div>
        <a className="t2-button action t2-update-go" href={open}>
          {tr("افتح تطبيق TAXO")}
        </a>
        <p className="t2-update-text">{tr("إن لم يُفتح: افتح التطبيق بنفسك، وستظهر لك النتيجة.")}</p>
      </div>
    </div>
  );
}
