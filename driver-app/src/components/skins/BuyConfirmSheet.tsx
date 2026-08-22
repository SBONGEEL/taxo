/** **ورقةُ تأكيد شراء مركبة** — `design/MONEY-STEPS-CHECKLIST.md` بندٌ ٥.
 *
 * **وضغطةٌ واحدةٌ تُخرج مالاً عطبٌ ولو كان الرقمُ صحيحاً**: بطاقةُ المتجر
 * تفتح ورقةَ المنتج، وورقةُ المنتج تفتح هذه، وهذه وحدَها تدفع. ثلاثُ خطواتٍ
 * لأن ما قبلها **يمكن الرجوعُ عنه** وما بعدها لا — والقرارُ مكتوب: **لا
 * استردادَ بعد الشراء، ولا عند إخفاء المركبة من المتجر لاحقاً**.
 *
 * **ولا يُطرح شيءٌ هنا** (§14، وبندُ ٦ من القائمة): «رصيدك بعد الشراء» يقتضي
 * `Number(balance) - Number(price)` — وهو المالُ يمرّ بعائمٍ بالضبط، وهو ما
 * طبع «٨ د.أ» بجانب «٥٫٠٠٠ د.أ» في تعميم الإحالات. فتُعرض **الثلاثةُ كما
 * وصلت نصّاً**: السعرُ، ورصيدك الآن، ثم **رصيدك بعدها من الدفتر**
 * (`BuySkinOut.balance_after`) بعد أن يقع الخصم.
 *
 * **وتُقفل بالنقر على الظلّ**: من فتحها يعرف ما فيها، والرجوعُ مجّانيٌّ هنا.
 */

import type { Currency, VehicleSkin } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

export function BuyConfirmSheet({
  skin,
  balance,
  currency,
  busy,
  error,
  onConfirm,
  onClose,
}: {
  skin: VehicleSkin;
  /** رصيدُ المحفظة كما وصل من `GET /vehicle-skins/store` — نصّاً لا رقماً. */
  balance: string;
  currency: Currency;
  busy: boolean;
  /** **نصُّ الخلفية كما هو** (§17) — ولا تكتب الشاشةُ عربيّةً لخطأٍ سُمِّي. */
  error: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const label = CURRENCY_LABEL[currency];
  return (
    <div
      className="absolute inset-0 z-50 animate-fadein-fast bg-dim"
      onClick={onClose}
    >
      <div
        className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">
          تأكيد شراء {skin.name}
        </h2>
        <p className="mb-16 text-12 leading-note text-muted">
          يُخصم المبلغ من رصيد محفظتك فوراً، وتصير المركبة في كراجك.
        </p>

        <div className="mb-12 rounded-14 border border-line bg-surface-2 px-14 py-12">
          <div className="flex items-baseline justify-between">
            <span className="text-12.5 text-muted">السعر</span>
            <span className="text-17 font-bold text-ink">
              {digits(skin.price ?? "")}{" "}
              <span className="text-11 font-medium text-muted">{label}</span>
            </span>
          </div>
          <div className="mt-8 flex items-baseline justify-between">
            <span className="text-11.5 text-muted">رصيدك الآن</span>
            <span className="text-12.5 font-semibold text-ink">
              {digits(balance)}{" "}
              <span className="text-10 font-medium text-muted">{label}</span>
            </span>
          </div>
        </div>

        {/* **الجملةُ تُقرأ قبل الدفع لا بعده** (قرارُ المالك): من اشترى ثم
            اختفت المركبةُ من المتجر لا يُستردّ له شيء — وقولُ ذلك بعد الشراء
            تبريرٌ، وقولُه قبله شرطٌ قَبِله بيده */}
        <p className="mb-16 rounded-14 border border-line bg-surface-2 px-14 py-11 text-11.5 leading-note text-warn">
          لا استرداد بعد الشراء. وإن أُخفيت المركبة من المتجر لاحقاً فهي تبقى
          في كراجك، ولا يُستردّ ثمنها.
        </p>

        <ErrorNote message={error} />

        <div className="mt-10 flex flex-col gap-9">
          <Button size="md" loading={busy} onClick={onConfirm}>
            خصم من المحفظة
          </Button>
          <button
            type="button"
            onClick={onClose}
            className="pressable w-full py-8 text-center text-12.5 font-semibold text-muted"
          >
            تراجع
          </button>
        </div>
      </div>
    </div>
  );
}
