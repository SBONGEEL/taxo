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
import type { MySubscription } from "@/api/types";
import { BottomNav } from "@/components/BottomNav";
import { Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { forDisplay } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

const STATUS_LINE: Record<string, { text: string; dot: string }> = {
  approved: { text: "حساب معتمد · كل المستندات مقبولة", dot: "bg-ok" },
  pending: { text: "قيد المراجعة — لا تصلك طلبات بعد", dot: "bg-warn" },
  rejected: { text: "طلبك مرفوض — راجع الدعم", dot: "bg-danger" },
  suspended: { text: "حسابك موقوف — راجع الدعم", dot: "bg-danger" },
};

export function AccountScreen() {
  const navigate = useNavigate();
  const { profile } = useDriver();
  const { signOut } = useSession();
  const country = useCountryConfig(profile?.user.country_code);
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
  const status = STATUS_LINE[driver.status] ?? STATUS_LINE.pending;
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

  const pendingDocs = documents.filter(
    (document) => document.review_status !== "approved",
  ).length;

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
              <span dir="ltr">
                {arabicDigits(
                  country
                    ? forDisplay(user.phone, country.dial_code)
                    : user.phone,
                )}
              </span>{" "}
              · ★ {arabicDigits(driver.rating_avg)}
            </div>
          </div>
        </div>

        <div className="mb-12 flex items-center gap-8 rounded-12 border border-line bg-surface px-13 py-10">
          <span className={cn("block size-8 rounded-full", status.dot)} />
          <span className="text-12 text-muted">{status.text}</span>
        </div>

        <button
          type="button"
          onClick={() => navigate("/subscription")}
          className="mb-10 flex w-full items-center gap-12 rounded-16 border border-line bg-surface p-15 text-start"
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
                ? `${vehicle.make} ${vehicle.model}${pendingDocs > 0 ? ` · ${arabicDigits(String(pendingDocs))} مستند بانتظار المراجعة` : ""}`
                : "لم تُسجّل مركبة بعد"
            }
            onClick={() => navigate("/account/vehicle")}
          />
          <Row
            label="البطاقات المحفوظة"
            sub="بطاقاتُ الدفع التي حفظتَها"
            onClick={() => navigate("/account/cards")}
          />
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
          className="mt-14 w-full p-10 text-center text-13 font-semibold text-danger"
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
        "flex w-full items-center gap-12 px-15 py-14 text-start",
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
