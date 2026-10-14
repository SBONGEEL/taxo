/** **نصوصُ حذف الحساب — بيتٌ واحدٌ لكلِّ ما يقرؤه صاحبُ الحساب** (SPEC §59).
 *
 * **ونسخةٌ حرفيّةٌ في التطبيقين** (`driver-app/src/lib/deletion-text.ts`):
 * الفرقُ بين الراكب والكبتن **مصرَّحٌ بـ`isDriver`** لا بنصّين يفترقان.
 *
 * **والأرقامُ لاتينية، واسمُ المنصّة TAXO باللاتينية** (قرارُ المالك). **ويقول
 * صراحةً إن سجلّاتِ الرحلات والمعاملات المالية تُحفظ لأسبابٍ قانونيةٍ
 * ومحاسبية بعد الحذف** — فلا يَعِد «حذفٌ» بما لا يقع.
 */

export const GRACE_DAYS = 30;

export const DELETION_TEXT = {
  title: tr("حذف الحساب"),
  intro:
    tr("سيُحذف حسابك في TAXO نهائياً بعد {0} يوماً من تأكيد الطلب. ", { 0: GRACE_DAYS }) +
    tr("وحتى ذلك اليوم تستطيع التراجع بتسجيل الدخول واختيار «استعادة الحساب»."),
  erasedTitle: tr("ما يُحذف"),
  erased: (isDriver: boolean) => [
    tr("اسمك ورقم هاتفك وبريدك وصورتك الشخصية"),
    tr("بطاقاتك وأماكنك المحفوظة"),
    tr("أجهزتك المسجّلة وإشعاراتك"),
    ...(isDriver ? [tr("وثائقك المرفوعة وملفاتها")] : []),
  ],
  keptTitle: tr("ما يُحفظ بعد الحذف"),
  kept: [
    tr("سجلات الرحلات والمعاملات المالية تُحفظ لأسباب قانونية ومحاسبية بعد الحذف، بلا اسمك ولا رقمك."),
    tr("وتبقى نسخها الاحتياطية حتى تنقضي مدة حفظها."),
  ],
  graceTitle: tr("خلال المهلة"),
  grace: (isDriver: boolean) => [
    tr("لا تستطيع طلب رحلة، ولا تصلك إشعارات."),
    ...(isDriver
      ? [
          tr("تتوقف طلبات الرحلات فوراً."),
          tr("اسحب رصيدك خلال المهلة — لا يُحذف حسابٌ فيه رصيد."),
          tr("اشتراكك الساري — إن وُجد — لا يُسترد."),
        ]
      : []),
  ],
  next: tr("متابعة"),

  blockedTitle: tr("لا يمكن حذف الحساب الآن"),
  blockers: {
    active_ride: tr("لديك رحلة جارية — أنهِها أولاً."),
    open_dispute: tr("لديك نزاع مفتوح على دفعة لم يُحسم بعد."),
    unpaid_charge: tr("عليك رسم إلغاء مستحق — ادفعه أولاً."),
    unpaid_advance: tr("عليك سلفة غير مسدّدة — سدّدها أولاً."),
  } as Record<string, string>,

  balanceTitle: tr("رصيد محفظتك"),
  balanceIntro: (amount: string) =>
    tr("في محفظتك {0}. الرصيد لا يُسحب، فاختر قبل الحذف:", { 0: amount }),
  transferTitle: tr("حوّله لمستخدم آخر"),
  transferBody: tr("انقل رصيدك إلى حساب آخر في TAXO، ثم عد إلى هذه الشاشة."),
  transferButton: tr("تحويل الرصيد"),
  transferElsewhere: tr("يمكنك تحويله لمستخدم آخر من تطبيق TAXO."),
  forfeitTitle: tr("أوافق على ضياع الرصيد"),
  forfeitLabel: (amount: string) => tr("اكتب المبلغ كما هو للموافقة: {0}", { 0: amount }),
  forfeitHint: tr("بالأرقام اللاتينية، ومنازله العشرية الثلاث."),
  forfeitMismatch: tr("المبلغ لا يطابق رصيدك."),

  confirmTitle: tr("تأكيد الحذف"),
  confirmBody: (date: string) =>
    tr("سيُحذف حسابك في {0}. وتستطيع التراجع قبل ذلك بتسجيل الدخول.", { 0: date }),
  confirmForfeit: (amount: string) => tr("وتوافق على ضياع رصيدك {0}.", { 0: amount }),
  confirmSignOut: tr("وسيُسجَّل خروجك من كل أجهزتك الآن."),
  confirmButton: tr("حذف حسابي"),
  cancelButton: tr("تراجع"),

  restoreTitle: tr("حسابك مجدول للحذف"),
  restoreBody: (date: string) =>
    tr("سيُحذف حسابك نهائياً في {0}. إن غيّرت رأيك فاستعده الآن — يعود كما كان.", { 0: date }),
  restoreDriverBalance: (amount: string) =>
    tr("في محفظتك {0} — اسحبه قبل موعد الحذف، فلا يُحذف حسابٌ فيه رصيد.", { 0: amount }),
  withdrawButton: tr("سحب الرصيد"),
  restoreButton: tr("استعادة الحساب"),
  signOutButton: tr("تسجيل الخروج"),
  deferredTitle: tr("حلّ موعد الحذف ولم يُنفَّذ"),
  deferred: {
    rider_balance_changed:
      tr("تغيّر رصيد محفظتك بعد موافقتك على ضياعه. استعد الحساب ثم اطلب الحذف من جديد."),
    driver_balance: tr("في محفظتك رصيد لم يُسحب. اسحبه ليكتمل الحذف."),
    pending_money: tr("لديك عملية دفع أو شحن أو سحب لم تكتمل بعد."),
    active_ride: tr("لديك رحلة جارية."),
    open_dispute: tr("لديك نزاع مفتوح على دفعة لم يُحسم بعد."),
    unpaid_charge: tr("عليك رسم إلغاء مستحق."),
    unpaid_advance: tr("عليك سلفة غير مسدّدة."),
  } as Record<string, string>,
};

/** يحوّل ما كتبه إلى صيغة الرصيد (`5` ← `5.000`) — **أو `null` إن لم يكن مبلغاً**.
 *
 * **والأرقامُ العربيةُ تُقبل وتُحوَّل**: من كتب بلوحة مفاتيحه لا يُردّ على
 * شكل خانة — **والموافقةُ على المبلغ لا على لوحة المفاتيح**. */
export function normalizeAmount(typed: string): string | null {
  const latin = typed
    .trim()
    .replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[\u06f0-\u06f9]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace("\u066b", ".");
  const match = latin.match(/^(\d+)(?:\.(\d{1,3}))?$/);
  if (!match) return null;
  const whole = String(Number(match[1]));
  return `${whole}.${(match[2] ?? "").padEnd(3, "0")}`;
}
import { tr } from "@/lib/i18n";
