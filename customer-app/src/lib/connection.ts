/** **حالُ الاتصال كما يعيشها المستخدم** — ثلاثُ حالاتٍ لا «خطأ شبكة» (أمرُ المالك ٢٠٢٦-١١-٠٦، البند ٥).
 *
 * - **`offline`**: الجهازُ بلا شبكةٍ أصلاً (`navigator.onLine === false`) — «لا يوجد اتصال بالإنترنت».
 * - **`weak`**: الشبكةُ موجودةٌ والطلبُ لم يكتمل (انتهت المهلة أو سقط في الطريق) — ضعيفٌ أو غيرُ مستقرّ، **ونعيد المحاولة وحدَنا**.
 * - **`down`**: وصلنا إلى الحافّة وردّت أن الخادمَ خلفها لا يجيب (`502/503/504/52x` بلا جسمِ عقدِنا) — «الخدمة متوقفة مؤقتاً».
 *
 * **والفرقُ فرقٌ في ما يفعله القارئ**: الأولى يفحص شبكتَه، والثانية يبدّل بين Wi-Fi والبيانات، والثالثة ينتظر — **ورسالةٌ واحدةٌ
 * للثلاث ترسل نصفَ الناس يفحصون ما ليس معطوباً**. وأيُّ ردٍّ من الخادم يعيد الحالَ `ok`: الجوابُ نفسُه هو الدليل.
 */

import { useSyncExternalStore } from "react";

export type ConnectionState = "ok" | "offline" | "weak" | "down";

let state: ConnectionState = typeof navigator !== "undefined" && navigator.onLine === false ? "offline" : "ok";
const listeners = new Set<() => void>();

export function setConnection(next: ConnectionState): void {
  if (next === state) return;
  state = next;
  listeners.forEach((listener) => listener());
}

export function connectionState(): ConnectionState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useConnection(): ConnectionState {
  return useSyncExternalStore(subscribe, () => state);
}

/** **حافّةٌ تقول إن الخادمَ خلفها لا يجيب** — لا خطأٌ من عقدنا: ردُّ الخادم نفسِه بـ503 (مفتاحٌ مطفأ مثلاً) يحمل JSON ويُعرض كما هو. */
export function isEdgeDown(response: Response): boolean {
  const edge = [502, 503, 504, 520, 521, 522, 523, 524, 530].includes(response.status);
  return edge && !(response.headers.get("content-type") ?? "").includes("application/json");
}

if (typeof window !== "undefined") {
  window.addEventListener("offline", () => setConnection("offline"));
  // عودةُ الشبكة لا تعني عودةَ الخادم — فتُقرأ «ضعيفاً» حتى يصل أوّلُ جواب
  window.addEventListener("online", () => setConnection(state === "offline" ? "weak" : state));
}
