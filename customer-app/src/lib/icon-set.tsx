/** **أيُّ أيقوناتٍ تُرسم** (SPEC §١٠٥/٣) — مفتاحُ `icons_v2` لدولة الحساب؛ وقبل الدخول لا دولةَ فالقديمةُ كما هي. */
import { useLayoutEffect } from "react";

import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";
import { ICONS_V2_FLAG, setIconSetV2 } from "@/taxo2";

export function IconSetSwitch(): null {
  const { user } = useSession();
  const on = useFeature(user?.country_code, ICONS_V2_FLAG);
  useLayoutEffect(() => setIconSetV2(on), [on]);
  return null;
}
