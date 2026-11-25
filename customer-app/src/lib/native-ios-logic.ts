/** **منطقُ جسر iOS الخالص** (`lib/native-ios.ts`) — بلا استيرادٍ واحد، فيُختبر بـ`node --test` بلا هاتفٍ ولا محرّك
 * (`customer-app/tests/native-ios.test.ts`). **ونسخةٌ واحدةٌ في التطبيقين بايتاً** (`check:ios`).
 */

// ── المكالمة ────────────────────────────────────────────────────────────

/** ما يحتاجه الجسرُ من حال المكالمة — جزءٌ من `CallView` لا نسخةٌ منه */
export interface CallLike {
  stage: string;
  callId: string | null;
  outgoing: boolean;
  muted: boolean;
}

export type NativeCallStep = "start" | "incoming" | "connected" | "end" | null;

const OVER = new Set(["broken", "unanswered", "tripover", "hungup"]);

/** **ما يُقال للنظام حين تتغيّر الحال** — والواردةُ والتطبيقُ ظاهرٌ لا تُعلن: شاشةُ المكالمة في التطبيق ترنّ بنفسها. */
export function nativeCallStep(before: CallLike | null, after: CallLike | null): NativeCallStep {
  const wasLive = !!before?.callId && !OVER.has(before.stage);
  if (!after || !after.callId || OVER.has(after.stage)) return wasLive ? "end" : null;
  if (before?.callId !== after.callId) return after.outgoing ? "start" : null;
  if (after.stage === "talking" && before?.stage !== "talking") return "connected";
  return null;
}

// ── النشاطُ الحيُّ للرحلة ───────────────────────────────────────────────

/** ما يحتاجه النشاطُ من الرحلة — جزءٌ من `Ride` في التطبيقين (الكبتنُ لا يحمل `driver`، والراكبُ يحمله) */
export interface RideLike {
  id: string;
  status: string;
  pickup_address?: string | null;
  dropoff_address?: string | null;
  driver?: { name: string; vehicle?: { make?: string | null; model?: string | null; color?: string | null; plate_number?: string | null } | null } | null;
}

export interface ActivityState {
  title: string;
  detail: string;
  plate: string;
  step: number;
}

/** **حالُ الرحلة نصّاً** — `null` لما لا يُرسم (البحث، والانتهاء): النشاطُ لرحلةٍ قُبلت ولم تنتهِ. */
export function rideActivity(
  ride: RideLike | null,
  side: "rider" | "driver",
  // **`tr` مُمرَّرةً لا مستوردة**: `lib/i18n` يستورد ملفَّ الترجمة بمسارٍ مستعار لا يقرؤه `node --test` — والاسمُ `tr` بعينه
  // ليجدها جردُ العربيّة (`check:arabic`) كما يجد كلَّ نصّ.
  tr: (text: string) => string,
): ActivityState | null {
  if (!ride) return null;
  if (side === "rider") {
    if (!ride.driver) return null;
    const vehicle = ride.driver.vehicle;
    const car = [vehicle?.make, vehicle?.model, vehicle?.color].filter(Boolean).join(" · ");
    const plate = vehicle?.plate_number ?? "";
    const who = [ride.driver.name, car].filter(Boolean).join(" · ");
    switch (ride.status) {
      case "accepted":
        return { title: tr("الكابتن في الطريق إليك"), detail: who, plate, step: 1 };
      case "arrived":
        return { title: tr("وصل الكابتن"), detail: who, plate, step: 2 };
      case "in_progress":
      case "at_stop":
        return { title: tr("في الرحلة"), detail: ride.dropoff_address ?? who, plate, step: 3 };
      default:
        return null;
    }
  }
  switch (ride.status) {
    case "accepted":
      return { title: tr("في الطريق إلى الراكب"), detail: ride.pickup_address ?? "", plate: "", step: 1 };
    case "arrived":
      return { title: tr("وصلتَ إلى الراكب"), detail: ride.pickup_address ?? "", plate: "", step: 2 };
    case "in_progress":
    case "at_stop":
      return { title: tr("في الرحلة"), detail: ride.dropoff_address ?? "", plate: "", step: 3 };
    default:
      return null;
  }
}
