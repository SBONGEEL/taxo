/** المستخدمون والصلاحيات — SPEC القسم 13/8.
 *
 * **دوران لا أربعة، ومصفوفتُهما ثابتةٌ في الكود لا في جدول.** القسم 13/8 يعرّف
 * `admin` كاملَ الصلاحية و`support` قراءةً ومعالجةَ نزاعات، ويفرضهما
 * `core/deps.py` على كل مسار. فما تعرضه هذه الشاشة **قراءةٌ لما تفرضه الخلفية
 * فعلاً**، لا مفاتيحُ تُقلَّب.
 *
 * والتصميم يرسم مصفوفةً «انقر لتفعيل أو تعطيل» بأربعة أدوار — ولم تُبنَ كذلك
 * عمداً، لسببين:
 *
 * 1. **دورٌ ثالث لا يوجد في `UserRole`**، وإضافةُ «عمليات» و«مالية» إلى اللوحة
 *    وحدها تعني اسماً في شاشةٍ بلا حارسٍ خلفه — وهو أخطرُ من غيابه: مشرفٌ
 *    يظن أن ما أطفأه مُطفأ.
 * 2. **وخليةٌ تُنقر تعني جدولَ صلاحيات** يصير مصدرَ الحقيقة بدل الكود، فتنشأ
 *    حالتان قابلتان للاختلاف لأمرِ صلاحيات — نفس ما يمنعه القسم 4 في العمولة.
 *    وحين تُطلب أدوارٌ قابلةٌ للضبط تُبنى في الخلفية أولاً.
 *
 * **ولا زرَّ «دعوة مستخدم»**: الحساب يُنشأ بإثبات ملكية رقمٍ من التطبيق (القسم
 * 15/أ)، ولا مسارَ في المشروع يفتح حساباً بلا ذلك الإثبات. ورفعُ حسابٍ قائم
 * إلى `support` تغييرُ دورٍ لا يصفه هذا المستند — فالشاشة تقول أين يقع ذلك
 * اليوم (في القاعدة، بيد من يملكها) بدل أن تخترع له باباً.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listUsers } from "@/api/endpoints";
import type { User, UserRole } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { ErrorNote } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "مالك · صلاحيات كاملة",
  support: "دعم فني",
  rider: "راكب",
  driver: "سائق",
};

/** ما تفرضه الخلفية فعلاً — كلُّ سطرٍ يقابل حارساً في `core/deps.py`. */
const MATRIX: { area: string; admin: boolean; support: boolean; note: string }[] =
  [
    {
      area: "نظرة عامة والتقارير",
      admin: true,
      support: true,
      note: "تقريرُ حالٍ لا إجراء — ومن يعالج نزاعاً يحتاج أن يرى كم منها مفتوح",
    },
    {
      area: "سجل الرحلات والركّاب (قراءة)",
      admin: true,
      support: true,
      note: "مادةُ الفصل في النزاع نفسها",
    },
    {
      area: "النزاعات والدعم (فصلٌ وقرار)",
      admin: true,
      support: true,
      note: "هذا هو نصفُ تعريف الدور في القسم 13/8",
    },
    {
      area: "الخريطة الحيّة",
      admin: true,
      support: false,
      note: "المنفذُ الوحيد الذي يقرن هويةً بموقع — وفتحُه يدخل سجل التدقيق",
    },
    {
      area: "مراجعة وثائق السائقين واعتمادُهم",
      admin: true,
      support: false,
      note: "قرارٌ يفتح باب العمل على المنصة، لا إجراءَ دعمٍ فني",
    },
    {
      area: "توثيق جنس السائق",
      admin: true,
      support: false,
      note: "إعلانُ جنس الكبتن يقيّد أمان غيره",
    },
    {
      area: "حظرُ حساب وتجميدُ محفظة",
      admin: true,
      support: false,
      note: "إغلاقُ حسابٍ أو حبسُ مالٍ ليس قراءةً ولا نزاعاً",
    },
    {
      area: "المالية: تأكيدُ الشحنات ودفعُ السحوبات",
      admin: true,
      support: false,
      note: "كلُّ حركةٍ منها قيدٌ في الدفتر",
    },
    {
      area: "الإعدادات والتسعيرة والباقات",
      admin: true,
      support: false,
      note: "تسري على التطبيقين فور الحفظ بلا نشر",
    },
    {
      area: "عقود مزوّدي API",
      admin: true,
      support: false,
      note: "الصفحةُ لـ admin حصراً (القسم 13/7)",
    },
    {
      area: "الإشعارات الجماعية",
      admin: true,
      support: false,
      note: "حملةٌ تصل عشرات الآلاف ليست إجراء دعمٍ فني",
    },
  ];

