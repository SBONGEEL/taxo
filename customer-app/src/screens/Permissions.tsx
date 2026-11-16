/** **«الأذونات» في تطبيق الراكب** (SPEC §١٠٣ المرحلة A/28، أمرُ المالك ٢٠٢٦-١١-١٦) — صفٌّ لكلِّ إذنٍ يستعمله التطبيق بحاله الحيّ وسببه
 * وزرٍّ لصفحة النظام الدقيقة. **وأختُ شاشة الكبتن** (`driver-app/src/screens/Permissions.tsx`) بالمنطق نفسِه من `lib/permissions-center`.
 *
 * **الحالُ تُقرأ في كلِّ فتحةٍ وعند كلِّ عودة** — المستخدمُ يغيّر الإذنَ من إعدادات الهاتف ولا يمرّ بنا. **ولا مانعَ هنا**: الراكبُ يطلب
 * رحلتَه بلا أيٍّ منها (يختار الانطلاقَ بالدبوس)، فالصفوفُ «مستحسن» لا «مطلوب». وخلف `permissions_center`، **وفي غلافٍ يحمل الملحق**.
 * **والشرحُ قبل الحسّاس** (الخطوة c): الميكروفونُ ومِلءُ الشاشة يُشرحان في الصفّ نفسِه قبل الزرّ — لا طلبَ نظامٍ بلا جملةٍ تسبقه.
 */
import { useCallback, useEffect, useState } from "react";

import { useGoBack } from "@/lib/back";
import {
  PERMISSION_META,
  askPermission,
  centerAvailable,
  ordered,
  readPermissions,
  type OpenedAt,
  type PermissionKey,
  type PermissionRow,
} from "@/lib/permissions-center";
import { Icon } from "@/taxo2";
import { SubHeadT2 } from "@/screens/t2/KitT2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css"; import { tr } from "@/lib/i18n";

/** **أيقوناتُ ما يعلنه بيانُ الراكب وحدَه** — وما سواه (الفقاعةُ والبطاريةُ والتشغيلُ التلقائيّ) لا صفَّ له هنا، فلا تُحمَّل أيقونتُه في المقتطَع */
const ROW_ICON: Partial<Record<PermissionKey, string>> = {
  location: "location_on",
  location_background: "my_location",
  notifications: "notifications",
  full_screen: "open_in_full",
  microphone: "mic",
};

export function PermissionsScreen() {
  const goBack = useGoBack("/account");
  const [rows, setRows] = useState<PermissionRow[] | null>(null);
  const [openedAt, setOpenedAt] = useState<Partial<Record<PermissionKey, OpenedAt | null>>>({});

  const read = useCallback(async () => {
    setRows(ordered(await readPermissions(), "rider"));
  }, []);

  useEffect(() => {
    void read();
    const onShow = () => {
      if (!document.hidden) void read();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [read]);

  async function grant(key: PermissionKey) {
    const where = await askPermission(key);
    setOpenedAt((current) => ({ ...current, [key]: where }));
    void read();
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title={tr("الأذونات")} onBack={goBack} />

      {!centerAvailable() ? (
        <p className="t2-srow-hint" role="status">
          {tr("هذه الصفحة تقرأ أذونات الهاتف من التطبيق المثبَّت بإصداره الأحدث — حدّث التطبيق من المتجر ثم افتحها.")}
        </p>
      ) : null}

      <div className="t2-list t2-sgroup">
        {(rows ?? []).map((row) => {
          const meta = PERMISSION_META[row.key];
          const on = row.state === "on";
          const where = openedAt[row.key];
          return (
            <div key={row.key} className="t2-srow">
              <Icon name={ROW_ICON[row.key] ?? "verified_user"} className="t2-srow-icon" />
              <span className="t2-srow-main">
                <span className="t2-srow-title">{tr(meta.label)}</span>
                <span className="t2-srow-hint">{tr(meta.why.rider)}</span>
                {!on && (where === "details" || where === "none") ? (
                  <ol className="t2-srow-hint">
                    {meta.steps.map((step) => (
                      <li key={step}>{tr(step)}</li>
                    ))}
                  </ol>
                ) : null}
              </span>
              {on ? (
                <span className="t2-chip ok">{tr("مفعّل")}</span>
              ) : (
                <button type="button" className="t2-chip warn" onClick={() => void grant(row.key)}>
                  {row.state === "unknown" ? tr("تحقّق") : tr("فعّل")}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
