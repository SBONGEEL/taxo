/** الجلسةُ على الجهاز والدخولُ بالبصمة — **بيتان آمنان لسرّين مختلفين** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §60-ج).
 *
 * ## الأوّل — رمزُ التجديد: **يعيش في المخزن الآمن دائماً على الجهاز**
 *
 * **كان يعيش هناك حين تُشعَل البصمةُ وحدَها**، ولا يُقرأ إلا بها — **فكلُّ إقلاعٍ باردٍ بعد نصف ساعة** (عمرُ رمز الوصول) كان
 * يجد الذاكرةَ فارغةً فيقف على شاشة الدخول (قِيس ٢٠٢٦-١١-٠٢). **وهو علّةُ «يخرجني التطبيق» عند من أشعلها بعينها.**
 *
 * فالآن **البيتُ واحدٌ ولا يتبع التفضيل**: على الجهاز `SecureStorage` (Keystore على أندرويد، Keychain على iOS) **يُقرأ عند
 * الإقلاع بلا بصمة** قبل أن يُحكم بخروج أحد، ولا نسخةَ في `localStorage`. وفي المتصفّح `localStorage` كما كان. **والرمزُ
 * يُدوَّر، فنسخةٌ ثانيةٌ تموت عند أوّل تجديد** — وهو الشكلُ الثامن الذي كان يمنعه هذا الملفُّ ويبقى يمنعه.
 *
 * ## الثاني — بيانُ الجهاز: **الدخولُ بالبصمة بعد «تسجيل الخروج»**
 *
 * الخروجُ **يُنهي الجلسةَ على الخادم** — فلا رمزَ تجديدٍ يبقى ليُفتح بالبصمة. **فالبصمةُ تفتح سرّاً آخرَ**: بيانُ جهازٍ يصدره
 * الخادمُ عند الإشعال (`POST /auth/device-login/enroll`)، **ويُقرأ من المخزن بعد أن تصدق البصمةُ لا قبلها**، ويُصرف بجلسةٍ جديدة
 * ويُدوَّر مع كلِّ دخول. **ويُبطله الخادمُ** باستعادة كلمة المرور وبإيقاف الحساب وبإنهاء كلِّ الجلسات، **ويُبطله صاحبُه**
 * بـ«الدخول بحساب آخر» أو بإطفاء الميزة.
 *
 * ## ولا كلمةَ مرورٍ هنا بحال
 *
 * **لا مشفَّرةً ولا مُرمَّزة** (قرارُ المالك). ما يُحفظ رمزٌ وسرٌّ **يُبطلهما الخادمُ متى شاء** — وكلمةُ المرور لا تُبطَل.
 *
 * ## وفي المتصفّح: لا بصمةَ إطلاقاً
 *
 * `Capacitor.isNativePlatform()` أولاً، **قبل أيِّ نداءِ ملحق**. ومن لا بصمةَ على جهازه **لا يرى الميزةَ**، ولا رقمَ سرّيَّ
 * بديلاً — **بابٌ ثانٍ يضعف الأول** (قرارُ المالك).
 */

import { BiometricAuth, BiometryType } from "@aparajita/capacitor-biometric-auth";
import { SecureStorage } from "@aparajita/capacitor-secure-storage";
import { Capacitor } from "@capacitor/core"; import { tr } from "@/lib/i18n";

/** **بيتُ رمز التجديد على الجهاز** — بلا بصمة، يُقرأ عند الإقلاع. */
const SESSION_KEY = "taxo.driver.session.refresh";
/** بيتُه القديم حين كان خلف البصمة — **يُنقل منه مرّةً** إلى `SESSION_KEY` ثمّ يُمحى. */
const LEGACY_KEY = "taxo.driver.biometric.refresh";
/** **بيانُ الجهاز** — لا يُقرأ للدخول إلا بعد البصمة. */
const DEVICE_KEY = "taxo.driver.device.secret";

/** **التفضيلُ ليس سرّاً** فيعيش حيث تعيش التفضيلات — والجوابُ لا يفتح شيئاً بلا السرِّ الذي في المخزن الآمن. */
const PREF_KEY = "taxo.driver.biometric.enabled";

