/** **خدماتُ الكبتن في الرئيسيّة** (أمرُ المالك ٢٠٢٦-١١-٢٠ البند ٤، SPEC §١٠٩-د) — **من قائمة «حسابي» الحقيقيّة** لا من بلاطات اللوحة.
 *
 *  **علّةُ هذا الملفّ مقيسةٌ على الإنتاج** (٢٠٢٦-١١-٢٠): الرئيسيّةُ كانت ترسم «خدماتك» من بلاطات اللوحة (`GET /storefront`) وحدَها —
 *  وليبيا والجزائر **بلا بلاطةٍ واحدة**، وبلاطاتُ الأردن خدماتُ ركّاب (مطارات، أغراضي، طرود) — فلم يرَ كبتنُ ليبيا شيئاً، ولم يرَ
 *  أحدٌ اشتراكَه ولا محفظتَه ولا مهامَّه في الرئيسيّة. **فالخدماتُ هنا هي صفوفُ «حسابي» نفسُها بمقاصدها**، وما أُطفئ لدولته
 *  (السلفة · المستويات · الكراج) لا يُعدّ أصلاً. **وتبقى في «حسابي» كما هي.** وبلاطاتُ اللوحة المشتعلةُ تُلحق بعدها.
 *
 *  **و«منطقة العمل» ليست هنا**: لا شاشةَ لها في التطبيق — والأمرُ قال «من قائمة التطبيق الحقيقيّة»، فلا تُخترع بلاطةٌ لبابٍ غير موجود.
 *
 *  خالصٌ بلا React — يُختبر في `tests/service-usage.test.ts`.
 */
import type { ServiceTile } from "../api/types";

/** بلاطةٌ ومعها **رسمُها الجاهز** (نمطُ C) — بلاطاتُ اللوحة تُترجم أسماءَ lucide بـ`serviceIcon`، وهذه تسمّي رسمَها مباشرة. */
export type HomeTile = ServiceTile & { glyph?: string };

/** ما يُطفأ لدولة الكبتن بمفتاح اللوحة — **من بيوتها نفسِها** التي يسألها «حسابي» (`useFeature` و`useGarage`). */
export interface CaptainServiceSwitches {
  levels: boolean;
  advances: boolean;
  garage: boolean;
}

interface Row {
  key: string;
  title: string;
  glyph: string;
  destination: string;
  /** مفتاحُه إن كان خلف مفتاح — وبلا مفتاحٍ يظهر دائماً كصفِّه في «حسابي» */
  needs?: keyof CaptainServiceSwitches;
}

/** **الترتيبُ الأوّل** (قبل أن يُعدّ شيء): ما يفتحه الكبتنُ كلَّ يوم أوّلاً — ثمّ يرتّبها الاستعمالُ في هذا الهاتف. */
const ROWS: readonly Row[] = [
  { key: "subscription", title: "الاشتراك", glyph: "receipt_long", destination: "/subscription" },
  { key: "wallet", title: "المحفظة", glyph: "account_balance_wallet", destination: "/wallet" },
  { key: "earnings", title: "الأرباح", glyph: "payments", destination: "/wallet/earnings" },
  { key: "vehicle", title: "المركبة والوثائق", glyph: "directions_car", destination: "/account/vehicle" },
  { key: "missions", title: "مهامّي", glyph: "flag", destination: "/account/missions", needs: "levels" },
  { key: "support", title: "الدعم", glyph: "support_agent", destination: "/support" },
  { key: "advance", title: "السلفة", glyph: "request_quote", destination: "/account/advances", needs: "advances" },
  { key: "garage", title: "المتجر والكراج", glyph: "local_taxi", destination: "/account/garage", needs: "garage" },
  { key: "referral", title: "أحِل صديقك", glyph: "redeem", destination: "/account/referrals" },
  { key: "debt", title: "المستحقّات", glyph: "toll", destination: "/account/debt" },
];

/** **أهو مشتعلٌ لدولته؟** — كلُّ مفتاحٍ بقراءةٍ صريحة (لا فهرسةٌ بمتغيّر) فيراه `check:readers`. */
function switchedOn(row: Row, on: CaptainServiceSwitches): boolean {
  if (row.needs === "levels") return on.levels;
  if (row.needs === "advances") return on.advances;
  if (row.needs === "garage") return on.garage;
  return true;
}

/** **خدماتُ الكبتن** بشكل البلاطة — والمعرِّفُ `captain:<key>` فلا يصطدم بمعرِّفات اللوحة في عدّاد الاستعمال. */
export function captainServices(on: CaptainServiceSwitches, translate: (text: string) => string = (t) => t): HomeTile[] {
  return ROWS.filter((row) => switchedOn(row, on)).map((row) => ({
    id: `captain:${row.key}`,
    key: row.key,
    title: translate(row.title),
    subtitle: null,
    icon: "layout-grid",
    glyph: row.glyph,
    status: "active",
    destination: row.destination,
    is_new: false,
  }));
}

/** **الكلُّ في قائمةٍ واحدة**: خدماتُ الكبتن أوّلاً، ثمّ بلاطاتُ اللوحة — **وما يكرّر مقصداً قائماً يُسقط** (بلاطةٌ لوحيّةٌ إلى `/wallet`
 *  مثلاً) فلا تظهر خدمةٌ مرّتين. */
export function allServices(captain: readonly HomeTile[], panel: readonly ServiceTile[]): HomeTile[] {
  const taken = new Set(captain.map((tile) => tile.destination));
  return [...captain, ...panel.filter((tile) => tile.destination === null || !taken.has(tile.destination))];
}
