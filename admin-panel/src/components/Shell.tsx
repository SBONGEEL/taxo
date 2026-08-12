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

import { LogOut, Moon, Sun } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import type { CountryCode } from "@/api/types";
import { useCountry } from "@/lib/country";
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
    ],
  },
  {
    label: "المالية",
    items: [
      { label: "المحافظ والسحب", to: "/finance" },
      { label: "الاشتراكات والباقات", to: "/subscriptions" },
      { label: "التسعيرة", to: "/pricing" },
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
      { label: "عقود مزوّدي API", to: "/providers", adminOnly: true },
    ],
  },
];

const COUNTRY_LABEL: Record<CountryCode, string> = {
  JO: "الأردن",
  LY: "ليبيا",
};

const ROLE_LABEL: Record<string, string> = {
  admin: "مالك · صلاحيات كاملة",
  support: "دعم فني",
};

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

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="flex h-header items-center gap-14 px-20">
          <span className="text-21 font-bold tracking-wordmark text-ink">
            TAXO
          </span>
          <span className="text-12.5 text-muted">لوحة التحكم</span>
          <span className="block h-26 w-px bg-line" />

          <div className="flex items-center gap-3 rounded-full bg-surface-2 p-3">
            {(["JO", "LY"] as CountryCode[]).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setCountry(code)}
                className={cn(
                  "rounded-full px-13 py-6 text-12 font-semibold",
                  country === code ? "bg-surface text-ink" : "text-muted",
                )}
              >
                {COUNTRY_LABEL[code]}
              </button>
            ))}
          </div>

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

        <nav className="flex items-end gap-2 overflow-x-auto px-20">
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
