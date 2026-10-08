/** إطارُ اللوحة (A00، TAXO 2.0) — **عمودٌ جانبيٌّ عائمٌ بخمس مجموعات، وترويسةٌ فيها البحثُ العامّ ومبدّلُ السوق وحسابُ المشرف**.
 *
 * **والمنطقُ كما كان حرفاً** — المجموعاتُ ومساراتُها، و`adminOnly`، ومبدّلُ السوق، والمظهرُ، والخروجُ، وسطرُ التحقّق الثنائيّ —
 * **والتغييرُ في الشكل وحدَه** (`design/t2-new/admin/A00-frame.dc.html`): كانت المجموعاتُ قوائمَ منسدلةً في رأسٍ من صفّين، **فصارت
 * عموداً يُقرأ كلُّه بنظرة**، والنشطُ حبّةٌ بلون «التبويب النشط» في الهوية (`--t2-tab-on`: الجمرُ على الإسفلت والحبرُ على الحجر) —
 * **شريطُ TaxoTabs نفسُه قائماً**.
 *
 * **وتحت ١٠٢٤ بكسلاً** يصير العمودُ درجاً يُفتح بزرّ القائمة، **ويحمل في أسفله الحسابَ والمظهرَ والخروج** — فالترويسةُ على الهاتف
 * سطرٌ واحدٌ لا يُسحق فيه زرّ (AM02).
 *
 * **وآليةُ «قريباً» باقيةٌ عمداً** (`to` غائبةً تعني «لم تُبنَ بعد»): قائمةٌ تنقر فيها فلا يقع شيءٌ أسوأُ من قائمةٍ تقول «قريباً».
 *
 * **ومبدّلُ الدولة يعيش هنا** لأنه يضيّق ما تعرضه كلُّ شاشة — وهو حالةُ عرضٍ لا إعدادُ حساب، فمكانه `sessionStorage` لا الخلفية.
 *
 * **والدورُ يرسم ولا يحرس**: `support` لا يرى ما ليس له، والحمايةُ في الخلفية على كلِّ مسار (القسم 13/8) — إخفاءُ زرٍّ ليس منعاً.
 */

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { getMyTotp } from "@/api/endpoints";
import { GlobalSearch } from "@/components/GlobalSearch";
import { useCountries } from "@/lib/countries";
import { useCountry } from "@/lib/country";
import { useHolds } from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { Icon, Wordmark } from "@/taxo2";

/** **صلاحيةُ «الملخّصات المالية»** (SPEC §٦٥-د/٧) — **لا يملكها أحدٌ افتراضاً ولا المشرفُ الكامل**، فبندُها يُرسم لمن مُنحها بالاسم وحدَه
 *  (`useHolds`). **والدورُ لا يقولها**: `adminOnly` يرسم البندَ لكلِّ `admin`، وأكثرُهم يُردّ عنها. */
const FINANCE_SUMMARY = "finance.summary";

