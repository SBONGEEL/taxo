/** **الطرد** (§٦٣-ج/٤) — مفتاحُه في تطبيق الراكب.
 *
 * **مطفأً لا يظهر شيءٌ جديد** (قاعدةُ `lib/sharing.ts` و`lib/for-other.ts`): بلاطةُ «طرد» تبقى «قريباً» كما كانت. **والرحلةُ
 * القائمةُ تُقرأ من صفّها لا من المفتاح** — `ride.ride_type` و`ride.payer` يصلان دائماً، فطردٌ طُلب يبقى طرداً ولو أُطفئ المفتاحُ
 * بعده («الإطفاءُ يمنع الجديد ولا يفكّ القائم»).
 *
 * **ولا رسمَ ولا شرطَ يُكتب هنا**: الرسمُ والشروطُ من تقدير الخلفية (`parcel_fee` · `parcel_terms`)، **ورسمٌ صفرٌ يُخفي الخدمةَ
 * ولو اشتعل المفتاح** — فيصل التقديرُ بلا رسمٍ، وتقول الورقةُ ذلك بدل طلبٍ يرتدّ.
 */

import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export function useParcel(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "parcel_enabled");
}
