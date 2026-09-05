/** هيكلُ اللوحة: رأسٌ لاصق من صفّين — `DESIGN.md` §3.1.
 *
 * **وأقسامُ المرحلة 11 كلُّها مبنيّةٌ الآن**، فلا عنصرَ في القائمة بلا شاشة.
 * وآليةُ «قريباً» باقيةٌ عمداً (`to` غائبةً تعني «لم تُبنَ بعد»): ما يرسمه
 * التصميم من أقسامٍ خارج القسم 13 — الرحلاتُ المجدولة والكوبونات وما معهما —
 * يقع في المرحلة 12، ويوم يُضاف اسمُه هنا يُرسم معطّلاً يقول حالَه. وقائمةٌ
 * تنقر فيها فلا يقع شيء أسوأ من قائمةٍ تقول «قريباً»: الأولى تجعل المستخدم
 * يشك في اللوحة، والثانية تخبره بحالها.
 *
 * **ومبدّلُ الدولة يعيش هنا** لأنه يضيّق ما تعرضه كلُّ شاشة: صفحةُ الحملات
 * تقرأ منه الدولةَ التي تُجدول فيها وساعاتِ هدوئها. وهو حالةُ عرضٍ لا إعداد
 * حساب، فمكانه `sessionStorage` لا الخلفية.
 *
 * **والدور يرسم ولا يحرس**: `support` لا يرى ما ليس له، والحمايةُ في الخلفية
 * على كل مسار (القسم 13/8) — إخفاءُ زرٍّ ليس منعاً.
 */

import { AlertTriangle, LogOut, Moon, Sun } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

import { GlobalSearch } from "@/components/GlobalSearch";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useCountries } from "@/lib/countries";
import { useCountry } from "@/lib/country";
import { getMyTotp } from "@/api/endpoints";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/** المجموعات كما في `DESIGN.md` §3.1 — و`to` غائبةً تعني «لم تُبنَ بعد». */
const GROUPS: {
  label: string;
  items: { label: string; to?: string; adminOnly?: boolean }[];
}[] = [
  {
    label: "العمليات",
    items: [
      { label: "نظرة عامة", to: "/overview" },
      { label: "الخريطة الحيّة", to: "/live-map", adminOnly: true },
      { label: "سجل الرحلات", to: "/rides" },
    ],
  },
  {
    label: "الأشخاص",
    items: [
      { label: "السائقون والوثائق", to: "/drivers" },
      { label: "الركّاب", to: "/riders" },
      { label: "النزاعات والدعم", to: "/disputes" },
      { label: "بلاغات الصور", to: "/photo-reports", adminOnly: true },
    ],
  },
  {
    label: "المالية",
    items: [
      { label: "المحافظ والسحب", to: "/finance" },
      { label: "الدفعات", to: "/payments" },
      { label: "الاشتراكات والباقات", to: "/subscriptions" },
      { label: "عروض الاشتراكات", to: "/offers", adminOnly: true },
      { label: "التسعيرة", to: "/pricing" },
      // **تحت «المالية» لا «النظام»**: المركبةُ منتَجٌ له سعرٌ وكميّةٌ وإيراد،
      // ومن يبحث عن «كم بعنا منها» يبحث حيث تُقرأ الأرقام
      { label: "مركبات المتجر", to: "/vehicle-skins", adminOnly: true },
      { label: "مشتريات المركبات", to: "/vehicle-skins/purchases", adminOnly: true },
    ],
  },
  {
    label: "التقارير",
    items: [
      { label: "التقارير والإحصاءات", to: "/reports" },
      { label: "الإشعارات الجماعية", to: "/campaigns", adminOnly: true },
    ],
  },
  {
    label: "النظام",
    items: [
      { label: "المستخدمون والصلاحيات", to: "/users" },
      { label: "سجل التدقيق", to: "/audit" },
      { label: "الإعدادات", to: "/settings" },
      // بلا `adminOnly`: بطاقةُ «عاملي» لكل من يدخل اللوحة، وبطاقةُ السياسة
      // وحدها للـ`admin` — والشاشةُ تُخفيها بنفسها (SPEC §14.1)
      { label: "الأمان", to: "/security" },
      // عالميٌّ لا يتبع مبدّلَ الدولة — الرقمُ والعقدُ عالميان
      { label: "قوالب رسائل الرمز", to: "/otp-templates", adminOnly: true },
      { label: "عقود مزوّدي API", to: "/providers", adminOnly: true },
      // **إصداراتُ التطبيقات** (البند ٨): إعدادُ منصّةٍ يقرّر من يفتح
      // التطبيق — لا إدارةَ أسطول، ولا يتبع مبدّلَ الدولة
      { label: "إصدارات التطبيقات", to: "/releases", adminOnly: true },
      // **السياساتُ والشروط** (البند ١٠): نصٌّ قانونيٌّ في القاعدة لا في
      // الحزمة — وتعديلُه لا يكون نشراً
      { label: "السياسات والشروط", to: "/policies", adminOnly: true },
      // **الموقع** (البند ٤٩): ما يعرضه `taxo.tajora.ly` — نصوصٌ وروابطُ
      // ومفتاحُ التوزيع. **إعدادُ منصّةٍ لا إدارةُ أسطول**، ولا يتبع مبدّلَ الدولة
      { label: "الموقع", to: "/site", adminOnly: true },
    ],
  },
];

