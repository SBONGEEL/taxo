/** حسابي — TAXO 2.0 «R15» (Claude Design «Rider»)، **في المظهر النهاريّ المرسوم وحدَه**.
 *
 * **لا طلبَ جديد**: الاسمُ والرقمُ من الجلسة، وعددُ الأماكن من `PlacesProvider` (محمَّلةٌ عند الإقلاع).
 * **والأبوابُ أبوابُ الشاشة القائمة كلُّها** (`screens/Account.tsx`) بمفاتيحها، وفعلا التبديلِ وإنهاءِ
 * الجلسات من بيتيهما (`useSwitchToDriver` · `SignOutEverywhereRow`) — فلا تفترق الشاشتان.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٦):
 * - **الأرقامُ الثلاثة** (رحلة · تقييمك · معنا منذ): الأولان ليسا في `GET /auth/me` — حقلان جديدان.
 * - **بطاقةُ الخدمة النسائية بمفتاحها**: «نطابقك مع كبتنة كلما توفرت» تفضيلٌ يرجع إلى أيِّ كبتن، والتفضيلُ
 *   اليومَ «كبتنة فقط» — وهي من البند ١٣ الذي ينتظر شاشاتِه. ويبقى التفضيلُ في «بياناتي».
 * - **«الأمان وجهات الطوارئ» · «المساعدة والدعم» · «الشروط والخصوصية»**: لا شاشةَ لها في التطبيق.
 * - **«اللغة»**: محذوفةٌ بقرار المالك (§61) — التطبيقُ عربيٌّ وحدَه.
 * - **«VISA 4242» بجانب طرق الدفع**: تحتاج `GET /me/cards` هنا — طلبٌ جديد.
 *
 * **وما في الشاشة القائمة ولم يُرسم يبقى** بلغة القائمة: رحلاتي المجدولة (خلف مفتاحها) · ادعُ صديقك ·
 * الإشعارات · الإعدادات · حذفُ الحساب (آخرَ القائمة بقصد) · التبديلُ إلى تطبيق السائق · إنهاءُ كلِّ الجلسات.
 * **و«بياناتي» صار زرَّ القلم في الرأس** كما في اللوحة — البابُ نفسُه.
 */

import { useNavigate } from "react-router-dom";

import { useScheduledRides } from "@/lib/bookings";
import { usePlaces } from "@/lib/places";
import { useSession } from "@/lib/session";
import { useSwitchToDriver } from "@/lib/switch-app";
import { SignOutEverywhereRow } from "@/screens/Account";

import "./t2.css";

interface Row {
  to: string;
  icon: string;
  label: string;
  /** ما يُكتب في طرف الصفّ — **ممّا في الذاكرة لا من طلب**. */
  trailing?: string;
}

export function AccountT2Screen() {
  const navigate = useNavigate();
  const { user, signOut } = useSession();
  const { places } = usePlaces();
  const scheduled = useScheduledRides();
  const swap = useSwitchToDriver();

  const rows: Row[] = [
    {
      to: "/account/places",
      icon: "bookmark",
      label: "الأماكن المحفوظة",
      trailing: places.length > 0 ? String(places.length) : undefined,
    },
    { to: "/account/cards", icon: "credit_card", label: "طرق الدفع" },
    // **خلف مفتاحه** (12-ط) كما في الشاشة القائمة: صفٌّ يفتح شاشةً فارغةً في سوقٍ مطفأٍ يُقرأ عطباً
    ...(scheduled ? [{ to: "/account/bookings", icon: "event_upcoming", label: "رحلاتي المجدولة" }] : []),
    { to: "/account/referrals", icon: "redeem", label: "ادعُ صديقك" },
    { to: "/account/notifications", icon: "notifications", label: "الإشعارات" },
    { to: "/account/settings", icon: "settings", label: "الإعدادات" },
    // **حذفُ الحساب آخرَ القائمة بقصد** (٢٠٢٦-٠٩-٠٧) — **وظاهرٌ لا مخفيّ**: شرطُ المتجر «an in-app path»
    { to: "/account/delete", icon: "delete", label: "حذف الحساب" },
  ];

  return (
    <div className="t2 t2-page t2-account pb-nav">
      <div className="t2-prof">
        <span className="t2-avatar">{user?.name.slice(0, 1) ?? "؟"}</span>
        <div className="t2-prof-main">
          <div className="t2-prof-name">{user?.name}</div>
          {/* **الرقمُ لا يُحرَّر ولا يُعرَّب** — معرَّفٌ يُقارَن ويُملى (الشاشةُ القائمة) */}
          <div dir="ltr" className="t2-prof-phone">
            {user?.phone}
          </div>
        </div>
        <button
          type="button"
          className="t2-back t2-edit"
          aria-label="بياناتي"
          onClick={() => navigate("/account/profile")}
        >
          <span className="t2-icon" aria-hidden="true">edit</span>
        </button>
      </div>

      <div className="t2-list t2-arows">
        {rows.map((row) => (
          <button key={row.to} type="button" className="t2-arow" onClick={() => navigate(row.to)}>
            <span className="t2-icon" aria-hidden="true">{row.icon}</span>
            <span className="t2-arow-label">{row.label}</span>
            {row.trailing ? <span className="t2-arow-trail">{row.trailing}</span> : null}
            <span className="t2-icon t2-chev" aria-hidden="true">chevron_left</span>
          </button>
        ))}
      </div>

      {/* **التبديلُ آخرَ صفٍّ قبل الخروج** (§23) — أقربُ ما يكون إليه معنىً: مغادرةُ هذا التطبيق */}
      <div className="t2-list t2-arows">
        <button type="button" className="t2-arow tall" disabled={swap.busy} onClick={() => void swap.press()}>
          <span className="t2-icon" aria-hidden="true">directions_car</span>
          <span className="t2-arow-label">
            تبديل إلى تطبيق السائق
            <span className="t2-arow-sub">نفس الحساب — تنتقل جلستك بلا تسجيل دخول</span>
          </span>
          <span className="t2-icon t2-chev" aria-hidden="true">chevron_left</span>
        </button>
        {swap.blocked ? <p className="t2-arow-note">{swap.blocked}</p> : null}
      </div>

      <button type="button" className="t2-logout" onClick={() => void signOut()}>
        تسجيل الخروج
      </button>

      <SignOutEverywhereRow className="t2-endall" />
    </div>
  );
}
