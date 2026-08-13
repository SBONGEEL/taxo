import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// prettier-ignore
const FONT_SIZES = [
  "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "13.5",
  "14", "14.5", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
  "25", "26", "30", "32", "34", "38", "44",
];

const twMerge = extendTailwindMerge({
  override: { classGroups: { "font-size": [{ text: FONT_SIZES }] } },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const CURRENCY_LABEL: Record<string, string> = { JOD: "د.أ", LYD: "د.ل" };

/** تسميةُ العملة للعرض — **لا يُعرض الرمزُ الخام في واجهةٍ عربية**.
 *
 * كان حقلُ مبلغ الشحن يعرض `JOD` لاحقةً بينما كلُّ سطرِ مالٍ آخر يعرض «د.أ»
 * (دَينٌ مسجَّلٌ في `CLAUDE.md`)، ثم استنسختُه في ورقة الشحن الجديدة — فصار
 * البيتُ الواحد للتسمية هو الإصلاح: `formatMoney` يقرؤه، وكذلك أيُّ لاحقةِ حقل.
 */
export function currencyLabel(currency: string | null | undefined): string {
  return currency ? (CURRENCY_LABEL[currency] ?? currency) : "";
}

const CURRENCY_NAME: Record<string, string> = {
  JOD: "دينار أردني",
  LYD: "دينار ليبي",
};

/** اسمُ العملة كاملاً — لسطرٍ واحدٍ تحت المبلغ الكبير في طبقة الدفع
 *  (`t.jodFull` في تصميم الراكب). ويسكن هنا لا في الشاشة، لأن تسميةَ العملة
 *  دَينٌ أُغلق مرةً بجعلها بيتاً واحداً؛ وبيتان لها يفترقان كما افترقا. */
export function currencyName(currency: string | null | undefined): string {
  return currency ? (CURRENCY_NAME[currency] ?? currency) : "";
}

/** المبالغ نصوصٌ من الخلفية ولا تُحوَّل إلى `number` (SPEC القسم 4).
 *
 * `Intl.NumberFormat` يأخذ رقماً فيمرّ المال بالفاصلة العائمة ولو للعرض —
 * فالتنسيق هنا نصّيٌّ بحت: ثلاث خانات كسرية دائماً، وفاصلة كل ثلاث خانات
 * صحيحة. الرقم يبقى كما حسبته الخلفية حرفاً بحرف.
 */
export function formatMoney(amount: string | null | undefined, currency?: string) {
  if (amount === null || amount === undefined || amount === "") return "—";

  const negative = amount.trimStart().startsWith("-");
  const [whole = "0", fraction = ""] = amount.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const padded = (fraction + "000").slice(0, 3);
  const label = currency ? ` ${CURRENCY_LABEL[currency] ?? currency}` : "";
  return `${negative ? "−" : ""}${grouped}.${padded}${label}`;
}

/** مسافة للعرض: بالأمتار تحت الكيلومتر، وبكسرٍ واحد فوقه. */
export function formatDistance(km: string | number | null | undefined) {
  if (km === null || km === undefined || km === "") return "—";
  const value = Number(km);
  if (!Number.isFinite(value)) return "—";
  return value < 1 ? `${Math.round(value * 1000)} م` : `${value.toFixed(1)} كم`;
}

export function formatDuration(minutes: string | number | null | undefined) {
  if (minutes === null || minutes === undefined || minutes === "") return "—";
  const value = Math.round(Number(minutes));
  if (!Number.isFinite(value)) return "—";
  if (value < 60) return `${value} دقيقة`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  return rest ? `${hours} س ${rest} د` : `${hours} ساعة`;
}

const DATE_FORMAT = new Intl.DateTimeFormat("ar", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatDateTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return DATE_FORMAT.format(new Date(iso));
}

export function formatTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("ar", { timeStyle: "short" }).format(new Date(iso));
}

/** مفتاح عدم تكرار للدفع والتحويل (SPEC القسم 14) — يُولَّد مرةً ويُعاد
 * استعماله في كل محاولةٍ لنفس العملية، فضغطتان لا تدفعان مرتين. */
export function newIdempotencyKey(prefix: string) {
  const random =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`.slice(0, 64);
}

export function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