const ROLE_LABEL: Record<string, string> = {
  admin: "مالك · صلاحيات كاملة",
  support: "دعم فني",
};


/** **سطرٌ دائمٌ لمشرفٍ بلا عاملٍ ثانٍ** (شرطُ المالك 2026-08-21).
 *
 * **ولماذا سطرٌ لا نافذة**: النافذةُ تُغلق فتُنسى، وتُغلق أسرعَ كلَّما تكرّرت —
 * فتصير التكرارُ نفسُه هو ما يعلّم تجاهلَها. والسطرُ لا يُغلق: يبقى ما بقي
 * السبب، **ويختفي وحدَه لحظةَ تأكيد العامل** — فزوالُه خبرٌ لا زرّ.
 *
 * **ولا يُعرض لغير `admin`**: `support` تسجيلُه اختياريٌّ اليوم
 * (`security_settings.totp_required_for`)، وتذكيرُ من لا يُلزَم ضجيجٌ يُطفأ.
 *
 * **ولا يُعرض على حساب الطوارئ**: هو مُعفىً بقرارٍ مكتوب، فتذكيرُه يدعوه إلى
 * ما يُبطل وجودَه. والخلفيةُ هي التي تقرّر — `required` تصل من `/auth/me/totp`
 * محسوبةً هناك، ولا تُحسب هنا ثانيةً: قاعدةٌ في مكانين تفترق.
 *
 * **والصمتُ عند فشل النداء مقصود**: القشرةُ تُرسم فوق كلِّ شاشة، وشريطُ خطأٍ
 * لأن نداءً تعثّر يزاحم عملاً حقيقياً بخبرٍ لا يفيد.
 */
