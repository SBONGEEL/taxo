/** أين يذهب إشعارٌ حين يُنقر — **بيتٌ واحدٌ للنقرتين**.
 *
 * صفُّ صندوق الوارد وإشعارُ النظام **حدثٌ واحدٌ بوجهين**: `kind` هو
 * `data.type` نفسُه (SPEC القسم 10). فلو حسب كلٌّ وجهتَه لَفتحت النقرتان
 * شاشتين مختلفتين لنفس الخبر — **وهي قاعدةٌ كانت مكتوبةً في `CLAUDE.md` بلا
 * بيتٍ يطبّقها**، لأن مسارَ النظام لم يكن موجوداً أصلاً.
 */

/** **عرضُ الرحلة يفتح الرئيسيةَ ومعه معرِّفُه** — لا الرئيسيةَ وحدَها.
 *
 * البطاقةُ تُرسم في `Home` وحدَها، **والرحلةُ ليست له بعد** — فـ
 * `GET /rides/{id}` يردّ منعاً لا بطاقة.
 *
 * **وأولُ صياغةٍ فتحت الرئيسيةَ عاريةً، وكان ذلك نصفَ إصلاح** (تصحيحُ
 * المالك): الشاشةُ تفتح فارغةً ثم تنقضي المهلةُ فيُقرأ ذلك عطباً. **فالنقرةُ
 * تحمل المعرّف**، والشاشةُ **تنتظر أن تصير الرحلةُ له** — والعرضُ المعلَّق
 * يصل مع أول اتصالٍ بالمقبس (`dispatch.pending_offer_frame`)، فالانتظارُ
 * انتظارُ حدثٍ قادمٍ لا سؤالٌ مرةً ويأس.
 */
const HOME = "/";

export function destinationFor(
  kind: string | undefined,
  data: Record<string, string> | null | undefined,
): string | null {
  if (!kind) return null;
  if (kind === "ride_offer") {
    return data?.ride_id ? `${HOME}?offer=${data.ride_id}` : HOME;
  }
  const rideId = data?.ride_id;
  if (rideId) return `/rides/${rideId}`;
  if (kind.startsWith("subscription_")) return "/subscription";
  if (kind.startsWith("document_")) return "/account/vehicle";
  return null;
}
