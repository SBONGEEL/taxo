import { useBrand } from "@/lib/brand";
import { cn } from "@/lib/utils";

/** اسم التطبيق كما يفرضه SPEC القسم 1: **TAXO** في كل الواجهات.
 *
 * والاسمُ نفسُه يتلوّن مع السِمة الوردية (المرحلة 10-ج). وهو **الموضع الوحيد
 * الذي يقرأ فيه مكوّنٌ حالةَ السِمة**: بقيةُ الواجهة مكتوبةٌ بـ`--brand` أصلاً
 * فتتحول بلا شرط، أمّا الاسم فلونُه `--tx` في الأصل — و`text-brand` بلا شرطٍ
 * كان سيصبغه بلون التطبيق الافتراضي، وذلك تغييرُ هويةٍ لم يطلبه أحد.
 */
export function Brand({
  subtitle,
  className,
}: {
  subtitle?: string;
  className?: string;
}) {
  const { pink } = useBrand();

  return (
    <div className={cn("space-y-8 text-center", className)}>
      <div className="mx-auto flex size-64 items-center justify-center rounded-16 bg-brand">
        <span className="text-24 font-bold tracking-tight text-brand-ink">T</span>
      </div>
      <h1
        className={cn(
          "text-30 font-bold tracking-tight",
          pink ? "text-brand" : "text-ink",
        )}
      >
        TAXO
      </h1>
      {subtitle ? <p className="text-14 text-muted">{subtitle}</p> : null}
    </div>
  );
}