function FactorReminder() {
  const { isAdmin } = useSession();
  const [due, setDue] = useState(false);

  useEffect(() => {
    if (!isAdmin) return;
    let alive = true;
    getMyTotp()
      .then((status) => {
        if (alive) setDue(!status.confirmed);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [isAdmin]);

  if (!due) return null;
  return (
    <div className="border-b border-warn bg-surface-2 px-20 py-9">
      <div className="mx-auto flex max-w-screen-2xl items-center gap-9 text-12 text-ink">
        <AlertTriangle size={15} className="shrink-0 text-warn" />
        <span className="min-w-0 flex-1">
          حسابك بلا تحقّقٍ بخطوتين — كلمةُ المرور وحدَها تفتح لوحةً تُدير مالَ
          الكباتن والركّاب.
        </span>
        <NavLink
          to="/security"
          className="shrink-0 rounded-10 border border-line bg-surface px-10 py-5 text-11.5 font-semibold text-ink"
        >
          فعّله الآن
        </NavLink>
      </div>
    </div>
  );
}

export function Shell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const { user, isAdmin, signOut } = useSession();
  const { dark, toggle } = useTheme();
  const { country, setCountry } = useCountry();
  const { rows } = useCountries();
  // **قبل وصول الجواب تُرسم الدولةُ المعروضةُ وحدها** — لا قائمةٌ محفوظة
  // تومض ثم تُصحَّح، ولا شريطٌ فارغٌ يقفز عند وصولها
  const countries = rows ?? [
    { country_code: country, name: country, visible: true },
  ];

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="flex h-header items-center gap-14 px-20">
          <span className="text-21 font-bold tracking-wordmark text-ink">
            TAXO
          </span>
          <span className="text-12.5 text-muted">لوحة التحكم</span>
          <span className="block h-26 w-px bg-line" />

          {/* **الأسواقُ من الخلفية لا من قائمةٍ مكتوبة** (SPEC §24): اللوحةُ
              ترى المخفيَّ كما ترى الظاهر، وعليه نقطةٌ تقول إنه مطفأٌ في
              التطبيقات — من يُجهّز سوقاً يحتاج أن يعرف أنه لم يُفتح بعد. */}
          {/* **الاختيارُ يُقرأ من سمةٍ لا من لون** (قرارُ المالك 2026-08-28):
              كان السوقُ المختارُ يُميَّز بخلفيةٍ وحدَها، **فقارئُ الشاشة يقرأ
              زرَّين بلا أن يعرف أيَّهما قائم**. وهي علّةُ المفاتيح نفسُها في
              ثوبِ اختيارٍ من متعدّد — فيُوسَم `radiogroup`/`radio` لا
              `switch`: **هذا اختيارٌ واحدٌ من اثنين لا حالُ تشغيل**. */}
          <div
            role="radiogroup"
            aria-label="السوق"
            className="flex items-center gap-3 rounded-full bg-surface-2 p-3"
          >
            {countries.map((row) => (
              <button
                key={row.country_code}
                type="button"
                role="radio"
                aria-checked={country === row.country_code}
                onClick={() => setCountry(row.country_code)}
                title={row.visible ? undefined : "مخفيّة في التطبيقات"}
                className={cn(
                  "flex items-center gap-6 rounded-full px-13 py-6 text-12 font-semibold",
                  country === row.country_code
                    ? "bg-surface text-ink"
                    : "text-muted",
                )}
              >
                {!row.visible && (
                  <span
                    aria-label="مخفيّة في التطبيقات"
                    className="size-6 rounded-full bg-muted"
                  />
                )}
                {row.name}
              </button>
            ))}
          </div>

          {/* **البحثُ العامُّ قبل الفاصل لا بعده** (§39٫١٢٫٤): هو أداةُ
              عملٍ لا زرَّ حساب، **ومكانُه حيث تقع العينُ أوّلاً**. */}
          <GlobalSearch />

          <div className="ms-auto flex items-center gap-10">
            <div className="text-end">
              <div className="text-12.5 font-semibold text-ink">
                {user?.name}
              </div>
              <div className="text-10.5 text-muted">
                {ROLE_LABEL[user?.role ?? ""] ?? user?.role}
              </div>
            </div>
            <button
              type="button"
              onClick={toggle}
              aria-label="تبديل المظهر"
              className="flex size-34 items-center justify-center rounded-10 border border-line text-ink"
            >
              {dark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button
              type="button"
              onClick={() => void signOut().then(() => navigate("/login"))}
              aria-label="خروج"
              className="flex size-34 items-center justify-center rounded-10 border border-line text-ink"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>

        {/* **بلا `overflow-x-auto`** — وهذا ليس تفصيلاً تجميلياً: CSS يجعل المحورَ
            الآخر `auto` حين يكون أحدُهما `auto` (`visible` تُحسب `auto`)، فيصير
            الشريطُ حاويةَ قصٍّ رأسياً وقائمتُه المنسدلة **ابنتُه**. وقياسُ
            المتصفح: القائمةُ 130px تُقَص كاملةً (`menuBottom 230` مقابل
            `navBottom 100`) فيصير `scrollHeight` 172 في صندوقٍ ارتفاعُه 42، ويرسم
            المتصفحُ شريطَ تمريرٍ عمودياً — على الحافة اليسرى في RTL.
            و`flex-wrap` بدلَه: خمسُ مجموعاتٍ × 72px لا تحتاج تمريراً في شريطٍ
            عرضُه 1024 فما فوق، وتلتفّ إن ضاق أكثر. */}
        <nav className="flex flex-wrap items-end gap-2 px-20">
          {GROUPS.map((group) => (
            <div key={group.label} className="group relative">
              <span className="block cursor-default px-14 pb-10 pt-12 text-13 font-semibold text-muted">
                {group.label}
              </span>
              <div className="absolute start-0 top-full z-40 hidden min-w-menu rounded-14 border border-line bg-surface p-6 shadow-menu group-hover:block">
                {group.items
                  .filter((item) => !item.adminOnly || isAdmin)
                  .map((item) =>
                    item.to ? (
                      <NavLink
                        key={item.label}
                        to={item.to}
                        className={({ isActive }) =>
                          cn(
                            "block rounded-10 px-12 py-10 text-12.5",
                            isActive
                              ? "bg-stripe-a font-bold text-ink"
                              : "text-ink",
                          )
                        }
                      >
                        {item.label}
                      </NavLink>
                    ) : (
                      <span
                        key={item.label}
                        className="flex items-center justify-between rounded-10 px-12 py-10 text-12.5 text-muted"
                      >
                        {item.label}
                        <span className="text-9.5">قريباً</span>
                      </span>
                    ),
                  )}
              </div>
            </div>
          ))}
        </nav>
      </header>

      <FactorReminder />

      <main className="px-20 py-18">
        <div className="mb-16 flex items-start justify-between gap-16">
          <div>
            <h1 className="text-21 font-bold text-ink">{title}</h1>
            {subtitle ? (
              <p className="mt-3 text-12.5 text-muted">{subtitle}</p>
            ) : null}
          </div>
          {actions ? <div className="flex gap-10">{actions}</div> : null}
        </div>
        {children}
      </main>
    </div>
  );
}
