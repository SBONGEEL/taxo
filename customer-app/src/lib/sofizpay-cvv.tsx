/** **CVV2 لا PIN — قبل صفحة البنك وفوقها** (SPEC §٨٥/٩، أمرُ المالك ٢٠٢٦-١٠-٣٠): أوّلُ رفضٍ حقيقيٍّ لـSofizPay كان كبتناً أدخل رمزَ PIN
 * (٤ أرقام) بدل CVV2 (٣ أرقام خلف البطاقة) — فرُدّت الدفعةُ وهو يظنّ البطاقةَ عاطلة.
 *
 * **ثلاثةُ أشياءَ في ملفٍّ واحد، متطابقٍ بايتاً في التطبيقين** (كـ`pay-return.tsx`):
 * 1. `CvvNotice` — التنبيهُ والرسمُ على شاشة الدفع عندنا **قبل** الإرسال، لكلِّ شاشةٍ تقود إلى SofizPay (الشحن · «اشحن مبلغ الرحلة» ·
 *    الخدمات · الدَّين · الاشتراك تمرّ كلُّها من `PayRequestT2`).
 * 2. `CardBackIllustration` — رسمٌ متّجهيٌّ من عندنا لظهر بطاقةٍ عامّة («الذهبية / CIB»): شريطُ التوقيع والأرقامُ الثلاثةُ مطوَّقةٌ ببرتقاليّ
 *    TAXO. **لا صورةَ بطاقةٍ حقيقيّة ولا شعارَ بريد الجزائر أو SATIM.**
 * 3. `CheckoutFrameScreen` — **شريطُنا الرفيعُ فوق صفحة البنك داخل التطبيق** بالتنبيه نفسِه وزرِّ «؟» يفتح الرسمَ ورقةً سفليّةً بلا مغادرة
 *    الدفع؛ وصفحةُ البنك في `iframe` تحته فلا يغطّي نموذجَها ولا أزرارَها.
 *
 * **وحدُّ الإطار مقيسٌ لا مفترَض**: `sofizpay.com` (صفحةُ التجربة) يرسل `X-Frame-Options: ALLOWALL` (قِيس ٢٠٢٦-١٠-٣٠)؛ **ومضيفُ SATIM الحيّ
 * (`cib.satim.dz`) يردّ 403 لكلِّ طلبٍ من خارج الجزائر** فلم تُقَس سياستُه — وبطاقةٌ لا تُفتح داخل إطارٍ ممنوعٍ تعني دفعاً مقطوعاً بلا خطأٍ
 * يظهر. فالإطارُ **للمضيفين المقيسين وحدَهم** (`FRAMABLE_HOSTS`)، وما سواه يُفتح كما كان (`goToCheckout`) **بعد التنبيه نفسِه**؛
 * وحين يُقاس الحيُّ من الجزائر يُضاف مضيفُه هنا بسطرٍ واحد.
 *
 * **والعودةُ من داخل الإطار**: صفحةُ العودة (`PayReturnT2` · `PublicPayReturn`) تنادي `announceFrameReturn` فتُبلغ الإطارَ الأبَ
 * بـ`postMessage` من أصلنا نفسِه، والأبُ يذهب إلى «نتيجة الدفع». وأبوابُ `pay-return.tsx` الثلاثةُ باقيةٌ لما يُفتح خارج الإطار.
 */
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { tr } from "@/lib/i18n";
import { goToCheckout } from "@/lib/pay-return";
import { Icon } from "@/taxo2";

/** مضيفو صفحات الدفع **المقيسُ** سماحُهم بالإطار — انظر رأسَ الملفّ قبل أن تضيف */
export const FRAMABLE_HOSTS: readonly string[] = ["sofizpay.com"];
const FRAME_ROUTE = "/wallet/pay/frame";
const RETURN_ROUTE = "/wallet/pay/return";
const MESSAGE = "taxo.pay.return";

export function isSofizPay(gatewayName: string | null | undefined): boolean {
  return (gatewayName ?? "").toLowerCase().includes("sofizpay");
}

