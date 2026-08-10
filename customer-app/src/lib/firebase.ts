/** جسرُ Firebase: التحقق من الرقم على الجهاز، ورمزُ الجهاز للإشعارات.
 *
 * **الاستيراد كسولٌ عمداً** (`await import`): حزمة Firebase ثقيلة، ومعظم
 * المستخدمين لا يمرون بشاشة تسجيلٍ إلا مرة، وقد لا يكون عقدُ Firebase مفعّلاً
 * أصلاً — فلا تُحمَّل إلا حين تُستعمل فعلاً.
 *
 * **والإعداد يأتي من `GET /config` لا من ملف في الواجهة** (SPEC القسم 14):
 * قيمُه عامّةٌ بطبيعتها لكنها قيمُ مشروعٍ بعينه، فمصدرها عقدُ المزود مشفَّراً
 * في القاعدة. بغير عقدٍ مفعّل ترجع هذه الدوال `null` ولا تنفجر: غيابُ العقد
 * هو الوضع الافتراضي الذي يصفه القسم 15/أ لا عطل.
 *
 * وما تنتجه هذه الوحدة للخلفية شيءٌ واحد: **رمز هوية** يثبت ملكية الرقم. ولا
 * يدخل به أحدٌ النظام — الجلسات تصدرها الخلفية وحدها (SPEC القسم 2).
 */

import type { FirebaseApp } from "firebase/app";
import type { ConfirmationResult } from "firebase/auth";

export interface FirebaseWebConfig {
  apiKey: string;
  authDomain?: string;
  projectId: string;
  appId: string;
  messagingSenderId?: string;
}

let cached: { key: string; app: FirebaseApp } | null = null;

/** يبني (أو يعيد) نسخة التطبيق لهذا الإعداد. */
async function firebaseApp(config: FirebaseWebConfig): Promise<FirebaseApp> {
  const key = `${config.projectId}:${config.appId}`;
  if (cached?.key === key) return cached.app;

  const { initializeApp, getApps, getApp } = await import("firebase/app");
  const app = getApps().length ? getApp() : initializeApp({ ...config });
  cached = { key, app };
  return app;
}

// ------------------------------------------------- التحقق من الرقم

export interface PhoneChallenge {
  /** يكمل التحقق ويعيد **رمز الهوية** الذي ترسله الواجهة للخلفية. */
  confirm(code: string): Promise<string>;
}

/** يبدأ تدفّق Firebase: reCAPTCHA غير مرئي ثم رسالةٌ من Firebase نفسه.
 *
 * `containerId` عنصرٌ فارغ في الصفحة يعلّق عليه reCAPTCHA نفسه — الحزمة
 * تتطلبه ولو كان غير مرئي.
 */
export async function startPhoneVerification(
  config: FirebaseWebConfig,
  phoneE164: string,
  containerId: string,
): Promise<PhoneChallenge> {
  const app = await firebaseApp(config);
  const { getAuth, RecaptchaVerifier, signInWithPhoneNumber } = await import(
    "firebase/auth"
  );

  const auth = getAuth(app);
  auth.languageCode = "ar";

  const verifier = new RecaptchaVerifier(auth, containerId, { size: "invisible" });
  let result: ConfirmationResult;
  try {
    result = await signInWithPhoneNumber(auth, phoneE164, verifier);
  } catch (error) {
    verifier.clear();
    throw error;
  }

  return {
    async confirm(code: string) {
      const credential = await result.confirm(code);
      // رمز الهوية هو كل ما تريده الخلفية؛ ولا نُبقي جلسة Firebase مفتوحة
      // بعده — إثباتُ ملكية رقمٍ لا جلسةُ عمل (SPEC القسم 2)
      const token = await credential.user.getIdToken();
      await auth.signOut().catch(() => undefined);
      return token;
    },
  };
}

// ------------------------------------------------------- رمز الجهاز

/** يطلب إذن الإشعارات ويعيد رمز الجهاز — أو `null` إن رُفض أو لم يُهيَّأ.
 *
 * `null` ليست خطأً: مستخدمٌ رفض الإذن يستعمل التطبيق كاملاً وتصله الأحداث على
 * المقبس ما دام مفتوحاً (SPEC القسم 15/أ: «قبلها — WebSocket أثناء فتح
 * التطبيق يكفي»).
 */
export async function requestPushToken(
  config: FirebaseWebConfig,
  vapidKey: string,
): Promise<string | null> {
  if (!("Notification" in window) || !("serviceWorker" in navigator)) return null;
  if (!vapidKey) return null;

  const permission =
    Notification.permission === "default"
      ? await Notification.requestPermission()
      : Notification.permission;
  if (permission !== "granted") return null;

  const app = await firebaseApp(config);
  const { getMessaging, getToken, isSupported } = await import("firebase/messaging");
  if (!(await isSupported())) return null;

  // عاملُ الخدمة الخاص بالرسائل: هو ما يعرض الإشعار والتطبيقُ مغلق
  const registration = await navigator.serviceWorker.register(
    `/firebase-messaging-sw.js?config=${encodeURIComponent(JSON.stringify(config))}`,
    { scope: "/firebase-cloud-messaging-push-scope" },
  );

  return await getToken(getMessaging(app), {
    vapidKey,
    serviceWorkerRegistration: registration,
  }).catch(() => null);
}

/** ما يصل والتطبيق مفتوح — لا يعرضه المتصفح، فنعرضه نحن داخل الشاشة. */
export async function onForegroundMessage(
  config: FirebaseWebConfig,
  handler: (payload: { title?: string; body?: string; data?: Record<string, string> }) => void,
): Promise<() => void> {
  const app = await firebaseApp(config);
  const { getMessaging, onMessage, isSupported } = await import("firebase/messaging");
  if (!(await isSupported())) return () => undefined;

  return onMessage(getMessaging(app), (payload) => {
    handler({
      title: payload.notification?.title,
      body: payload.notification?.body,
      data: payload.data as Record<string, string> | undefined,
    });
  });
}
