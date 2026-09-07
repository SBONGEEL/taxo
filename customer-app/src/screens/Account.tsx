import { useState } from "react";
/** «حسابي» — التبويبُ الرابع وحاويةُ ما تحته (`tabAccount`، القراران 22 و23).
 *
 * **حاويةٌ لا شاشةُ تحرير**: الرأسُ يعرض ما يُقرأ ولا يُحرَّر (الاسم والرقم)،
 * والصفوفُ أبوابُ ستِّ شاشاتٍ صارت تحت `/account/*`. وتحريرُ البيانات نفسِه
 * صفٌّ منها («بياناتي») لا محتوىً هنا — وإلا صارت الحاويةُ شاشةً طويلةً يُبحث
 * فيها عن مفتاح، وهو ما فرّقه القرارُ (د) أصلاً بين ما يخصّ **الجهاز** وما يخصّ
 * **الحساب**.
 *
 * **والرقمُ لا يُحرَّر ولا يُعرَّب**: هو هويةُ الدخول وقد أُثبت مرةً
 * (`users.phone_verified_at`)، فتغييرُه من شاشةٍ بلا إعادة إثبات بابُ سرقةِ
 * حساب — وهو **معرَّفٌ يُقارَن ويُملى** لا كمّيةٌ تُقرأ (قاعدةُ `Cards.tsx`).
 *
 * **وتسجيلُ الخروج هنا** كما في النموذج، لا في «بياناتي»: بابان لفعلٍ واحدٍ
 * يفترقان أوّلَ مرةٍ يتغيّر أحدُهما، والنموذجُ يضعه أسفلَ هذه الشاشة.
 */

import { ChevronLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Screen } from "@/components/ui/Screen";
import { useScheduledRides } from "@/lib/bookings";
import { blockedReason, switchToDriver } from "@/lib/switch-app";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

interface Row {
  to: string;
  label: string;
  sub: string;
  /** مفتاحُ الميزة الذي يحكم ظهورَ الصف — والصفُّ يُخفى لا يُعطَّل. */
  scheduled?: boolean;
}

const ROWS: Row[] = [
  { to: "/account/profile", label: "بياناتي", sub: "الاسم والجنس وتفضيل الكبتن" },
  { to: "/account/places", label: "الأماكن المحفوظة", sub: "المنزل والعمل وغيرهما" },
  {
    to: "/account/bookings",
    label: "رحلاتي المجدولة",
    sub: "حجوزٌ بمواعيد",
    // **خلف مفتاحه** (12-ط): صفٌّ يفتح شاشةً فارغةً لا سبيلَ لملئها في سوقٍ
    // مطفأٍ يُقرأ عطباً لا ميزةً مغلقة
    scheduled: true,
  },
  {
    to: "/account/referrals",
    label: "ادعُ صديقك",
    sub: "رمزك ومن سجّل به",
    // **بلا مفتاح**: الرمزُ يُعرض والدعواتُ تُسجَّل ولو كان الحافزُ مطفأً —
    // فمن دعا اليومَ يُحفظ أثرُه ليُكافأ يومَ يُحدَّد المبلغ. وما يُخفى هو
    // **المبلغُ** لا الشاشة (قاعدةُ `referrals.attach` لا تسأل عن المفتاح)
  },
  { to: "/account/cards", label: "بطاقاتي", sub: "الدفع بضغطة" },
  { to: "/account/notifications", label: "الإشعارات", sub: "ما وصلك من أخبار رحلاتك" },
  { to: "/account/settings", label: "الإعدادات", sub: "المظهر · إشعارات العروض" },
  // **إغلاقُ الحساب آخرَ القائمة بقصد** (٢٠٢٦-٠٩-٠٧): فعلٌ لا رجعةَ فيه
  // **لا يُجاور «بياناتي»** حيث تقع الإصبعُ وهي تتصفّح. **وظاهرٌ لا مخفيّ**:
  // شرطُ المتجر «an in-app path»، **ومسارٌ يُوصل إليه بالكتابة في العنوان
  // ليس مساراً في التطبيق**.
  {
    to: "/account/close",
    label: "إغلاق الحساب",
    sub: "طلبٌ يراجعه مشرف",
  },
];

export function AccountScreen() {
  const navigate = useNavigate();
  const { user, signOut } = useSession();
  const scheduled = useScheduledRides();
  const rows = ROWS.filter((row) => !row.scheduled || scheduled);

  return (
    <Screen title="حسابي" nav back={false}>
      <div className="mb-18 flex items-center gap-14">
        <div className="flex size-54 items-center justify-center rounded-full border border-brand-brd bg-brand-soft text-18 font-bold text-brand">
          {user?.name.slice(0, 1) ?? "؟"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-17 font-bold text-ink">{user?.name}</p>
          <p dir="ltr" className="truncate text-12 text-muted">
            {user?.phone}
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-16 border border-line bg-surface">
        {rows.map((row, index) => (
          <button
            key={row.to}
            type="button"
            onClick={() => navigate(row.to)}
            className={cn(
              "pressable flex w-full items-center gap-12 px-15 py-14 text-start transition hover:bg-surface-2",
              index === rows.length - 1 ? null : "border-b border-line",
            )}
          >
            <span className="min-w-0 flex-1">
              <span className="block text-13.5 font-semibold text-ink">
                {row.label}
              </span>
              <span className="block truncate text-11 text-muted">{row.sub}</span>
            </span>
            <ChevronLeft className="size-16 shrink-0 text-muted" />
          </button>
        ))}
      </div>

      {/* **التبديلُ في «حسابي» لا في شريطٍ سفليٍّ ولا على الرئيسية** (§23):
          تبديلٌ لا يُضغط يومياً، وموضعُه بين ما يُفتح عن قصد. وهو **آخرُ صفٍّ
          قبل الخروج** لأنه أقربُ ما يكون إليه معنىً: مغادرةُ هذا التطبيق */}
      <SwitchRow />

      <button
        type="button"
        onClick={() => void signOut()}
        className="pressable mt-14 w-full p-10 text-center text-13 font-semibold text-danger"
      >
        تسجيل الخروج
      </button>
    </Screen>
  );
}


/** صفُّ التبديل — **يرسم ما يقدر عليه، ويقول سببَه إن مُنع**. */
function SwitchRow() {
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);

  async function press() {
    setBusy(true);
    setBlocked(null);
    try {
      // `false` تعني **غير مثبَّت** — والصفحةُ تشرح وتعطي رابطَ التنزيل
      if (!(await switchToDriver())) window.location.href = "/account/switch/driver-not-installed";
    } catch (caught) {
      // نصُّ المنع من الخلفية — ولا تُكتب هنا عربيةٌ ثانية (§17)
      // **لا رسالةَ إلا للمنع المعلن** — والفتحُ نفسُه لا يفشل
      setBlocked(blockedReason(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-14 overflow-hidden rounded-16 border border-line bg-surface">
      <button
        type="button"
        disabled={busy}
        onClick={() => void press()}
        className="pressable flex w-full items-center gap-12 px-15 py-14 text-start transition hover:bg-surface-2"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-13.5 font-semibold text-ink">
            تبديل إلى تطبيق السائق
          </span>
          <span className="block truncate text-11 text-muted">
            نفس الحساب — تنتقل جلستك بلا تسجيل دخول
          </span>
        </span>
        <ChevronLeft className="size-16 shrink-0 text-muted" />
      </button>
      {blocked ? (
        <p className="border-t border-line px-15 py-10 text-11.5 leading-note text-warn">
          {blocked}
        </p>
      ) : null}
    </div>
  );
}
