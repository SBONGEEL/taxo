/** المستنداتُ المطلوبةُ من الكبتن — **بيتٌ واحدٌ لا قائمتان**.
 *
 * كانت مكتوبةً بيدٍ في `Vehicle.tsx` وحدَها، فكانت شاشةُ «حسابي» تحكم على
 * اكتمال المستندات بلا أن تعرف ما المطلوب: تعدّ المرفوضَ والمعلَّق، **فإذا
 * لم يُرفع شيءٌ أصلاً كان العدّان صفرين** فتقول «كل المستندات مقبولة».
 * **وصفرٌ مقروءٌ عطبٌ لا سلامة** (عطبٌ مقيسٌ ٢٠٢٦-٠٩-٠٩).
 *
 * والترتيبُ ترتيبُ شاشة التسجيل: من رفع هناك يجده نفسَه هنا حين يستبدل.
 */
import type { DocumentType } from "@/api/types";

export const REQUIRED_DOCUMENTS: DocumentType[] = [
  "driving_license",
  "national_id",
  "vehicle_registration",
  "vehicle_front",
  "vehicle_back",
  "vehicle_plate",
  "vehicle_side_right",
  "vehicle_side_left",
  "vehicle_interior",
];