function hostOf(url: string): string | null {
  try {
    return new URL(url).host.toLowerCase();
  } catch {
    return null;
  }
}

export function framable(url: string): boolean {
  const host = hostOf(url);
  return host !== null && FRAMABLE_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
}

/** **يحلّ محلَّ `goToCheckout` على كلِّ شاشةٍ تقود إلى وسيط**: SofizPay على مضيفٍ مقيسٍ ⇐ إطارُنا بشريطه؛ وإلا الصفحةُ كما كانت. */
export function openCheckout(
  navigate: (to: string) => void, requestId: string, url: string, gatewayName: string | null | undefined,
): void {
  if (isSofizPay(gatewayName) && framable(url)) {
    navigate(`${FRAME_ROUTE}?r=${encodeURIComponent(requestId)}&u=${encodeURIComponent(url)}`);
    return;
  }
  goToCheckout(requestId, url);
}

/** تناديه صفحةُ العودة: إن كانت داخل إطارنا أبلغت الأبَ فذهب إلى «نتيجة الدفع» — وإلا لا شيء. */
export function announceFrameReturn(requestId: string | null): void {
  if (!requestId || window.parent === window) return;
  try {
    window.parent.postMessage({ type: MESSAGE, r: requestId }, window.location.origin);
  } catch {
    /* أصلٌ مختلف — ليست صفحتَنا */
  }
}

export function CvvText({ className }: { className?: string }) {
  return <p className={className ?? "t2-cvv-text"}>{tr("ستُطلب منك 3 أرقام من خلف بطاقتك (CVV2)، لا رمز PIN")}</p>;
}

/** ظهرُ بطاقةٍ عامّة — الشريطُ المغنطيسيّ، شريطُ التوقيع، والأرقامُ الثلاثةُ الأخيرةُ مطوَّقة. */
export function CardBackIllustration({ compact = false }: { compact?: boolean }) {
  return (
    <svg
      className={compact ? "t2-cvv-card compact" : "t2-cvv-card"}
      viewBox="0 0 340 214"
      role="img"
      aria-label={tr("ظهر البطاقة: الأرقام الثلاثة الأخيرة بجانب شريط التوقيع هي CVV2")}
    >
      <defs>
        <linearGradient id="cvvCard" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2b3038" />
          <stop offset="1" stopColor="#15181d" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="336" height="210" rx="18" fill="url(#cvvCard)" stroke="#454b55" strokeWidth="2" />
      <rect x="2" y="30" width="336" height="40" fill="#0b0d10" />
      <rect x="26" y="96" width="230" height="38" rx="4" fill="#f2f0eb" />
      <g stroke="#c9c2b5" strokeWidth="1.5">
        <line x1="36" y1="106" x2="236" y2="106" /><line x1="36" y1="115" x2="236" y2="115" /><line x1="36" y1="124" x2="236" y2="124" />
      </g>
      <text x="40" y="128" fontSize="13" fontWeight="700" fill="#6e7681" fontFamily="monospace" direction="ltr" style={{ letterSpacing: 2 }}>1234</text>
      <rect x="262" y="96" width="52" height="38" rx="4" fill="#fff4ec" />
      <text x="288" y="122" fontSize="18" fontWeight="800" fill="#111" fontFamily="monospace" textAnchor="middle" direction="ltr">•••</text>
      <circle cx="288" cy="115" r="33" fill="none" stroke="#f05a28" strokeWidth="5" />
      <text x="288" y="172" fontSize="15" fontWeight="800" fill="#f05a28" textAnchor="middle" direction="ltr">CVV2</text>
      <text x="30" y="190" fontSize="12" fontWeight="700" fill="#9aa3ad" direction="ltr">{tr("الذهبية / CIB")}</text>
    </svg>
  );
}

