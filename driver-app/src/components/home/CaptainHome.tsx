/** **الشاشة الرئيسة للكبتن — من ملفّ التصميم `home Captain`.**
 *
 * **وصفحةٌ تُمرَّر لا خريطةٌ ملءَ الشاشة**: الخريطةُ بطاقةُ ١٧٠ في أعلاها،
 * وتحتها الأرقامُ والبلاطاتُ واللافتةُ والاشتراكُ والمركبة.
 *
 * ## وثلاثةٌ تبقى رغم أنّ التصميم لا يرسمها (قرارُ المالك 2026-08-30)
 *
 * 1. **تفضيلُ جنس الركّاب** — قرارٌ مسجَّلٌ بعلّته: من ضيّق من يُقلّهم يرى
 *    طلباتٍ أقلّ، **وسببُ القلّة يجب أن يكون أمام عينه** لا في شاشةٍ يفتحها
 *    بحثاً عن عطل.
 * 2. **إشعارُ الإذن المرفوض** — شرطُ المالك 2026-08-21.
 * 3. **مبدّلُ السِمة** — ميزةٌ حيّة، **ولا يُنزع رسمٌ لا يذكره**.
 *
 * ## والأرقامُ من السوق الحيّ لا من الرسم (قرارُ المالك)
 *
 * التصميمُ ليبيٌّ بالكامل (`د.ل` · طرابلس · «حتى 50 د.ل») **وليبيا مغلقة**.
 * **فالعملةُ والمبالغُ من `GET /drivers/me/earnings?period=today`** — وهو
 * يحسب **بيوم الدولة** (`stats._zone` + `_window`)، **ولا حسابَ ثانياً**.
 *
 * ## والعمولةُ **نسبةٌ مقروءةٌ لا مبلغٌ ولا رقمٌ مرسوم**
 *
 * التصميمُ يكتب «عمولة TAXO ‎0%». **ورقمٌ مخبوزٌ في شاشة مالٍ يمنعه §14.**
 * **و`earnings.commission` مبلغٌ اقتُطع لا نسبة** — وهما شيئان، ولا يُعرض
 * أحدُهما مكان الآخر. **والنسبةُ نسبتُه هو**: `commission_percent` على حسابه
 * مجمَّدةٌ على وعد اشتراكه — فمن اشترى على صفرٍ يرى صفراً ولو رفع السوقُ إلى
 * خمسة. **وهذا تطبيقُ قاعدة الوعد لا اجتهادٌ جديد.**
 */

