/** **«لم نتمكن من تحديد موقعك»** للكبتن (SPEC §١٠٩-ج) — فوق زرِّ الاستقبال لا عليه: نصُّ المالك حرفاً، **وسطرٌ يقول لماذا لا
 *  يتّصل**، و«تحديث الموقع الحالي» بحالة تحميل، والزرُّ الثاني بحسب السبب (في الغلاف وحدَه — المتصفّحُ لا يفتح إعداداتِ الهاتف). */
import type { LocationCause } from "@/lib/location-help";
import { actionFor, messageFor, REFRESH_LABEL } from "@/lib/location-help";
import { centerAvailable, openLocationServices, openPermission } from "@/lib/permissions-center";
import { Icon } from "@/taxo2";
import { tr } from "@/lib/i18n";

export function LocationHelpNotice({
  cause,
  locating,
  onRefresh,
}: {
  cause: LocationCause;
  locating: boolean;
  onRefresh: () => void;
}) {
  const action = centerAvailable() ? actionFor(cause) : null;
  return (
    <div className="t2-location-off" role="status">
      <span className="t2-location-off-text">{tr(messageFor(cause))}</span>
      <span className="t2-location-off-why">{tr("لا يمكنك استقبال الطلبات قبل تحديد موقعك — فالطلباتُ تصلك بحسب مكانك.")}</span>
      <button
        type="button"
        className="t2-chip t2-location-refresh"
        onClick={onRefresh}
        disabled={locating}
        aria-busy={locating}
      >
        <Icon name="my_location" />
        {locating ? tr("جارٍ تحديد موقعك…") : tr(REFRESH_LABEL)}
      </button>
      {action ? (
        <button
          type="button"
          className="t2-chip"
          onClick={() => void (action.key === "location_services" ? openLocationServices() : openPermission("location"))}
        >
          {tr(action.label)}
        </button>
      ) : null}
    </div>
  );
}