export type BiometryKind = "fingerprint" | "face" | "generic";

export interface BiometryStatus {
  /** **أهو جهازٌ أصليّ؟** — يفصل «متصفّحٌ لا ميزةَ فيه أصلاً» عن «جهازٌ يملكها ولم تُسجَّل بعد». */
  native: boolean;
  /** **الجهازُ يملكها ومسجَّلةٌ فيه** — وإلا فلا زرَّ ولا مفتاحَ في الإعدادات. */
  available: boolean;
  kind: BiometryKind;
  /** أشعلها المستخدمُ من إعداداته. */
  enabled: boolean;
  /** **ثمّة بيانُ جهازٍ محفوظٌ فعلاً** — والزرُّ لا يُرسم بدونه ولو كان التفضيلُ مشتعلاً. */
  armed: boolean;
  /** **رمزُ المنصّة حين تكون غيرَ متاحة** — يُسجَّل للتشخيص **ولا يُعرض**. */
  code?: string;
}

export const UNAVAILABLE: BiometryStatus = {
  native: false,
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
  if (kind === "face") return tr("بصمة الوجه");
  if (kind === "fingerprint") return tr("بصمة الإصبع");
  return tr("قفل الجهاز");
}

function prefEnabled(): boolean {
  try {
    return localStorage.getItem(PREF_KEY) === "1";
  } catch {
    return false;
  }
}

async function read(key: string): Promise<string | null> {
  try {
    return await SecureStorage.getItem(key);
  } catch {
    return null;
  }
}

async function remove(key: string): Promise<void> {
  try {
    await SecureStorage.removeItem(key);
  } catch {
    // المحوُ لا يُسقط شيئاً: غيابُ المفتاح هو المقصودُ منه أصلاً
  }
}

/** **الحالُ تُقاس ولا تُفترض** — وفي المتصفّح تعود «غيرُ متاحة» بلا نداءِ ملحق. */
export async function biometryStatus(): Promise<BiometryStatus> {
  if (!Capacitor.isNativePlatform()) return UNAVAILABLE;
  try {
    const check = await BiometricAuth.checkBiometry();
    if (!check.isAvailable) {
      // **يُسجَّل السببُ ولا يُعرض**: القارئُ يحتاج ما يفعله، والمشخِّصُ يحتاج ما ردَّته المنصّة
      console.warn(
        tr("الدخول السريع غيرُ متاح — {0}: {1}", { 0: check.code ?? tr("بلا رمز"), 1: check.reason ?? "" }) +
          tr(" · قويّةٌ متاحة: {0}", { 0: String(check.strongBiometryIsAvailable) }) +
          tr(" · الجهازُ مؤمَّن: {0}", { 0: String(check.deviceIsSecure) }) +
          tr(" · الأنواع: {0}", { 0: JSON.stringify(check.biometryTypes) }),
      );
      return { ...UNAVAILABLE, native: true, code: check.code };
    }
    const enabled = prefEnabled();
    // **«أمشتعلٌ التفضيل؟» غيرُ «أثمّة بيان؟»** — والإبطالُ يمحو الثاني ويترك الأول، فمن رسم الزرَّ على التفضيل وحدَه رسم زرّاً
    // يفشل عند الضغط
    const armed = enabled ? (await read(DEVICE_KEY)) !== null : false;
    return { native: true, available: true, kind: kindOf(check.biometryType), enabled, armed };
  } catch (error) {
    // **ملحقٌ لا يجيب يُقرأ «غيرُ متاح» لا يُسقط الشاشة** — **و`native: true`**: جهازٌ سقط ملحقُه ليس متصفّحاً (صُحّح 2026-08-29)
    console.warn("تعذّر سؤالُ الملحق عن البصمة", error);
    return { ...UNAVAILABLE, native: true, code: "plugin_error" };
  }
}

// ------------------------------------------------------------ رمزُ التجديد

