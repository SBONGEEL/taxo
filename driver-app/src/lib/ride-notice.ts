import { tr } from "@/lib/i18n";

/**
 * **سطرُ الرحلة في إشعار «متّصل»** (SPEC §١٠٣ B/18) — جملةٌ بحال الرحلة لا بتفاصيلها:
 * **لا اسمَ راكبٍ ولا عنوانَ في شريط الحالة**، فالإشعارُ يُرى على شاشة القفل.
 */
export function rideNoticeLine(status: string | null): string | null {
  switch (status) {
    case "accepted":
      return tr("في الطريق إلى الراكب");
    case "arrived":
      return tr("بانتظار الراكب");
    case "in_progress":
      return tr("في الرحلة — إلى الوجهة");
    case "at_stop":
      return tr("في محطة توقّف");
    default:
      return null;
  }
}