/** المجموعاتُ كما في `DESIGN.md` §3.1 — و`to` غائبةً تعني «لم تُبنَ بعد». **والأيقونةُ من الهوية** (Material Symbols Rounded). */
const GROUPS: {
  label: string;
  items: { label: string; icon: string; to?: string; adminOnly?: boolean; permission?: typeof FINANCE_SUMMARY }[];
}[] = [
  {
    label: "العمليات",
    items: [
      { label: "نظرة عامة", icon: "space_dashboard", to: "/overview" },
      { label: "الخريطة الحيّة", icon: "map", to: "/live-map", adminOnly: true },
      { label: "سجل الرحلات", icon: "route", to: "/rides" },
    ],
  },
  {
    label: "الأشخاص",
    items: [
      { label: "السائقون والوثائق", icon: "badge", to: "/drivers" },
      { label: "الركّاب", icon: "group", to: "/riders" },
      { label: "النزاعات والدعم", icon: "gavel", to: "/disputes" },
      { label: "بلاغات الصور", icon: "hide_image", to: "/photo-reports", adminOnly: true },
    ],
  },
  {
    label: "المالية",
    items: [
      { label: "المحافظ والسحب", icon: "account_balance_wallet", to: "/finance" },
      // **الملخّصاتُ المالية** (A37–A39، SPEC §٦٥-د) — أوّلَ ما تحت المحافظ: مجاميعُ المال كلِّه قبل صفوفه. **ولمن مُنحها وحدَه**
      { label: "الملخّصات المالية", icon: "receipt_long", to: "/finance/summary", permission: FINANCE_SUMMARY },
      { label: "الدفعات", icon: "payments", to: "/payments" },
      // **المدفوعاتُ غيرُ المؤكَّدة** (A10، `design/PAYMENTS-UNCONFIRMED.md` §٥) — جوارَ «الدفعات»: صفوفُها هي هي، وهذه ما ينتظر
      // أحداً منها. **وبلا `adminOnly`**: القراءةُ لـ`support` والأفعالُ يحرسها الخادم (`DisputeResolver`) كالنزاعات
      { label: "المدفوعات غير المؤكدة", icon: "request_quote", to: "/payments/unconfirmed" },
      { label: "الاشتراكات والباقات", icon: "card_membership", to: "/subscriptions" },
      { label: "عروض الاشتراكات", icon: "redeem", to: "/offers", adminOnly: true },
      { label: "التسعيرة", icon: "sell", to: "/pricing" },
      // **تحت «المالية» لا «النظام»**: المركبةُ منتَجٌ له سعرٌ وكميّةٌ وإيراد،
      // ومن يبحث عن «كم بعنا منها» يبحث حيث تُقرأ الأرقام
      { label: "مركبات المتجر", icon: "directions_car", to: "/vehicle-skins", adminOnly: true },
      { label: "مشتريات المركبات", icon: "shopping_bag", to: "/vehicle-skins/purchases", adminOnly: true },
    ],
  },
  {
    label: "التقارير",
    items: [
      { label: "التقارير والإحصاءات", icon: "bar_chart", to: "/reports" },
      { label: "الإشعارات الجماعية", icon: "campaign", to: "/campaigns", adminOnly: true },
    ],
  },
  {
    label: "النظام",
    items: [
      { label: "المستخدمون والصلاحيات", icon: "manage_accounts", to: "/users" },
      { label: "سجل التدقيق", icon: "fact_check", to: "/audit" },
      // **الأعطالُ جوارَ التدقيق**: كلاهما «ما جرى» لا «ما يُضبَط»
      { label: "الأعطال", icon: "bug_report", to: "/errors", adminOnly: true },
      { label: "الإعدادات", icon: "settings", to: "/settings" },
      // **المرافقُ الحيويّة جوارَ الإعدادات** (§٦٣-ج/٢): مفتاحُ «المطار» هناك ومناطقُه ورسمُه هنا — **وكلاهما يتبع مبدّلَ
      // الدولة**. وبلا `adminOnly` كالإعدادات: القراءةُ لطاقم اللوحة، والكتابةُ يحرسها الخادم (`SettingsWriter`)
      { label: "المرافق الحيوية", icon: "local_airport", to: "/facilities" },
      // **مساراتُ بين المدن جوارَ المرافق** (§٦٣-ج/٧): مفتاحُها ومهلتُها في الإعدادات، والمساراتُ وسعراها هنا — **وتتبع مبدّلَ
      // الدولة**. وبلا `adminOnly` كأختها: القراءةُ لطاقم اللوحة، والكتابةُ يحرسها الخادم (`SettingsWriter`)
      { label: "مسارات بين المدن", icon: "alt_route", to: "/intercity" },
      // بلا `adminOnly`: بطاقةُ «عاملي» لكل من يدخل اللوحة، وبطاقةُ السياسة
      // وحدها للـ`admin` — والشاشةُ تُخفيها بنفسها (SPEC §14.1)
      { label: "الأمان", icon: "shield", to: "/security" },
      // عالميٌّ لا يتبع مبدّلَ الدولة — الرقمُ والعقدُ عالميان
      { label: "قوالب رسائل الرمز", icon: "sms", to: "/otp-templates", adminOnly: true },
      { label: "عقود مزوّدي API", icon: "hub", to: "/providers", adminOnly: true },
      // **إصداراتُ التطبيقات** (البند ٨): إعدادُ منصّةٍ يقرّر من يفتح
      // التطبيق — لا إدارةَ أسطول، ولا يتبع مبدّلَ الدولة
      { label: "إصدارات التطبيقات", icon: "system_update", to: "/releases", adminOnly: true },
      // **السياساتُ والشروط** (البند ١٠): نصٌّ قانونيٌّ في القاعدة لا في
      // الحزمة — وتعديلُه لا يكون نشراً
      { label: "السياسات والشروط", icon: "policy", to: "/policies", adminOnly: true },
      // **الموقع** (البند ٤٩): ما يعرضه `taxo.tajora.ly` — نصوصٌ وروابطُ
      // ومفتاحُ التوزيع. **إعدادُ منصّةٍ لا إدارةُ أسطول**، ولا يتبع مبدّلَ الدولة
      { label: "الموقع", icon: "public", to: "/site", adminOnly: true },
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
 * **والصمتُ عند فشل النداء مقصود**: الإطارُ يُرسم فوق كلِّ شاشة، وشريطُ خطأٍ
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
    <div className="ad-reminder" role="status">
      <Icon name="shield" fill className="ad-reminder-icon" />
      <span className="ad-reminder-text">
        حسابك بلا تحقّقٍ بخطوتين — كلمةُ المرور وحدَها تفتح لوحةً تُدير مالَ
        الكباتن والركّاب.
      </span>
      <NavLink to="/security" className="ad-reminder-link">
        فعّله الآن
      </NavLink>
    </div>
  );
}

/** مبدّلُ السوق — **الأسواقُ من الخلفية لا من قائمةٍ مكتوبة** (SPEC §24).
 *
 * اللوحةُ ترى المخفيَّ كما ترى الظاهر، وعليه نقطةٌ تقول إنه مطفأٌ في التطبيقات — من يُجهّز سوقاً يحتاج أن يعرف أنه لم يُفتح
 * بعد. **والاختيارُ يُقرأ من سمةٍ لا من لون** (قرارُ المالك 2026-08-28): `radiogroup`/`radio` لا `switch` — **هذا اختيارٌ واحدٌ
 * من اثنين لا حالُ تشغيل**.
 */
function CountrySwitch() {
  const { country, setCountry } = useCountry();
  const { rows } = useCountries();
  // **قبل وصول الجواب تُرسم الدولةُ المعروضةُ وحدها** — لا قائمةٌ محفوظة
  // تومض ثم تُصحَّح، ولا شريطٌ فارغٌ يقفز عند وصولها
  const countries = rows ?? [
    { country_code: country, name: country, visible: true },
  ];
  return (
    <div role="radiogroup" aria-label="السوق" className="ad-seg ad-country">
      {countries.map((row) => (
        <button
          key={row.country_code}
          type="button"
          role="radio"
          aria-checked={country === row.country_code}
          onClick={() => setCountry(row.country_code)}
          title={row.visible ? undefined : "مخفيّة في التطبيقات"}
          className={country === row.country_code ? "ad-seg-opt on" : "ad-seg-opt"}
        >
          {!row.visible && (
            <span aria-label="مخفيّة في التطبيقات" className="ad-seg-dot" />
          )}
          {row.name}
        </button>
      ))}
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
  const { pathname } = useLocation();
  const { user, isAdmin, signOut } = useSession();
  const { dark, toggle } = useTheme();
  // **قبل الجواب لا يُرسم البند** (`null`) — بندٌ يظهر ثمّ يختفي أسوأُ من بندٍ يتأخّر لحظة
  const holdsSummary = useHolds(FINANCE_SUMMARY) === true;
  // **درجُ القائمة على الهاتف** — يُغلق بالتنقّل، وبالنقر خارجه، وبـEsc
  const [menu, setMenu] = useState(false);
  const nav = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setMenu(false);
  }, [pathname]);

  // **النشطُ في مرمى العين**: كلُّ شاشةٍ ترسم إطارَها فيُبنى العمودُ من جديد — وعمودٌ أطولُ من الشاشة (٢٦ قسماً للمالك)
  // كان سيعود إلى أوّله فيخفي «الموقع» تحت الطيّ وهو المفتوح. **يُمرَّر العمودُ وحدَه لا الصفحة** — عند كلِّ رسمٍ له،
  // **وعند فتح الدرج على الهاتف** (مغلقاً لا يُرسم فلا ارتفاعَ يُقاس)
  useEffect(() => {
    const list = nav.current;
    const item = list?.querySelector<HTMLElement>(".ad-nav-item.on");
    if (!list || !item || list.clientHeight === 0) return;
    if (item.offsetTop + item.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = item.offsetTop - list.clientHeight / 2;
    }
  }, [pathname, menu]);

  useEffect(() => {
    if (!menu) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  const initial = (user?.name ?? "").trim().slice(0, 1);
  const role = ROLE_LABEL[user?.role ?? ""] ?? user?.role;
  const leave = () => void signOut().then(() => navigate("/login"));
  const themeLabel = "تبديل المظهر";
  const themeIcon = dark ? "light_mode" : "dark_mode";

  return (
    <div className="ad-app">
      <aside
        id="ad-side"
        className={menu ? "ad-side open" : "ad-side"}
        aria-label="أقسام اللوحة"
      >
        <div className="ad-side-brand">
          <Wordmark size={24} />
          <span className="ad-side-tag">لوحة التحكم</span>
          <button
            type="button"
            className="ad-round ad-side-close"
            onClick={() => setMenu(false)}
            aria-label="إغلاق القائمة"
          >
            <Icon name="close" />
          </button>
        </div>

        <nav ref={nav} className="ad-nav scr">
          {GROUPS.map((group) => {
            const items = group.items.filter(
              (item) => (!item.adminOnly || isAdmin) && (item.permission !== FINANCE_SUMMARY || holdsSummary),
            );
            if (items.length === 0) return null;
            return (
              <div key={group.label} className="ad-nav-group">
                <p className="ad-nav-label">{group.label}</p>
                {items.map((item) =>
                  item.to ? (
                    <NavLink
                      key={item.label}
                      to={item.to}
                      // `end` — «مركبات المتجر» لا تبقى نشطةً تحت «مشتريات المركبات»
                      end
                      className={({ isActive }) =>
                        isActive ? "ad-nav-item on" : "ad-nav-item"
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <Icon name={item.icon} fill={isActive} />
                          <span>{item.label}</span>
                        </>
                      )}
                    </NavLink>
                  ) : (
                    <span key={item.label} className="ad-nav-item soon">
                      <Icon name={item.icon} />
                      <span>{item.label}</span>
                      <span className="ad-nav-soon">قريباً</span>
                    </span>
                  ),
                )}
              </div>
            );
          })}
        </nav>

        {/* **على الهاتف وحدَه**: الحسابُ والمظهرُ والخروجُ في أسفل الدرج — والترويسةُ تحملها على الحاسوب */}
        <div className="ad-side-foot">
          <div className="ad-account flat">
            <span className="ad-avatar">{initial}</span>
            <span className="ad-account-text">
              <span className="ad-account-name">{user?.name}</span>
              <span className="ad-account-role">{role}</span>
            </span>
          </div>
          <div className="ad-side-actions">
            <button type="button" className="ad-btn ad-btn-secondary ad-btn-md" onClick={toggle} aria-label={themeLabel}>
              <Icon name={themeIcon} />
              المظهر
            </button>
            <button type="button" className="ad-btn ad-btn-secondary ad-btn-md" onClick={leave}>
              <Icon name="logout" />
              خروج
            </button>
          </div>
        </div>
      </aside>

      {menu ? (
        <div className="ad-scrim" onClick={() => setMenu(false)} aria-hidden="true" />
      ) : null}

      <div className="ad-main">
        {/* `safe-top` — **قصاصةُ أعلى الشاشة**: الترويسةُ لاصقة، **وبلا الحشوة يقع سطرُها الأوّل تحت الحزّ** */}
        <header className="ad-head safe-top">
          <button
            type="button"
            className="ad-round ad-menu"
            onClick={() => setMenu(true)}
            aria-label="القائمة"
            aria-expanded={menu}
            aria-controls="ad-side"
          >
            <Icon name="menu" />
          </button>
          <span className="ad-head-mark">
            <Wordmark size={21} />
          </span>

          {/* **البحثُ العامُّ أوّلَ الترويسة** (§39٫١٢٫٤): أداةُ عملٍ لا زرُّ حساب، **ومكانُه حيث تقع العينُ أوّلاً** */}
          <GlobalSearch />
          <CountrySwitch />

          <span className="ad-head-gap" />

          {/* **الاسمُ والدورُ خبرٌ لا زرّ** — والزرّان بجانبه ٤٤ لا يُسحقان */}
          <button type="button" onClick={toggle} aria-label={themeLabel} className="ad-round ad-desk">
            <Icon name={themeIcon} />
          </button>
          <div className="ad-account ad-desk">
            <span className="ad-avatar">{initial}</span>
            <span className="ad-account-text">
              <span className="ad-account-name">{user?.name}</span>
              <span className="ad-account-role">{role}</span>
            </span>
          </div>
          <button type="button" onClick={leave} aria-label="خروج" className="ad-round ad-desk">
            <Icon name="logout" />
          </button>
        </header>

        <FactorReminder />

        <main className="ad-page safe-bottom">
          <div className="ad-page-head">
            <div className="ad-page-titles">
              <h1 className="ad-page-title">{title}</h1>
              {subtitle ? <p className="ad-page-sub">{subtitle}</p> : null}
            </div>
            {actions ? <div className="ad-page-actions">{actions}</div> : null}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