/** التنبيهُ والرسمُ على شاشة الدفع عندنا — قبل «ادفع عبر SofizPay». */
export function CvvNotice({ gatewayName }: { gatewayName?: string | null }) {
  if (!isSofizPay(gatewayName)) return null;
  return (
    <section className="t2-cvv" aria-label={tr("قبل أن تدفع")}>
      <span className="t2-cvv-mark" aria-hidden="true"><Icon name="credit_card" /></span>
      <div className="t2-cvv-body">
        <CvvText />
        <CardBackIllustration />
        <p className="t2-cvv-sub">{tr("رمز PIN تستعمله في الصرّاف فقط — ولا تكتبه في صفحة الدفع.")}</p>
      </div>
    </section>
  );
}

/** **صفحةُ البنك داخل التطبيق وفوقها شريطُنا** — `?r=<طلب>&u=<رابط الصفحة>`. */
export function CheckoutFrameScreen() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestId = params.get("r") ?? "";
  const url = params.get("u") ?? "";
  const [help, setHelp] = useState(false);
  const ok = requestId !== "" && framable(url);

  useEffect(() => {
    if (!ok) return;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const data = event.data as { type?: string; r?: string } | null;
      if (data && data.type === MESSAGE && typeof data.r === "string") {
        navigate(`${RETURN_ROUTE}?r=${encodeURIComponent(data.r)}`, { replace: true } as never);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [navigate, ok]);

  // **رابطٌ ليس لمضيفٍ مقيس أو بلا طلب** — الطريقُ القديمُ لا صفحةٌ فارغة
  useEffect(() => {
    if (!ok && requestId && url) goToCheckout(requestId, url);
  }, [ok, requestId, url]);
  if (!ok) return null;

  return (
    <div className="t2 t2-frame" role="main">
      <div className="t2-frame-bar" role="note">
        <span className="t2-frame-mark" aria-hidden="true"><Icon name="credit_card" /></span>
        <CvvText className="t2-frame-text" />
        <button type="button" className="t2-frame-help" aria-label={tr("أين أجد CVV2؟")} onClick={() => setHelp(true)}>؟</button>
      </div>
      <iframe
        className="t2-frame-page"
        src={url}
        title={tr("صفحة الدفع")}
        allow="payment"
        onLoad={(event) => {
          // **إشارةُ العودة الثانية — من الأب نفسِه**: حين يعود الإطارُ إلى أصلنا تُقرأ وجهتُه مباشرةً (أصلٌ واحد)، فلا يتوقّف الذهابُ
          // إلى «نتيجة الدفع» على أن يعمل سكربتُ الصفحة داخل الإطار (قِيس ٢٠٢٦-١٠-٣٠: تخزينُ الصفحة داخل الإطار قد يُرفض)
          try {
            const href = event.currentTarget.contentWindow?.location.href ?? "";
            if (href.includes(RETURN_ROUTE)) {
              const r = new URL(href).searchParams.get("r") ?? requestId;
              navigate(`${RETURN_ROUTE}?r=${encodeURIComponent(r)}`, { replace: true } as never);
            }
          } catch {
            /* أصلٌ آخر — صفحةُ البنك ما زالت مفتوحة */
          }
        }}
      />
      <p className="t2-frame-fallback">
        <button type="button" className="t2-link" onClick={() => goToCheckout(requestId, url)}>{tr("لا تظهر صفحة الدفع؟ افتحها كاملةً")}</button>
      </p>
      {help ? (
        <div className="t2-frame-sheet-back" onClick={() => setHelp(false)} role="presentation">
          <div className="t2-frame-sheet" role="dialog" aria-modal="true" aria-label={tr("أين أجد CVV2؟")} onClick={(e) => e.stopPropagation()}>
            <h2 className="t2-frame-sheet-title">{tr("أين أجد CVV2؟")}</h2>
            <CardBackIllustration />
            <p className="t2-cvv-sub">{tr("3 أرقام بجانب شريط التوقيع خلف بطاقتك — ليست رمز PIN الذي تستعمله في الصرّاف.")}</p>
            <button type="button" className="t2-button primary t2-m-cta" onClick={() => setHelp(false)}>{tr("فهمت")}</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
