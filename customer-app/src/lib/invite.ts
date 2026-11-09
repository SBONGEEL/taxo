/** رمزُ الدعوة الذي جاء به صاحبُه — **يُلتقط قبل أيِّ شاشة ويُملأ في «أنشئ حسابك»** (أمرُ المالك ٢٠٢٦-١١-٠٨).
 *
 * **ثلاثةُ أبوابٍ يصل منها الرمز، ولكلٍّ حالُه:**
 *
 * | حالُ الهاتف | من أين يصل |
 * |---|---|
 * | التطبيقُ مثبَّتٌ ويعمل | `appUrlOpen` — رابطُ تطبيقٍ موثَّق `https://taxo.tajora.ly/i/<الرمز>` |
 * | مثبَّتٌ ومُغلَق | `getLaunchUrl()` — و`appUrlOpen` **لا يُطلق** في الإقلاع البارد |
 * | **غيرُ مثبَّت** | الرابطُ يحوّل إلى Google Play بـ`referrer=taxo_ref=<الرمز>`، **ومُحيلُ التثبيت** يعيده في أوّل فتح |
 *
 * **والحكمُ في الخلفية لا هنا**: الرمزُ يُرسل مع التسجيل فتقبله أو ترفضه بحقلها (`referral_code`) **قبل أن يُحرق رمزُ التحقّق**.
 * فما هنا ملءٌ لا تحقّق — وصاحبُ الحقل يمحوه أو يغيّره بيده.
 *
 * **ولا صفحةَ ويب ولا التفاف** (شرطُ المالك): الرابطُ تحويلٌ واحدٌ إلى المتجر، والملءُ داخل التطبيق.
 */
import { App } from "@capacitor/app";
import { Capacitor, registerPlugin } from "@capacitor/core";
import { Share } from "@capacitor/share";

import { tokens } from "@/api/client";
import type { ShareOutcome } from "@/lib/share-app";
import { tr } from "@/lib/i18n";

/** الرابطُ الذي يُشارَك — **من النطاق العامّ** لا من نطاق الغلاف، فهو ما يعرفه الناسُ وما يوثّقه `assetlinks.json`. */
export const INVITE_BASE = "https://taxo.tajora.ly/i/";

const KEY = "taxo.invite";
const REFERRER_READ = "taxo.invite.referrer-read";
/** حدثٌ يبلغ «أنشئ حسابك» إن وصل الرمزُ بعد أن رُسمت (مُحيلُ التثبيت غير متزامن). */
export const INVITE_EVENT = "taxo:invite";

/** أبجديةُ الخلفية (`referrals.ALPHABET`) وطولُ حقلها (٤–١٦) — **ما خالفها لا يُحفظ**، فلا يُملأ الحقلُ بقمامة. */
function clean(raw: string | null | undefined): string | null {
  const code = (raw ?? "").trim().toUpperCase();
  return /^[A-Z0-9]{4,16}$/.test(code) ? code : null;
}

function store(code: string): void {
  try {
    localStorage.setItem(KEY, code);
  } catch {
    /* مخزنٌ مقفل — الحقلُ يبقى يُكتب باليد */
  }
  window.dispatchEvent(new CustomEvent(INVITE_EVENT, { detail: code }));
}

export function pendingInvite(): string | null {
  try {
    return clean(localStorage.getItem(KEY));
  } catch {
    return null;
  }
}

/** بعد تسجيلٍ ناجح — **الرمزُ يُستعمل مرّةً**، ولا يُملأ لحسابٍ ثانٍ على الهاتف نفسِه. */
export function forgetInvite(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* لا شيء */
  }
}

/** `https://taxo.tajora.ly/i/ABCD2345` ⇐ `ABCD2345` — أو لا شيء. */
function codeOfUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== "taxo.tajora.ly") return null;
    const match = /^\/i\/([^/]+)\/?$/.exec(parsed.pathname);
    return match ? clean(decodeURIComponent(match[1])) : null;
  } catch {
    return null;
  }
}

function adoptUrl(url: string): void {
  const code = codeOfUrl(url);
  if (!code) return;
  store(code);
  // **من له جلسةٌ لا يُنقَل**: الرمزُ للتسجيل، وصاحبُ حسابٍ فتح رابطاً من صديقٍ لا يُخرَج من شاشته
  if (!tokens.access() && !window.location.pathname.startsWith("/register")) {
    window.location.replace("/register");
  }
}

type ReferrerPlugin = { get(): Promise<{ referrer: string }> };
const installReferrer = registerPlugin<ReferrerPlugin>("InstallReferrer");

/** **يُسأل مرّةً في عمر التثبيت**: المُحيلُ ثابتٌ لا يتغيّر، والسؤالُ اتصالٌ بخدمة المتجر. وغلافٌ قديمٌ بلا الملحق يُتخطّى بصمت. */
async function readInstallReferrer(): Promise<void> {
  if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("InstallReferrer")) return;
  try {
    if (localStorage.getItem(REFERRER_READ)) return;
  } catch {
    return;
  }
  try {
    const { referrer } = await installReferrer.get();
    const code = clean(new URLSearchParams(referrer ?? "").get("taxo_ref"));
    if (code && !pendingInvite()) store(code);
    localStorage.setItem(REFERRER_READ, "1");
  } catch {
    /* خدمةُ المتجر لم تُجب — يُعاد السؤالُ في الفتح التالي */
  }
}

/** **يُسجَّل مرّةً عند الإقلاع** قبل أيِّ شاشة — كـ`listenForHandoff`. */
export function listenForInvite(): void {
  void App.addListener("appUrlOpen", ({ url }) => adoptUrl(url)).catch(() => undefined);
  void App.getLaunchUrl()
    .then((launch) => {
      if (launch?.url) adoptUrl(launch.url);
    })
    .catch(() => undefined);
  void readInstallReferrer();
}

/** **الرسالةُ تحمل الرابط** (أمرُ المالك): من ضغطه وعنده التطبيقُ فُتح ورمزُه مكتوب، ومن ليس عنده ذهب إلى المتجر ورمزُه معه.
 *  **وورقةُ النظام من `@capacitor/share`** — `WebView` لا يعرف `navigator.share`، فكانت المشاركةُ تقع على النسخ صامتة. */
export async function shareInvite(code: string): Promise<ShareOutcome> {
  const url = `${INVITE_BASE}${code}`;
  const title = tr("TAXO — تطبيق الرحلات");
  const text = tr("سجّل في تاكسو برمزي {0}", { 0: code });
  const cancelled = (error: unknown) => {
    const message = String((error as { message?: string })?.message ?? error).toLowerCase();
    return message.includes("cancel") || message.includes("abort");
  };
  if (Capacitor.isPluginAvailable("Share")) {
    try {
      await Share.share({ title, text, url, dialogTitle: tr("ادعُ صديقك") });
      return "shared";
    } catch (error) {
      if (cancelled(error)) return "cancelled";
    }
  } else if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return "shared";
    } catch (error) {
      if (cancelled(error)) return "cancelled";
    }
  }
  try {
    await navigator.clipboard.writeText(`${text}\n${url}`);
    return "copied";
  } catch {
    return "failed";
  }
}
