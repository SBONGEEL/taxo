/** الهوية الصوتية — `DESIGN.md` §9. موتيفٌ واحد تتفرّع منه كلُّ النغمات.
 *
 * **مولَّدةٌ برمجياً لا ملفات**: الجدولُ أدناه ~٢ كيلوبايت مقابل ~٦٠ من الأصول،
 * **ولا شبكةَ فلا تأخيرَ لأول رسم** — وكلُّها مشتقّةٌ من `MOTIF` الواحد، وهو ما
 * يجعلها هويةً لا خمسةَ عشرَ ملفاً لا يجمعها شيء.
 *
 * **والسياقُ يُنشأ عند أول تشغيلٍ لا عند التحميل**: `AudioContext` مورِدٌ ثقيل،
 * وإنشاؤه في وحدةٍ تُستورد مع التطبيق يوقظ عتادَ الصوت لمن لن يسمع شيئاً.
 *
 * **والمتصفحاتُ تمنع الصوتَ قبل إيماءة**: `unlock()` تُنادى من أول لمسةٍ في
 * التطبيق، وقبلها كلُّ `play` تصمت بلا خطأ. ولذلك نُقل توقيعُ الشاشة الترحيبية
 * إلى **أول لمسةٍ بعد الدخول** (قرارُ المالك §9.2): نغمةٌ لا تُسمع في أول فتحةٍ
 * هي الفتحةُ التي يُبنى فيها الانطباعُ الأول.
 *
 * **وما لا نملكه لا نَعِد به**: صوتُ الويب على iOS يمرّ بقناة الوسائط، ومفتاحُ
 * الصامت لا يوقفه دائماً. لا حيلةَ في المنصة تتجاوز ذلك — فيُذكر في `README`
 * ويبقى مفتاحُ التطبيق هو ما يملكه المستخدم فعلاً.
 */

/** مفاتيحُ التخزين — **على الجهاز لا الحساب** كالسِمة: من يُسكت تطبيقه في
 *  اجتماعٍ لا يريد إسكاته على هاتفه في البيت. */
const KEY = "taxo.sound";
const KEY_NOTIFICATIONS = "taxo.sound.notifications";

/** الموتيف: `A4 → D5 → E5` — رابعةٌ تامّة صاعدة ثم درجةٌ كاملة (§9). */
const A4 = 440;
const D5 = 587.33;
const E5 = 659.25;
const A5 = 880;
const D6 = 1174.66;

interface Note {
  /** التردد بالهرتز — من سلّم §9 لا رقمٌ يُكتب في موضع الاستعمال. */
  hz: number;
  /** بدايتُها من أول النغمة بالثواني. */
  at: number;
  /** طولُها بالثواني. */
  for: number;
  /** شدّتُها — الخطأُ بثلث الشدة عمداً (§9.1). */
  gain?: number;
}

export type Cue =
  | "request"
  | "accepted"
  | "arrived"
  | "started"
  | "paid"
  | "topup"
  | "error"
  | "notify"
  | "signature";

/** كلُّ نغمةٍ اشتقاقٌ من الموتيف — والجدولُ هو الهوية (§9.1). */
const CUES: Record<Cue, Note[]> = {
  // تأكيدُ الطلب — أوّلُ نغمتين
  request: [
    { hz: A4, at: 0, for: 0.16 },
    { hz: D5, at: 0.12, for: 0.16 },
  ],
  // **قبولُ كبتن — الأهم**: الموتيف كاملاً صاعداً
  accepted: [
    { hz: A4, at: 0, for: 0.18 },
    { hz: D5, at: 0.14, for: 0.18 },
    { hz: E5, at: 0.28, for: 0.22 },
  ],
  arrived: [
    { hz: D5, at: 0, for: 0.16 },
    { hz: E5, at: 0.12, for: 0.16 },
    { hz: A5, at: 0.24, for: 0.18 },
  ],
  started: [
    { hz: D5, at: 0, for: 0.16 },
    { hz: A5, at: 0.13, for: 0.18 },
  ],
  paid: [
    { hz: A4, at: 0, for: 0.16 },
    { hz: D5, at: 0.13, for: 0.16 },
    { hz: E5, at: 0.26, for: 0.16 },
    { hz: D6, at: 0.34, for: 0.2 },
  ],
  topup: [
    { hz: A5, at: 0, for: 0.14 },
    { hz: D6, at: 0.12, for: 0.18 },
  ],
  // **الخطأُ ليس صوتاً منفّراً**: الموتيف منعكساً، نغمتان، بثلث الشدة
  error: [
    { hz: E5, at: 0, for: 0.18, gain: 0.34 },
    { hz: A4, at: 0.15, for: 0.2, gain: 0.34 },
  ],
  notify: [{ hz: D5, at: 0, for: 0.2 }],
  // توقيعُ العلامة — الموتيف مهلاً، وهو أوّلُ ما يُسمع
  signature: [
    { hz: A4, at: 0, for: 0.26 },
    { hz: D5, at: 0.17, for: 0.26 },
    { hz: E5, at: 0.34, for: 0.34 },
  ],
};

