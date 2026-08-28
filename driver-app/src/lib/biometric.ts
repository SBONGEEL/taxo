/** دخولٌ سريعٌ بالبصمة أو الوجه — **البصمةُ تفتح رمزاً، ولا تصدّق أحداً**.
 *
 * **والخلفيةُ لا تعرف بصمةً ألبتّة** (قرارُ المالك 2026-08-29): لا مسارَ دخولٍ
 * جديد، ولا تصديقَ عندها. الجهازُ يشهد لنفسِه، **والذي يُقدَّم للخلفية هو رمزُ
 * التجديد نفسُه كما اليوم** — فالميزةُ كلُّها في الواجهة، وسطحُ الهجوم لا
 * يتّسع بحرف.
 *
 * ## ولمَ **رمزُ التجديد وحدَه** ولمَ **في مكانٍ واحد**
 *
 * **رمزُ التجديد يُستهلك مرّةً ويُدوَّر** — قِيس في `token_service.rotate_refresh_token`:
 * كلُّ نداءِ `/auth/refresh` **يحذف مفتاحَ Redis القديم** ويُصدر زوجاً جديداً،
 * وإعادةُ استعمال المستهلَك تُرفض بـ«جلسة منتهية أو أُبطلت».
 *
 * **فنسختان من رمزٍ يُدوَّر ليستا نسختين — بل واحدةٌ حيّةٌ وأخرى ميتةٌ بعد أوّل
 * تجديد.** ولو خزّنّا نسخةً في المخزن الآمن وتركنا الأصلَ في `localStorage`
 * لَعملت الميزةُ يوماً ثمّ ردَّت «جلسة منتهية» بلا سبب يظهر — **وهو الشكلُ
 * الثامن بحرفه**: بابان ينشران الشيءَ نفسَه، وكلٌّ صادقٌ منفرداً.
 *
 * **فالبيتُ واحد**: حين تُشعَل الميزة، رمزُ التجديد **يعيش في المخزن الآمن
 * وحدَه** ويُنزع من `localStorage`، **ويُعاد كتابتُه هناك بعد كلِّ تدوير**.
 * ورمزُ الوصول يبقى كما هو (عمرُه ٣٠ دقيقة) — فمن فتح التطبيقَ خلالها يدخل
 * بلا بصمةٍ أصلاً، وهو المقصود لا نقص.
 *
 * ## ولا كلمةَ مرورٍ هنا بحال
 *
 * **لا مشفَّرةً ولا مُرمَّزة** (قرارُ المالك). المخزَّنُ رمزُ تجديدٍ **يُبطله
 * الخادمُ متى شاء** — وكلمةُ المرور لا تُبطَل، فتسريبُها يعيش مع صاحبه.
 *
 * ## وأين يسكن
 *
 * `@aparajita/capacitor-secure-storage` — **Keystore على أندرويد وKeychain على
 * iOS**، لا `localStorage`. **و`localStorage` مفتاحُه الأصلُ** (origin) فتشاركه
 * كلُّ شيفرةٍ تعمل في الغلاف؛ والمخزنُ الآمن مفتاحُه **حزمةُ التطبيق**.
 *
 * **وأثرُ النكهتين مقيسٌ من هذا الباب**: النسخةُ التجريبية معرّفُها
 * `…rider.test`/`…driver.test` — **حزمةٌ أخرى بمجلَّد بياناتٍ آخرَ ومدخلِ
 * Keystore آخر**، فلا تختلط نسختان على هاتفٍ واحد. (والعزلُ حكمُ المنصّة لا
 * إعدادٌ نضبطه، **ولم يُقَس على جهاز** — يُقال ولا يُدَّعى.)
 *
 * ## وفي المتصفّح: لا زرَّ إطلاقاً
 *
 * `Capacitor.isNativePlatform()` أولاً، **قبل أيِّ نداءِ ملحق**. ومن لا بصمةَ
 * على جهازه **لا يرى الميزةَ**، ولا رقمَ سرّيَّ بديلاً — **بابٌ ثانٍ يضعف
 * الأول** (قرارُ المالك).
 */

import { BiometricAuth, BiometryType } from "@aparajita/capacitor-biometric-auth";
import { SecureStorage } from "@aparajita/capacitor-secure-storage";
import { Capacitor } from "@capacitor/core";

/** **المخزَّنُ الوحيد** — رمزُ تجديدٍ لا غير. */
const SECURE_KEY = "taxo.driver.biometric.refresh";

/** **التفضيلُ ليس سرّاً** فيعيش حيث تعيش التفضيلات: «أيريد المستخدمُ الميزة؟»
 *  — والجوابُ لا يفتح شيئاً بلا الرمز الذي في المخزن الآمن. */
const PREF_KEY = "taxo.driver.biometric.enabled";

export type BiometryKind = "fingerprint" | "face" | "generic";

export interface BiometryStatus {
  /** **الجهازُ يملكها ومسجَّلةٌ فيه** — وإلا فلا زرَّ ولا مفتاحَ في الإعدادات. */
  available: boolean;
  kind: BiometryKind;
  /** أشعلها المستخدمُ من إعداداته. */
  enabled: boolean;
  /** **ثمّة رمزٌ محفوظٌ فعلاً** — والزرُّ لا يُرسم بدونه ولو كان التفضيلُ مشتعلاً. */
  armed: boolean;
}

export const UNAVAILABLE: BiometryStatus = {
  available: false,
  kind: "generic",
  enabled: false,
  armed: false,
};

