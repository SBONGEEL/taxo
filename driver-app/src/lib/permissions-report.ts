/** **بلاغُ الأذونات إلى اللوحة** (SPEC §١٠٣ المرحلة A/28) — ما أُطفئ الآن على هاتف الكبتن، ليراه المشرفُ في درجه.
 *
 * **يُبلَّغ حين تتغيّر البصمةُ وحدَها** (`reportKey`)، فالكتابةُ نادرة؛ والبصمةُ الأخيرةُ في `localStorage` وإن ضاعت أُعيد البلاغُ
 * مرّةً لا أكثر. **وخلف `permissions_center` لدولته**: مطفأً لا نداءَ أصلاً. **ولا يحجب ولا يُطفئ استقبالاً** — قراءةٌ لا قرار.
 */
import { useEffect } from "react";

import type { CountryCode } from "@/api/types";

import { reportPermissions } from "@/api/endpoints";
import { useFeature } from "@/lib/config";
import type { PermissionStatus } from "@/lib/offer-alert";
import { REPORT_KEY, ROWS } from "@/lib/permission-rows";
import { reportKey, type PermissionKey } from "@/lib/permissions-center";

const STORE = "taxo.permissions.reported";

/** المطفأُ بمفاتيح البلاغ — بلا تكرار (القناةُ والإشعاراتُ مفتاحٌ واحد) */
export function offKeys(state: PermissionStatus): PermissionKey[] {
  const off = new Set<PermissionKey>();
  for (const row of ROWS) {
    const key = REPORT_KEY[row.key];
    if (key && !row.read(state)) off.add(key);
  }
  return [...off].sort();
}

export function usePermissionsReport(country: CountryCode | undefined, state: PermissionStatus | null): void {
  const on = useFeature(country, "permissions_center");
  useEffect(() => {
    if (!on || !state) return;
    const off = offKeys(state);
    const key = reportKey(off);
    let last: string | null = null;
    try {
      last = localStorage.getItem(STORE);
    } catch {
      last = null;
    }
    if (last === key) return;
    reportPermissions({ off })
      .then(() => {
        try {
          localStorage.setItem(STORE, key);
        } catch {
          // لا مخزن — يُعاد البلاغُ في الفتحة القادمة، ولا ضرر
        }
      })
      .catch(() => undefined);
  }, [on, state]);
}
