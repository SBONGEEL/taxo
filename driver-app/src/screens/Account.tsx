/** حسابي — SPEC القسم 12، وشكلُه من `DESIGN.md` §5.3.
 *
 * صفحةُ عبورٍ لا صفحةُ تحرير: ما يملك الكبتن تغييرَه من ملفه حقلٌ واحد
 * (`cliq_alias` عبر `PATCH /drivers/me`)، ومكانُه الإعدادات مع بقية ما
 * يُحفظ. أما اسمُه ورقمُه فلا منفذَ لتعديلهما — ورقمُه بالذات **هوية الدخول
 * وقد أُثبتت مرةً** (`users.phone_verified_at`)، فتغييرُه من شاشةٍ بلا إعادة
 * إثبات بابٌ لسرقة حساب. فيُعرضان ولا يُحرَّران.
 *
 * ولا مبدّلَ لغةٍ في الرأس: التطبيق عربيٌّ وحده (`DESIGN-DECISIONS` بند 18).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

import { getMySubscription } from "@/api/endpoints";
import type { DriverStatus, MySubscription } from "@/api/types";
import { BottomNav } from "@/components/BottomNav";
import { Spinner } from "@/components/ui/Feedback";
import { useCountryConfig, useFeature } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { forDisplay } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

/** والنوعُ `DriverStatus` لا `string`: حالٌ جديدةٌ في الخلفية تكسر البناء
 * هنا بدل أن تخرج على الشاشة سطراً فارغاً. */
const STATUS_LINE: Record<DriverStatus, { text: string; dot: string }> = {
  approved: { text: "حساب معتمد", dot: "bg-ok" },
  pending: { text: "قيد المراجعة — لا تصلك طلبات بعد", dot: "bg-warn" },
  rejected: { text: "طلبك مرفوض — راجع الدعم", dot: "bg-danger" },
  suspended: { text: "حسابك موقوف — راجع الدعم", dot: "bg-danger" },
};