function kindOf(type: BiometryType): BiometryKind {
  switch (type) {
    case BiometryType.touchId:
    case BiometryType.fingerprintAuthentication:
      return "fingerprint";
    case BiometryType.faceId:
    case BiometryType.faceAuthentication:
      return "face";
    default:
      return "generic";
  }
}

/** اسمٌ يُعرض للمستخدم — **بما يملكه جهازُه لا بالعموم**. */
export function biometryLabel(kind: BiometryKind): string {
  if (kind === "face") return "بصمة الوجه";
  if (kind === "fingerprint") return "بصمة الإصبع";
  return "قفل الجهاز";
}

function prefEnabled(): boolean {
  try {
    return localStorage.getItem(PREF_KEY) === "1";
  } catch {
    return false;
  }
}

/** **الحالُ تُقاس ولا تُفترض** — وفي المتصفّح تعود «غيرُ متاحة» بلا نداءِ ملحق. */
export async function biometryStatus(): Promise<BiometryStatus> {
  if (!Capacitor.isNativePlatform()) return UNAVAILABLE;
  try {
    const check = await BiometricAuth.checkBiometry();
    if (!check.isAvailable) return UNAVAILABLE;
    const enabled = prefEnabled();
    // **«أمشتعلٌ التفضيل؟» غيرُ «أثمّة رمز؟»** — والخروجُ يمحو الثاني ويترك
    // الأول، فمن رسم الزرَّ على التفضيل وحدَه رسم زرّاً يفشل عند الضغط
    const armed = enabled ? (await readToken()) !== null : false;
    return { available: true, kind: kindOf(check.biometryType), enabled, armed };
  } catch {
    // **ملحقٌ لا يجيب يُقرأ «غيرُ متاح» لا يُسقط الشاشة**: هذه شاشةُ دخول،
    // وسقوطُها يمنع الدخولَ بالطريق العاديِّ أيضاً
    return UNAVAILABLE;
  }
}

async function readToken(): Promise<string | null> {
  try {
    return await SecureStorage.getItem(SECURE_KEY);
  } catch {
    return null;
  }
}

/** يُكتب بعد **كلِّ** تدوير — وهو ما يمنع الشكلَ الثامن. */
export async function rememberToken(refreshToken: string): Promise<void> {
  if (!Capacitor.isNativePlatform() || !prefEnabled()) return;
  try {
    await SecureStorage.setItem(SECURE_KEY, refreshToken);
  } catch (error) {
    console.warn("تعذّر حفظ رمز التجديد في المخزن الآمن", error);
  }
}

/** **المحوُ في أربع** (قرارُ المالك): خروج · تبديلُ كلمة المرور · ردُّ الخادم
 *  بأن الجلسةَ لم تعد صالحة · إطفاءُ الميزة.
 *
 *  **والتفضيلُ يبقى مشتعلاً في الثلاثة الأولى**: من أشعل الميزةَ لا يطفئها
 *  خروجُه — فإذا دخل بكلمته ثانيةً عاد الرمزُ إلى مكانه بلا أن يُشعلها من جديد.
 *  **وإطفاؤها هو وحدَه ما يطفئ التفضيل.** */
export async function forgetToken(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  try {
    await SecureStorage.removeItem(SECURE_KEY);
  } catch {
    // المحوُ لا يُسقط شيئاً: غيابُ المفتاح هو المقصودُ منه أصلاً
  }
}

export async function enableBiometric(refreshToken: string | null): Promise<void> {
  localStorage.setItem(PREF_KEY, "1");
  if (refreshToken) await rememberToken(refreshToken);
}

export async function disableBiometric(): Promise<void> {
  localStorage.removeItem(PREF_KEY);
  await forgetToken();
}

/** **يُطلب الإصبعُ عند الإشعال** — إثباتاً أن الجهازَ يفتح فعلاً.
 *
 * **ولمَ لا يُؤجَّل إلى أوّل استعمال**: من أشعلها بلا إصبعٍ يظنّها تعمل، ثمّ
 * يكتشف يومَ يحتاجها أنها لا تفتح — **ومفتاحٌ يُشعَل ولا يُقاس هو «حقلٌ يُعلن
 * ولا يقيس»**.
 */
export async function proveBiometry(reason: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    throw new Error("الدخول بالبصمة على الجهاز وحده");
  }
  await BiometricAuth.authenticate({
    reason,
    cancelTitle: "إلغاء",
    allowDeviceCredential: false,
  });
}

/** **الفتحُ**: تُطلب البصمة، فإن صدقت أُعيد رمزُ التجديد المخزَّن.
 *
 * **ويُرمى الخطأُ ولا يُبتلع**: «بصمةٌ خاطئة» و«لا رمزَ محفوظاً» حالان
 * مختلفتان — والشاشةُ تقول أيَّهما وقع.
 */
export async function unlockToken(reason: string): Promise<string> {
  if (!Capacitor.isNativePlatform()) {
    throw new Error("الدخول بالبصمة على الجهاز وحده");
  }
  // **الترتيب مقصود**: تُطلب البصمةُ **قبل** قراءة المخزن — فقراءةٌ تسبق
  // التصديق تجعل الرمزَ في الذاكرة ولو رُفض صاحبُ الإصبع
  await BiometricAuth.authenticate({
    reason,
    cancelTitle: "إلغاء",
    // **ولا بديلَ بقفل الجهاز** (قرارُ المالك: لا بابَ ثانياً): من لا بصمةَ
    // له يدخل بكلمة المرور — وهو البابُ الأول لا بابٌ أضعفُ منه
    allowDeviceCredential: false,
  });
  const token = await readToken();
  if (!token) throw new Error("لا رمزَ محفوظاً على هذا الجهاز");
  return token;
}
