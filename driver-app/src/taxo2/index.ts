/** TAXO 2.0 — نظامُ التصميم (SPEC §61-ج). **استيرادُه يُحمِّل رموزَه وأصنافَه** قبل أيِّ صنفٍ في شاشة.
 *
 * والدليلُ في `README.md` بجانبه. **ونسخةٌ واحدةٌ في كلِّ تطبيق، متطابقةٌ بايتاً** (`check:taxo2`) — من عدّل ملفّاً هنا
 * نسخه إلى التطبيق الآخر في الإيداع نفسِه.
 */
import "./tokens.css";
import "./primitives.css";

export {
  AuthBlock,
  AuthChoice,
  AuthCode,
  AuthConditions,
  AuthConsent,
  AuthCountrySheet,
  AuthError,
  AuthInput,
  AuthOr,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  AuthWomenNote,
} from "./Auth";
export type { AuthCountryOption } from "./Auth";
export { Flag } from "./Flag";
export { DateField } from "./DateField";
export { Icon } from "./Icon";
export { Celebrate } from "./Celebrate";
export { CAR_ART, GLYPHS, IDLE_GLYPH } from "./glyphs";
export { GLYPHS_C, MARKER_C, VEHICLES_C, smoothBearing } from "./glyphsC";
export { ICONS_V2_FLAG, motionAllowed, setIconSetV2, useIconSetV2 } from "./iconSet";
export { SERVICE_ICON, serviceIcon } from "./serviceIcon";
export { Switch } from "./Switch";
export { Wordmark } from "./Wordmark";
