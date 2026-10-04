/** **منطقُ ورقة التتبّع في بيتٍ واحد** — الإلغاءُ بأسبابه، وإرسالُ التفاصيل، ورسمةُ المركبة.
 *
 * يقرؤه وجهان: **القائمُ** (`TrackingSheet`) و**TAXO 2.0** «R07–R09» (`screens/t2/TrackingSheetT2`) — **فلا يفترقان في
 * إلغاءٍ ولا في سببٍ ولا في رسم**. والنصُّ منقولٌ من `TrackingSheet` **حرفاً بتعليقاته**، والعرضُ القائمُ لم يتغيّر فيه سطر.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { cancelRide } from "@/api/endpoints";
import type { Ride } from "@/api/types";

export const CANCELLABLE = new Set(["requested", "searching", "accepted", "arrived"]);

export interface CancelReason {
  label: string;
  /** `undefined` = نصٌّ حر بلا أثرٍ على الرسوم؛ والمصنَّف يغيّر السلوك. */
  code?: "gender_mismatch";
}

/** أسبابُ الإلغاء كما في التصميم — والنصُّ الحرّ يصل الإدارة كما كُتب. */
export const CANCEL_REASONS: CancelReason[] = [
  { label: "الكبتن تأخر" },
  { label: "غيّرت رأيي" },
  { label: "الكبتن ليس أنثى — عدم تطابق", code: "gender_mismatch" },
  { label: "عنوان الالتقاء خطأ" },
];

/** «أرسل تفاصيل رحلتك» (SPEC القسم 11.4) — نصٌّ يُرسل عبر ورقة مشاركة النظام.
 *
 * **وسُمّي بغير «مشاركة الرحلة» بعد 12-ي**: صارت المشاركةُ اسماً لشيءٍ آخر —
 * راكبٌ ثانٍ في السيارة — وشارةُ «رحلة مشتركة» تقف الآن على الورقة نفسِها فوق
 * هذا الزرِّ بالضبط. فكلمتان متجاورتان تعنيان أمرين مختلفين تجعلان من يضغط
 * يظنّ أنه يضيف راكباً أو يظنّ أن رحلتَه صارت مشتركةً بضغطة. والتسميةُ الجديدة
 * تقول ما يفعله الزرُّ فعلاً: يُرسل التفاصيل لمن ينتظره.
 *
 * **لا رابطَ تتبعٍ عام**: ذاك يحتاج رمزاً على `rides` يفتح الرحلة لمن لا
 * حساب له، وهو جدولٌ وعقدُ صلاحياتٍ لم يصفهما SPEC — وكل مسارٍ يلمس رحلةً
 * يتحقق من ملكيتها (القسم 14). فالمشاركة تحمل ما يطمئن المنتظِر فعلاً: اسم
 * الكبتن ولوحته والوجهة على الخريطة.
 */
export async function shareRide(ride: Ride) {
  const destination = `https://maps.google.com/?q=${ride.dropoff.lat},${ride.dropoff.lng}`;
  const vehicle = ride.driver?.vehicle;
  const lines = [
    "أنا الآن في رحلة TAXO.",
    ride.driver ? `الكبتن: ${ride.driver.name}` : null,
    vehicle ? `المركبة: ${vehicle.make} ${vehicle.model} — لوحة ${vehicle.plate_number}` : null,
    `الوجهة: ${ride.dropoff_address ?? destination}`,
  ].filter(Boolean);

  const text = lines.join("\n");
  if (navigator.share) {
    await navigator.share({ title: "رحلتي على TAXO", text, url: destination }).catch(
      () => undefined,
    );
    return true;
  }
  await navigator.clipboard?.writeText(`${text}\n${destination}`).catch(() => undefined);
  return false;
}

export function useTrackingSheet({
  ride,
  onChanged,
}: {
  ride: Ride;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareHintClosed, setShareHintClosed] = useState(false);
  const [reason, setReason] = useState<CancelReason | null>(null);
  /** حالُ رسمة المركبة — **والسطرُ لا يُرسم حتى تصل**: صندوقُ صورةٍ مكسورةٍ
   *  بجانب اسم الكبتن يُقرأ عطباً في التطبيق، وسطرٌ يختفي كأن لا مركبةَ له
   *  هو **نفسُ ما تراه بطاقةُ من لا مركبةَ له** — فلا فرقَ يُرى. */
  const [skinArt, setSkinArt] = useState<"loading" | "ready" | "broken">("loading");

  const searching = ride.status === "requested" || ride.status === "searching";
  // «رحلةٌ نسائية» = ما طُلب فيها جنسٌ بعينه — وصفٌ للطلب لا لصاحبته
  const gendered = ride.gender_preference !== "any";
  const afterAccept = ride.status === "accepted" || ride.status === "arrived";

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await cancelRide(ride.id, reason?.label, reason?.code);
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إلغاء الرحلة");
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return {
    busy,
    error,
    confirming,
    setConfirming,
    copied,
    setCopied,
    shareHintClosed,
    setShareHintClosed,
    reason,
    setReason,
    skinArt,
    setSkinArt,
    searching,
    gendered,
    afterAccept,
    cancel,
  };
}