/** النغماتُ التي يحكمها مفتاحُ الإشعارات لا المفتاحُ العام. */
const NOTIFICATION_CUES: ReadonlySet<Cue> = new Set<Cue>(["notify"]);

function enabled(key: string): boolean {
  try {
    // الغيابُ يعني **مفعّلاً**: الصوتُ ميزةٌ افتراضية يُطفئها صاحبُها، لا ميزةٌ
    // تنتظر إشعالاً — وهذا عكسُ قاعدة `feature_flags` لأن لا مالَ هنا ولا حارس
    return localStorage.getItem(key) !== "off";
  } catch {
    return true;
  }
}

export function soundsEnabled(): boolean {
  return enabled(KEY);
}

export function notificationSoundEnabled(): boolean {
  return enabled(KEY_NOTIFICATIONS);
}

export function setSoundsEnabled(on: boolean): void {
  localStorage.setItem(KEY, on ? "on" : "off");
}

export function setNotificationSoundEnabled(on: boolean): void {
  localStorage.setItem(KEY_NOTIFICATIONS, on ? "on" : "off");
}

let context: AudioContext | null = null;
let unlocked = false;

/** يُنادى من أول إيماءةٍ في التطبيق — وبدونها كلُّ تشغيلٍ يصمت بلا خطأ. */
export function unlock(): void {
  if (unlocked) return;
  try {
    context ??= new AudioContext();
    void context.resume();
    unlocked = context.state === "running";
  } catch {
    unlocked = false;
  }
}

export function isUnlocked(): boolean {
  return unlocked;
}

function allowed(cue: Cue): boolean {
  if (NOTIFICATION_CUES.has(cue)) return notificationSoundEnabled();
  return soundsEnabled();
}

/** يعزف نغمةً واحدة على السياق المفتوح — بلا شرطٍ ولا فحصِ مفتاح. */
function voice(ctx: AudioContext, note: Note, from: number): void {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  // **مثلثةٌ لا مربّعة**: توافقياتُ المربّعة العليا هي ما يجعل نغمةَ الهاتف
  // حادّةً — والمثلثةُ تحمل دفئاً بلا أن تخترق (§9)
  osc.type = "triangle";
  osc.frequency.value = note.hz;

  const peak = note.gain ?? 0.5;
  const start = from + note.at;
  // هجومٌ 15ms وانحدارٌ أُسّي (§9): القطعُ المفاجئ يُسمع نقرةً
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(peak, start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + note.for);

  osc.connect(gain).connect(ctx.destination);
  osc.start(start);
  osc.stop(start + note.for + 0.02);
}

/** يعزف نغمةً — ويصمت بلا خطأ إن كان الصوتُ مطفأً أو لم تقع إيماءةٌ بعد. */
export function play(cue: Cue): void {
  if (!unlocked || !context || !allowed(cue)) return;
  const now = context.currentTime;
  for (const note of CUES[cue]) voice(context, note, now);
}

/** طولُ النغمة بالثواني — يحتاجه المكرِّر ليصل الدورات بلا فاصلٍ مسموع. */
export function durationOf(cue: Cue): number {
  return CUES[cue].reduce((end, note) => Math.max(end, note.at + note.for), 0);
}