import { Bell, ChevronLeft, Crown, Moon, Star, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import type { Earnings, PromoBanner, ServiceTile } from "@/api/types";
import { MapCard } from "@/components/home/MapCard";
import { PromoBanners } from "@/components/home/PromoBanners";
import { ServiceTiles } from "@/components/home/ServiceTiles";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

interface Props {
  name: string;
  rating: string | null;
  level: number | null;
  online: boolean;
  unread: number;
  dark: boolean;
  onToggleTheme: () => void;
  onToggleOnline: () => void;
  goLabel: string;
  goDisabled: boolean;
  /** `null` ما دامت لم تصل — **ولا يُرسم صفرٌ مكانَ «لم يُعرف بعد»**. */
  earnings: Earnings | null;
  /** **نسبةُ الكبتن السارية** — مقروءةٌ لا مرسومة. */
  commissionPercent: string | null;
  tiles: ServiceTile[];
  banners: PromoBanner[];
  /** الخريطةُ بطاقةً — تُمرَّر كما هي فلا تُبنى مرّتين. */
  map: ReactNode;
  /** **شارةُ «بانتظار الطلبات…» تحت البطاقة مباشرةً** — لا في ذيل الصفحة.
   *
   *  **وموضعُها جزءٌ من صدقها**: من رفع مفتاحَه ينظر إلى الزرِّ الذي ضغطه،
   *  **وخبرٌ عن حاله في آخر صفحةٍ تُمرَّر خبرٌ لا يصله**. */
  statusPill: ReactNode;
  /** ما يبقى رغم أن التصميم لا يرسمه. */
  extras: ReactNode;
  subscriptionLine: string | null;
  vehicleLine: string | null;
  vehicleNote: string | null;
}

export function CaptainHome({
  name,
  rating,
  level,
  online,
  unread,
  dark,
  onToggleTheme,
  onToggleOnline,
  goLabel,
  goDisabled,
  earnings,
  commissionPercent,
  tiles,
  banners,
  map,
  statusPill,
  extras,
  subscriptionLine,
  vehicleLine,
  vehicleNote,
}: Props) {
  const navigate = useNavigate();
  const currency = earnings ? CURRENCY_LABEL[earnings.currency] : "";

  return (
    <div className="scr absolute inset-0 bottom-0 overflow-y-auto px-16 pb-18 pt-2">
      {/* ── الرأس: التحيّةُ والتقييمُ والمستوى · مفتاحُ الاتصال · الجرس */}
      <div className="mb-12 flex items-center justify-between gap-8">
        <div className="flex min-w-0 items-center gap-10">
          <div className="flex size-38 shrink-0 items-center justify-center rounded-full border border-brand-brd bg-brand-soft text-15 font-bold text-ink">
            {name.slice(0, 1)}
          </div>
          <div className="min-w-0">
            <div className="text-14 font-semibold text-ink">{name}</div>
            <div className="flex items-center gap-5 text-11.5 text-muted">
              <Star className="size-12 text-warn" />
              {rating ? digits(rating) : "—"}
              {level !== null ? ` · المستوى ${digits(String(level))}` : null}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-7">
          {/* **مفتاحُ الاتصال في الرأس** كما في التصميم */}
          <button
            type="button"
            onClick={onToggleOnline}
            className="pressable flex items-center gap-8 rounded-full border border-line bg-surface py-6 pe-8 ps-11 text-12 font-semibold"
          >
            <span className={online ? "text-ink" : "text-muted"}>
              {online ? "متصل" : "غير متصل"}
            </span>
            <span
              className={`relative block h-16 w-28 rounded-full ${
                online ? "bg-ok" : "bg-line"
              }`}
            >
              <span
                className={`absolute top-2 block size-12 rounded-full ${
                  online ? "start-2 bg-surface" : "end-2 bg-muted"
                }`}
              />
            </span>
          </button>
          <button
            type="button"
            onClick={() => navigate("/notifications")}
            aria-label="الإشعارات"
            className="ctl relative size-33"
          >
            <Bell className="size-17" />
            {unread > 0 ? (
              <span className="absolute end-6 top-5 block size-7 rounded-full bg-danger" />
            ) : null}
          </button>
          {/* **مبدّلُ السِمة يبقى** — ميزةٌ حيّةٌ لا يذكرها الرسم */}
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label="تبديل المظهر"
            className="ctl size-33"
          >
            {dark ? <Sun className="size-16" /> : <Moon className="size-16" />}
          </button>
        </div>
      </div>

      {/* ── الخريطةُ بطاقةً تتوسّع، وفي قاعها زرُّ الاستقبال في الحالين */}
      <MapCard
        action={
          <button
            type="button"
            onClick={onToggleOnline}
            disabled={goDisabled}
            className="pressable w-full rounded-13 bg-brand p-13 text-center text-14.5 font-bold text-brand-ink disabled:opacity-50"
          >
            {goLabel}
          </button>
        }
        // **حالُه مقروءةٌ وهي موسَّعة** — وفي البطاقة يقرؤها من مفتاح الرأس
        expandedStatus={
          <span className="flex items-center gap-7 rounded-full border border-line bg-surface px-12 py-7 text-12 font-semibold">
            <span
              className={`block size-8 rounded-full ${online ? "bg-ok" : "bg-muted"}`}
            />
            <span className={online ? "text-ink" : "text-muted"}>
              {online ? "متصل — تستقبل الطلبات" : "غير متصل"}
            </span>
          </span>
        }
      >
        {map}
      </MapCard>

      {statusPill}

      {/* ── ثلاثةُ أرقام — **ولا يُرسم صفرٌ مكانَ «لم يُعرف بعد»** */}
      <div className="mb-12 grid grid-cols-3 gap-8">
        <Stat
          value={earnings ? digits(String(earnings.completed_rides)) : "—"}
          label="رحلات اليوم"
        />
        <Stat
          value={earnings ? digits(earnings.net) : "—"}
          label={currency ? `صافي (${currency})` : "صافي"}
        />
        {/* **نسبةٌ مقروءةٌ لا مبلغٌ ولا رقمٌ مرسوم** — §14 */}
        <Stat
          value={commissionPercent ? `${digits(commissionPercent)}٪` : "—"}
          label="عمولة TAXO"
          tone={commissionPercent === "0" ? "ok" : undefined}
        />
      </div>

      <ServiceTiles tiles={tiles} />
      <PromoBanners banners={banners} />

      {/* ── ما يبقى رغم أن التصميم لا يرسمه */}
      {extras}

      {subscriptionLine ? (
        <button
          type="button"
          onClick={() => navigate("/subscription")}
          className="pressable mb-8 flex w-full items-center gap-10 rounded-14 border border-line bg-surface px-13 py-12 text-start"
        >
          <Crown className="size-19 shrink-0 text-warn" />
          <span className="min-w-0 flex-1 text-12.5 font-medium text-ink">
            {subscriptionLine}
          </span>
          <span className="text-11.5 font-bold text-ink">جدّد</span>
        </button>
      ) : null}

      {vehicleLine ? (
        <button
          type="button"
          onClick={() => navigate("/account/vehicle")}
          className="pressable flex w-full items-center gap-12 rounded-14 border border-line bg-surface px-13 py-12 text-start"
        >
          <div className="min-w-0 flex-1">
            <div className="text-13 font-semibold text-ink">{vehicleLine}</div>
            {vehicleNote ? (
              <div className="mt-2 text-11 text-muted">{vehicleNote}</div>
            ) : null}
          </div>
          <ChevronLeft className="size-17 shrink-0 text-muted" />
        </button>
      ) : null}
    </div>
  );
}

function Stat({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone?: "ok";
}) {
  return (
    <div className="rounded-12 border border-line bg-surface px-8 py-10 text-center">
      <div
        className={`text-18 font-bold ${tone === "ok" ? "text-ok" : "text-ink"}`}
      >
        {value}
      </div>
      <div className="mt-2 text-10.5 text-muted">{label}</div>
    </div>
  );
}