/** **بيتُ رمز التجديد** كما يحتاجه `api/client` — يُحقن هناك فيبقى العميلُ جاهلاً بالملحقات. */
export const nativeRefreshStore = {
  native: Capacitor.isNativePlatform(),
  /** **يُقرأ عند الإقلاع** — ومن البيت القديم (خلف البصمة) أو من `localStorage` (جهازٌ قبل هذا الإصدار) **يُنقل مرّةً**. */
  async load(fromLocalStorage: string | null): Promise<string | null> {
    const held = await read(SESSION_KEY);
    if (held) return held;
    const legacy = (await read(LEGACY_KEY)) ?? fromLocalStorage;
    if (legacy) {
      await this.save(legacy);
      await remove(LEGACY_KEY);
    }
    return legacy;
  },
  async save(token: string): Promise<void> {
    try {
      await SecureStorage.setItem(SESSION_KEY, token);
    } catch (error) {
      console.warn("تعذّر حفظ رمز التجديد في المخزن الآمن", error);
    }
  },
  async clear(): Promise<void> {
    await remove(SESSION_KEY);
    await remove(LEGACY_KEY);
  },
};

// ------------------------------------------------------------ بيانُ الجهاز

/** **قراءتُه للإبطال وحدَه** («الدخول بحساب آخر») — الإبطالُ لا يفتح شيئاً، فلا يحتاج بصمة. */
export async function deviceSecretForRevoke(): Promise<string | null> {
  if (!Capacitor.isNativePlatform()) return null;
  return read(DEVICE_KEY);
}

export async function storeDeviceSecret(secret: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  try {
    await SecureStorage.setItem(DEVICE_KEY, secret);
  } catch (error) {
    console.warn("تعذّر حفظ بيان الجهاز في المخزن الآمن", error);
  }
}

/** **المحوُ المحلّيّ** — استعادةُ كلمة المرور، وردُّ الخادم بأن البيانَ أُبطل، و«الدخول بحساب آخر»، وإطفاءُ الميزة. */
export async function forgetDeviceSecret(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await remove(DEVICE_KEY);
  // **وما بقي من البيت القديم يُمحى معه** — رمزُ جلسةٍ خلف البصمة من إصدارٍ سابق
  await remove(LEGACY_KEY);
}

export function isBiometricPreferred(): boolean {
  return prefEnabled();
}

export function setBiometricPreferred(on: boolean): void {
  if (on) localStorage.setItem(PREF_KEY, "1");
  else localStorage.removeItem(PREF_KEY);
}

/** **يُطلب الإصبعُ عند الإشعال** — إثباتاً أن الجهازَ يفتح فعلاً؛ ومفتاحٌ يُشعَل ولا يُقاس «حقلٌ يُعلن ولا يقيس». */
export async function proveBiometry(reason: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    throw new Error(tr("الدخول بالبصمة على الجهاز وحده"));
  }
  await BiometricAuth.authenticate({ reason, cancelTitle: tr("إلغاء"), allowDeviceCredential: false });
}

/** **الفتحُ**: تُطلب البصمة، فإن صدقت أُعيد بيانُ الجهاز.
 *
 * **والترتيبُ مقصود**: البصمةُ **قبل** قراءة المخزن — فقراءةٌ تسبق التصديق تجعل السرَّ في الذاكرة ولو رُفض صاحبُ الإصبع.
 * **ولا بديلَ بقفل الجهاز** (قرارُ المالك: لا بابَ ثانياً) — من لا بصمةَ له يدخل بكلمة المرور.
 */
export async function unlockDeviceSecret(reason: string): Promise<string> {
  if (!Capacitor.isNativePlatform()) {
    throw new Error(tr("الدخول بالبصمة على الجهاز وحده"));
  }
  await BiometricAuth.authenticate({ reason, cancelTitle: tr("إلغاء"), allowDeviceCredential: false });
  const secret = await read(DEVICE_KEY);
  if (!secret) throw new Error(tr("لا دخولَ بالبصمة محفوظاً على هذا الجهاز"));
  return secret;
}
