/** **أيُّ أيقوناتٍ تُرسم في اللوحة** (SPEC §١٠٥/٣) — مفتاحُ `icons_v2` **للدولة المختارة في المبدّل**: فيرى المالكُ الجديدةَ حين
 *  يُشعلها لسوقٍ ويختاره، ويعود إلى القديمة بإطفائها. */
import { useLayoutEffect } from "react";

import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { ICONS_V2_FLAG, setIconSetV2 } from "@/taxo2";

export function IconSetSwitch(): null {
  const { country } = useCountry();
  const on = useCountryConfig(country)?.features[ICONS_V2_FLAG] === true;
  useLayoutEffect(() => setIconSetV2(on), [on]);
  return null;
}