const COLUMNS = "1.6fr 1.2fr 1.2fr 1fr";

export function UsersScreen() {
  const [rows, setRows] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    // الدوران في نداءين: القائمةُ تُفلتر بدورٍ واحد، والموظفون دوران
    const [admins, support] = await Promise.all([
      listUsers({ role: "admin", limit: 100 }),
      listUsers({ role: "support", limit: 100 }),
    ]);
    setRows([...admins, ...support]);
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الحسابات",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="المستخدمون والصلاحيات"
      subtitle="دوران تفرضهما الخلفية على كل مسار — وما تخفيه الشاشة راحةٌ لا حماية"
    >
      <ErrorNote message={error} />

      <Table
        columns={COLUMNS}
        headers={["المستخدم", "الهاتف", "الدور", "منذ"]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا حسابات إدارية",
          hint: "أوّلُ حسابٍ إداريٍّ يُنشأ من سكربت التهيئة لا من هذه الشاشة.",
        }}
        render={(row) => (
          <>
            <span className="flex items-center gap-9">
              <span className="flex size-30 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-11 font-bold text-ink">
                {row.name.trim().slice(0, 1)}
              </span>
              <span className="min-w-0 truncate font-semibold text-ink">
                {row.name}
              </span>
            </span>

            <span dir="ltr" className="text-start text-muted">
              {row.phone}
            </span>

            <span>
              <Badge tone={row.role === "admin" ? "ink" : "muted"}>
                {ROLE_LABEL[row.role]}
              </Badge>
            </span>

            <span className="text-muted">{moment(row.created_at)}</span>
          </>
        )}
      />

      <section className="mt-22">
        <h2 className="mb-4 text-16 font-bold text-ink">مصفوفة الصلاحيات</h2>
        <p className="mb-12 max-w-prose text-11.5 leading-note text-muted">
          مقروءةٌ لا قابلةٌ للنقر: هذه ليست إعداداً بل وصفاً لما تفرضه الخلفية
          على كل مسار. خليةٌ تُنقر هنا كانت ستصير مصدرَ حقيقةٍ ثانياً يخالف
          الحارس، ومشرفٌ يظن أن ما أطفأه مُطفأ أسوأُ ممن يعرف أنه لا يستطيع.
        </p>

        <div className="overflow-hidden rounded-16 border border-line bg-surface">
          <div
            className="grid gap-10 bg-surface-2 px-18 py-10 text-11 font-semibold text-muted"
            style={{ gridTemplateColumns: "2fr 0.6fr 0.6fr" }}
          >
            <span>المجال</span>
            <span className="text-center">مالك</span>
            <span className="text-center">دعم فني</span>
          </div>

          {MATRIX.map((row) => (
            <div
              key={row.area}
              className="grid items-center gap-10 border-t border-line px-18 py-12"
              style={{ gridTemplateColumns: "2fr 0.6fr 0.6fr" }}
            >
              <span className="min-w-0">
                <span className="block text-12.5 text-ink">{row.area}</span>
                <span className="mt-2 block text-11 leading-note text-muted">
                  {row.note}
                </span>
              </span>
              <Cell allowed={row.admin} />
              <Cell allowed={row.support} />
            </div>
          ))}
        </div>
      </section>
    </Shell>
  );
}

/** خليةُ الصلاحية — `DESIGN.md` §2.5: `28×28`، المفعّلة `--acc`/`--inv`. */
function Cell({ allowed }: { allowed: boolean }) {
  return (
    <span className="flex justify-center">
      <span
        aria-label={allowed ? "مسموح" : "ممنوع"}
        className={cn(
          "flex size-28 items-center justify-center rounded-8 text-12 font-bold",
          allowed
            ? "bg-accent text-accent-ink"
            : "border border-line text-muted",
        )}
      >
        {allowed ? "✓" : "—"}
      </span>
    </span>
  );
}
