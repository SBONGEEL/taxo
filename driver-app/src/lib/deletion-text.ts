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
  title: "حذف الحساب",
  intro:
    `سيُحذف حسابك في TAXO نهائياً بعد ${GRACE_DAYS} يوماً من تأكيد الطلب. ` +
    "وحتى ذلك اليوم تستطيع التراجع بتسجيل الدخول واختيار «استعادة الحساب».",
  erasedTitle: "ما يُحذف",
  erased: (isDriver: boolean) => [
    "اسمك ورقم هاتفك وبريدك وصورتك الشخصية",
    "بطاقاتك وأماكنك المحفوظة",
    "أجهزتك المسجّلة وإشعاراتك",
    ...(isDriver ? ["وثائقك المرفوعة وملفاتها"] : []),
  ],
  keptTitle: "ما يُحفظ بعد الحذف",
  kept: [
    "سجلات الرحلات والمعاملات المالية تُحفظ لأسباب قانونية ومحاسبية بعد الحذف، بلا اسمك ولا رقمك.",
    "وتبقى نسخها الاحتياطية حتى تنقضي مدة حفظها.",
  ],
  graceTitle: "خلال المهلة",
  grace: (isDriver: boolean) => [
    "لا تستطيع طلب رحلة، ولا تصلك إشعارات.",
    ...(isDriver
      ? [
          "تتوقف طلبات الرحلات فوراً.",
          "اسحب رصيدك خلال المهلة — لا يُحذف حسابٌ فيه رصيد.",
          "اشتراكك الساري — إن وُجد — لا يُسترد.",
        ]
      : []),
  ],
  next: "متابعة",

  blockedTitle: "لا يمكن حذف الحساب الآن",
  blockers: {
    active_ride: "لديك رحلة جارية — أنهِها أولاً.",
    open_dispute: "لديك نزاع مفتوح على دفعة لم يُحسم بعد.",
    unpaid_charge: "عليك رسم إلغاء مستحق — ادفعه أولاً.",
    unpaid_advance: "عليك سلفة غير مسدّدة — سدّدها أولاً.",
  } as Record<string, string>,

  balanceTitle: "رصيد محفظتك",
  balanceIntro: (amount: string) =>
    `في محفظتك ${amount}. الرصيد لا يُسحب، فاختر قبل الحذف:`,
  transferTitle: "حوّله لمستخدم آخر",
  transferBody: "انقل رصيدك إلى حساب آخر في TAXO، ثم عد إلى هذه الشاشة.",
  transferButton: "تحويل الرصيد",
  transferElsewhere: "يمكنك تحويله لمستخدم آخر من تطبيق TAXO.",
  forfeitTitle: "أوافق على ضياع الرصيد",
  forfeitLabel: (amount: string) => `اكتب المبلغ كما هو للموافقة: ${amount}`,
  forfeitHint: "بالأرقام اللاتينية، ومنازله العشرية الثلاث.",
  forfeitMismatch: "المبلغ لا يطابق رصيدك.",

  confirmTitle: "تأكيد الحذف",
  confirmBody: (date: string) =>
    `سيُحذف حسابك في ${date}. وتستطيع التراجع قبل ذلك بتسجيل الدخول.`,
  confirmForfeit: (amount: string) => `وتوافق على ضياع رصيدك ${amount}.`,
  confirmSignOut: "وسيُسجَّل خروجك من كل أجهزتك الآن.",
  confirmButton: "حذف حسابي",
  cancelButton: "تراجع",

  restoreTitle: "حسابك مجدول للحذف",
  restoreBody: (date: string) =>
    `سيُحذف حسابك نهائياً في ${date}. إن غيّرت رأيك فاستعده الآن — يعود كما كان.`,
  restoreDriverBalance: (amount: string) =>
    `في محفظتك ${amount} — اسحبه قبل موعد الحذف، فلا يُحذف حسابٌ فيه رصيد.`,
  withdrawButton: "سحب الرصيد",
  restoreButton: "استعادة الحساب",
  signOutButton: "تسجيل الخروج",
  deferredTitle: "حلّ موعد الحذف ولم يُنفَّذ",
  deferred: {
    rider_balance_changed:
      "تغيّر رصيد محفظتك بعد موافقتك على ضياعه. استعد الحساب ثم اطلب الحذف من جديد.",
    driver_balance: "في محفظتك رصيد لم يُسحب. اسحبه ليكتمل الحذف.",
    pending_money: "لديك عملية دفع أو شحن أو سحب لم تكتمل بعد.",
    active_ride: "لديك رحلة جارية.",
    open_dispute: "لديك نزاع مفتوح على دفعة لم يُحسم بعد.",
    unpaid_charge: "عليك رسم إلغاء مستحق.",
    unpaid_advance: "عليك سلفة غير مسدّدة.",
  } as Record<string, string>,
} as const;

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
