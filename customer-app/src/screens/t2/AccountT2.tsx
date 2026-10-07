/** حسابي — TAXO 2.0 «R15» (Claude Design «Rider»)، **في المظهرين** — رُسم نهاريّاً، **والليليُّ برموز إسفلت الهوية نفسِها** (§٦٢/٣).
 *
 * **لا طلبَ جديد**: الاسمُ والرقمُ من الجلسة، وعددُ الأماكن من `PlacesProvider` (محمَّلةٌ عند الإقلاع).
 * **والأبوابُ أبوابُ الشاشة القائمة كلُّها** (`screens/Account.tsx`) بمفاتيحها، وفعلا التبديلِ وإنهاءِ
 * الجلسات من بيتيهما (`useSwitchToDriver` · `SignOutEverywhereRow`) — فلا تفترق الشاشتان.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٦):
 * - ~~الأرقامُ الثلاثة~~ **بُنيت بقرار المالك** (§٦١-ط/٢): رحلاتُه وتقييمُه من `GET /rides/me/summary`، و«معنا منذ» سنةُ الحساب.
 * - ~~بطاقةُ الخدمة النسائية~~ **بُنيت** (§٦٢-ج/٢٣، `WomenServiceT2.tsx`): تعكس التفضيلَ الافتراضيَّ وتفتح RW1 — **و«كلما توفرت»
 *   لم تُكتب** (علّتُها هناك). ويبقى التفضيلُ بخياراته الثلاثة في «بياناتي».
 * - **«الأمان وجهات الطوارئ»**: تنتظر إقرارَ البيانات (§٦٢-ج/١٨) — **و«الشروط والخصوصية» بُنيت** (§٦١-ط/٣) صفّاً يفتح صفحتي
 *   الموقع، **و«المساعدة والدعم» بُنيت** (§٦٢-ج/١٦، R30) قبلها كما رُسمت.
 * - **«اللغة»**: محذوفةٌ بقرار المالك (§61) — التطبيقُ عربيٌّ وحدَه.
 * - **«VISA 4242» بجانب طرق الدفع**: تحتاج `GET /me/cards` هنا — طلبٌ جديد.
 *
 * **وما في الشاشة القائمة ولم يُرسم يبقى** بلغة القائمة: رحلاتي المجدولة (خلف مفتاحها) · **مشوارٌ ثابت واشتراكاتي** (§٦٣-ج/٦) ·
 * **بين المدن وحجوزاتُه** (§٦٣-ج/٧) · ادعُ صديقك ·
 * الإشعارات · الإعدادات · حذفُ الحساب (آخرَ القائمة بقصد) · التبديلُ إلى تطبيق السائق · إنهاءُ كلِّ الجلسات.
 * **و«بياناتي» صار زرَّ القلم في الرأس** كما في اللوحة — البابُ نفسُه.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getRiderSummary } from "@/api/endpoints";
import type { RiderSummary } from "@/api/types";

import {
  useCommuteService,
  useHasCommutes,
  useHasIntercityBookings,
  useIntercityService,
  useScheduledRides,
} from "@/lib/bookings";
import { usePlaces } from "@/lib/places";
import { useSession } from "@/lib/session";
import { useSwitchToDriver } from "@/lib/switch-app";
import { SignOutEverywhereRow } from "@/components/account/SignOutEverywhere";

import { WomenServiceCardT2 } from "./WomenServiceT2";
import "@/taxo2";
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
  const commuteService = useCommuteService();
  const hasCommutes = useHasCommutes();
  const intercity = useIntercityService();
  const hasIntercity = useHasIntercityBookings();
  const swap = useSwitchToDriver();
  // **الأرقامُ من الخلفية** (§٦١-ط/٢) — وحتى تصل، أو إن تعثّرت، «—» لا صفرٌ يُقرأ خبراً
  const [summary, setSummary] = useState<RiderSummary | null>(null);
  useEffect(() => {
    let live = true;
    getRiderSummary()
      .then((value) => {
        if (live) setSummary(value);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  const since = user ? new Date(user.created_at).getFullYear() : null;

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
    // **المشوارُ الثابت** (§٦٣-ج/٦) — لا بلاطةَ له في الرئيسية (بلاطاتُها كما رُسمت، ومقاصدُ المتجر مسجَّلةٌ في الخلفية)، **فبيتُه هنا
    // بجوار أخيه المجدول**: بابُ الجديد خلف مفتاحه، **و«اشتراكاتي» لمن له اشتراكٌ ولو أُطفئ المفتاح** — مالُه مدفوعٌ ويُرى
    ...(commuteService ? [{ to: "/account/commute", icon: "event_repeat", label: "مشوارٌ ثابت" }] : []),
    ...(hasCommutes ? [{ to: "/account/commutes", icon: "card_membership", label: "اشتراكاتي" }] : []),
    // **بين المدن** (§٦٣-ج/٧) — بجوار أخويه وبحكمهما: التصفّحُ والحجزُ خلف مفتاحه (المالكُ يراجع القانونَ قبل إشعاله)، **و«حجوزاتي
    // بين المدن» لمن له حجزٌ ولو أُطفئ** — مقعدٌ دُفع ثمنُه لا يختفي بمفتاح
    ...(intercity ? [{ to: "/account/intercity", icon: "route", label: "بين المدن" }] : []),
    ...(hasIntercity ? [{ to: "/account/intercity/bookings", icon: "event_upcoming", label: "حجوزاتي بين المدن" }] : []),
    { to: "/account/referrals", icon: "redeem", label: "ادعُ صديقك" },
    { to: "/account/notifications", icon: "notifications", label: "الإشعارات" },
    { to: "/account/settings", icon: "settings", label: "الإعدادات" },
    // **«المساعدة والدعم» قبل «الشروط والخصوصية» كما رُسمتا في R15** (§٦٢-ج/١٦) — الأسئلةُ وبريدُ الدعم من إعدادات الموقع
    { to: "/account/help", icon: "help", label: "المساعدة والدعم" },
    // **قوقل تشترط بلوغَ السياسات من داخل التطبيق** (§٦١-و/٦) — قبل الحذف الذي يبقى آخرَ القائمة
    { to: "/account/legal", icon: "gavel", label: "الشروط والخصوصية" },
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

      <div className="t2-stats">
        <div className="t2-stat">
          <div className="t2-stat-num" dir="ltr">{summary ? summary.completed_rides : "—"}</div>
          <div className="t2-stat-label">رحلة</div>
        </div>
        <div
          className="t2-stat"
          aria-label={summary && summary.ratings_count > 0 ? `تقييمك ${summary.rating_avg} من ${summary.ratings_count} تقييمات` : undefined}
        >
          <div className="t2-stat-num" dir="ltr">{summary?.rating_avg ?? "—"}</div>
          <div className="t2-stat-label">تقييمك</div>
        </div>
        <div className="t2-stat">
          <div className="t2-stat-num" dir="ltr">{since ?? "—"}</div>
          <div className="t2-stat-label">معنا منذ</div>
        </div>
      </div>

      {/* **بطاقةُ الخدمة النسائية بين الأرقام والصفوف كما رُسمت** (R15، §٦٢-ج/٢٣) — وبشرطها من `lib/women.ts` */}
      <WomenServiceCardT2 />

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
