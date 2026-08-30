/** جسرٌ إلى بطاقة الطلب الأصليّة وإلى حال الأذونات (قرارُ المالك 2026-08-30).
 *
 * **وهو صامتٌ في المتصفّح** كما هي البصمة: `Capacitor.isNativePlatform()` هو
 * الفاصل، **ولا يُدَّعى أنّ الفقاعةَ تعمل حيث لا وجودَ لها** — والشاشةُ تقول
 * ذلك بنصّها بدل أن تعرض مفتاحاً لا يفعل شيئاً.
 *
 * **وحالُ الأذونات تُقرأ في كلِّ فتحةٍ ولا تُخزَّن**: المستخدمُ يسحب الإذنَ من
 * إعدادات الهاتف **ولا يمرّ بنا** — فذاكرةٌ عن إذنٍ مُنح أمسِ تكذب اليوم، وهي
 * «حالٌ لا معالج» التي أرادها المالك.
 */

import { Capacitor, registerPlugin } from "@capacitor/core";

export interface PermissionStatus {
  notifications: boolean;
  location: boolean;
  backgroundLocation: boolean;
  overlay: boolean;
  fullScreenIntent: boolean;
  batteryUnrestricted: boolean;
  /** قناةُ الطلبات وحدَها — قد تُطفأ والمفتاحُ العامُّ مفتوح. */
  offerChannel: boolean;
  /** **دائماً `false`**: لا API يقرأ إعدادات المصنّع، ولا يُدَّعى خلافُ ذلك. */
  manufacturerSettingsKnown: boolean;
}

/** حمولةُ البطاقة كما ترسمها الأسطحُ الثلاثة — **قِيَمٌ خامٌ لا جملةٌ مصوغة**.
 *
 * **والسببُ نفسُ سبب `data` في إشعارات الخلفية**: الورقةُ والفقاعةُ وشاشةُ
 * ملء الشاشة ترسم الأجرةَ والمسافةَ والطريقَ بأحجامٍ مختلفة — **وجملةٌ
 * واحدةٌ مصوغةٌ هنا تُفقدها ذلك كلَّه**.
 */
// **غيرُ مُصدَّرٍ عن قصد**: قارئُ هذه الحقول **على الطرف الأصليّ**
// (`OfferData.java`) لا في الويب — و`check:readers` يقيس قرّاءَ الويب وحدَهم،
// **فتصديرُها يجعله يطلب قارئاً لا وجودَ له في نطاقه**. والنوعُ يُستنتج في
// موضع النداء، فلا يفقد المنادي شيئاً.
interface NativeOffer {
  rideId: string;
  fare: string;
  currency: string;
  /** «كاش» — طريقةُ الدفع كما تُعرض تحت الأجرة في التصميم. */
  method: string;
  /** «اقتصادي» — صنفُ المركبة. */
  category: string;
  /** «١٫٢ كم» — المسافةُ حتى الراكب. */
  distance: string;
  pickup: string;
  drop: string;
  seconds: number;
}

interface OfferAlertPlugin {
  status(): Promise<PermissionStatus>;
  requestOverlay(): Promise<void>;
  requestFullScreenIntent(): Promise<void>;
  openAppSettings(): Promise<void>;
  show(options: NativeOffer): Promise<void>;
  hide(): Promise<void>;
  setSession(options: {
    apiBase: string | null;
    accessToken: string | null;
  }): Promise<void>;
}

const plugin = registerPlugin<OfferAlertPlugin>("OfferAlert");

export function alertsAvailable(): boolean {
  return Capacitor.isNativePlatform();
}

export async function permissionStatus(): Promise<PermissionStatus | null> {
  if (!alertsAvailable()) return null;
  try {
    return await plugin.status();
  } catch {
    return null;
  }
}

export async function openOverlaySettings(): Promise<void> {
  if (alertsAvailable()) await plugin.requestOverlay().catch(() => undefined);
}

export async function openFullScreenSettings(): Promise<void> {
  if (alertsAvailable())
    await plugin.requestFullScreenIntent().catch(() => undefined);
}

export async function openAppSettings(): Promise<void> {
  if (alertsAvailable()) await plugin.openAppSettings().catch(() => undefined);
}

/** يُظهر البطاقةَ فوق كلِّ شيء — **ولا يُنادى والتطبيقُ ظاهر**. */
export async function showOfferAlert(options: NativeOffer): Promise<void> {
  if (!alertsAvailable()) return;
  await plugin.show(options).catch(() => undefined);
}

/** **ما تحتاجه الأسطحُ الأصليّةُ لتقبل بنفسها** — قاعدةُ الخدمة ورمزُ الوصول.
 *
 * **ويُنادى مع كلِّ تجديدٍ للرمز** لا مرّةً عند الدخول: عمرُ الرمز ثلاثون
 * دقيقة، **وواحدٌ محفوظٌ منذ ساعةٍ يجعل «اقبل» على الشاشة المقفلة يسقط
 * بصمت** — والكبتنُ يظنّ أنه أخذ الرحلة.
 *
 * **ولا رمزَ تجديدٍ يُمرَّر أبداً**: مُدوَّرٌ ذو استعمالٍ واحد (§23).
 */
export async function setNativeSession(
  apiBase: string | null,
  accessToken: string | null,
): Promise<void> {
  if (!alertsAvailable()) return;
  await plugin.setSession({ apiBase, accessToken }).catch(() => undefined);
}

export async function hideOfferAlert(): Promise<void> {
  if (!alertsAvailable()) return;
  await plugin.hide().catch(() => undefined);
}

const ASKED_KEY = "taxo.driver.overlay.asked";

/** **يُطلب إذنُ النافذة العائمة عند أوّل «استقبال طلبات» لا عند الباب**
 * (قرارُ المالك 2026-08-30).
 *
 * **ومرّةً واحدةً**: من رفضه لا يُساق إلى إعدادات النظام كلَّ صباح — **وطلبٌ
 * يتكرّر يُطفأ ومعه ما يحمله**، وهي قاعدةُ «حارسٌ يصيح على سليمٍ يُطفأ»
 * نفسُها. ومن أراده بعد ذلك يجده في شاشة الأذونات.
 *
 * **ولا يُسأل من مُنح**: القراءةُ من النظام قبل السؤال، **لا من ذاكرتنا** —
 * فمن منحه من الإعدادات مباشرةً لا يُسأل عمّا يملكه.
 */
export async function maybeAskForOverlay(): Promise<void> {
  if (!alertsAvailable()) return;
  const status = await permissionStatus();
  if (status === null || status.overlay) return;
  try {
    if (localStorage.getItem(ASKED_KEY) === "1") return;
    localStorage.setItem(ASKED_KEY, "1");
  } catch {
    // تخزينٌ محجوب — **يُسأل مرّةً في هذه الجلسة ولا يُمنع السؤالُ أصلاً**
  }
  const wants = window.confirm(
    "لتظهر لك بطاقة الطلب فوق أي شاشة وأنت تقود، يحتاج التطبيق إذن «الرسم فوق التطبيقات». بدونه سيصلك إشعار يملأ الشاشة بدلاً منها. أتفتح موضع المنح الآن؟",
  );
  if (wants) await openOverlaySettings();
}