export function AccountScreen() {
  const navigate = useNavigate();
  const { profile } = useDriver();
  const { signOut } = useSession();
  const country = useCountryConfig(profile?.user.country_code);
  const womenService = useFeature(
    profile?.user.country_code,
    "women_service_enabled",
  );
  // **الصفُّ خلف مفتاحه** (12-ح): قسمٌ يعرض رمزاً في سوقٍ لا حافزَ فيه يَعِد
  // بما لا وجودَ له. والإحالاتُ تُسجَّل على كل حال — ما يُخفى هو العرض
  const referralsOn = useFeature(
    profile?.user.country_code,
    "driver_referrals_enabled",
  );
  const [subscription, setSubscription] = useState<MySubscription | null>(null);

  useEffect(() => {
    getMySubscription()
      .then(setSubscription)
      .catch(() => setSubscription(null));
  }, []);

  if (!profile) {
    return (
      <div className="flex h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  const { driver, user, vehicles, documents } = profile;
  const status = STATUS_LINE[driver.status];
  const vehicle = vehicles[0];

  // سطرُ الاشتراك ولونُ شريطه — نفس الحالات الأربع في شاشة الاشتراك
  const subLine = !subscription
    ? "…"
    : subscription.is_active
      ? `ساري · باقٍ ${arabicDigits(String(subscription.days_remaining))} يوماً`
      : subscription.coverage_until
        ? "منتهٍ — جدّد للعودة للتوزيع"
        : "لا اشتراك — اشترك للبدء";
  const subTone = !subscription?.is_active
    ? "bg-danger"
    : subscription.days_remaining <= 1
      ? "bg-warn"
      : "bg-ok";

  // ولا يُقال «كل المستندات مقبولة» من حال الكبتن: من اعتُمد ثم رُفض مستندٌ
  // حدّثه يقرأ جملةً تكذّبها شاشةُ المستندات نفسها. والمرفوضُ ليس «بانتظار
  // المراجعة» — هو بانتظار **الكبتن**
  const rejectedDocs = documents.filter(
    (document) => document.review_status === "rejected",
  ).length;
  const pendingDocs = documents.filter(
    (document) => document.review_status === "pending",
  ).length;
  const docsNote =
    rejectedDocs > 0
      ? `${arabicDigits(String(rejectedDocs))} مستند مرفوض — يحتاج رفعاً جديداً`
      : pendingDocs > 0
        ? `${arabicDigits(String(pendingDocs))} مستند قيد المراجعة`
        : "كل المستندات مقبولة";

  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <div className="mb-16 mt-6 flex items-center gap-14">
          <div className="flex size-54 items-center justify-center rounded-full border border-line bg-surface-2 text-18 font-bold text-ink">
            {user.name.trim().slice(0, 1)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-17 font-bold text-ink">
              {user.name}
            </div>
            <div className="text-12 text-muted">
              {/* الرقم كما هو: معرّفٌ يُقارَن ويُملى، لا كمّيةٌ تُقرأ — نفس
                  قاعدة `Cards.tsx` و`Vehicle.tsx` (`CLAUDE.md`) */}
              <span dir="ltr">
                {country
                  ? forDisplay(user.phone, country.dial_code)
                  : user.phone}
              </span>{" "}
              · ★ {arabicDigits(driver.rating_avg)}
            </div>
          </div>
        </div>

        <div className="mb-12 flex items-center gap-8 rounded-12 border border-line bg-surface px-13 py-10">
          <span className={cn("block size-8 rounded-full", status.dot)} />
          <span className="text-12 text-muted">
            {status.text} · {docsNote}
          </span>
        </div>

        {/* توثيقُ الجنس (المرحلة 10-ج): تقرؤه الكبتنة لتعرف أنه **مثبَّتٌ من
            الإدارة عن هويتها** ومتى — لا حقلٌ نسيت ملأه. وقبل التثبيت لا
            تصلها الطلبات المجنّسة أصلاً، وقولُ ذلك هنا يمنع سؤال «لماذا لا
            تصلني طلبات النساء». ولا يُعدَّل من التطبيق */}
        {womenService ? (
          <div className="mb-10 rounded-16 border border-brand-brd bg-surface p-15">
            <div className="flex items-center justify-between gap-10">
              <span className="text-13.5 font-bold text-ink">الجنس</span>
              <span className="text-13 font-bold text-brand">
                {user.gender === "female"
                  ? "أنثى"
                  : user.gender === "male"
                    ? "ذكر"
                    : "غير مثبَّت"}
              </span>
            </div>
            <p className="mt-8 text-11.5 leading-note text-muted">
              {user.gender_verified_at
                ? `موثّق من الهوية بواسطة الإدارة · ${new Date(
                    user.gender_verified_at,
                  ).toLocaleDateString("ar-EG", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}`
                : "قبل التثبيت لا تصلك الطلبات التي تحدّد جنساً — لا كطلباتٍ مرفوضة، بل لا تُعرض أصلاً."}
            </p>
            <p className="mt-6 text-11.5 leading-note text-muted">
              لا يُعدَّل من التطبيق. للتصحيح راسل الدعم.
            </p>
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => navigate("/subscription")}
          className="pressable mb-10 flex w-full items-center gap-12 rounded-16 border border-line bg-surface p-15 text-start"
        >
          <span className={cn("block h-38 w-6 rounded-4", subTone)} />
          <span className="flex-1">
            <span className="block text-13.5 font-bold text-ink">الاشتراك</span>
            <span className="block text-11.5 text-muted">{subLine}</span>
          </span>
          <ChevronLeft size={16} className="text-muted" />
        </button>

        <div className="overflow-hidden rounded-16 border border-line bg-surface">
          <Row
            label="المركبة والمستندات"
            sub={
              vehicle
                ? `${vehicle.make} ${vehicle.model}`
                : "لم تُسجّل مركبة بعد"
            }
            onClick={() => navigate("/account/vehicle")}
          />
          <Row
            label="البطاقات المحفوظة"
            sub="بطاقاتُ الدفع التي حفظتَها"
            onClick={() => navigate("/account/cards")}
          />
          {referralsOn ? (
            <Row
              label="أَحِلْ سائقة"
              sub="رمزك ومن سجّل به"
              onClick={() => navigate("/account/referrals")}
            />
          ) : null}
          <Row
            label="الإعدادات"
            sub="الإشعارات · المظهر · alias كليك"
            onClick={() => navigate("/account/settings")}
            last
          />
        </div>

        <button
          type="button"
          onClick={() => void signOut()}
          className="pressable mt-14 w-full p-10 text-center text-13 font-semibold text-danger"
        >
          تسجيل الخروج
        </button>
      </div>

      <BottomNav />
    </div>
  );
}

function Row({
  label,
  sub,
  onClick,
  last = false,
}: {
  label: string;
  sub: string;
  onClick: () => void;
  last?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "pressable flex w-full items-center gap-12 px-15 py-14 text-start",
        last ? "" : "border-b border-line",
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="block text-13.5 font-semibold text-ink">{label}</span>
        <span className="block truncate text-11 text-muted">{sub}</span>
      </span>
      <ChevronLeft size={16} className="shrink-0 text-muted" />
    </button>
  );
}
