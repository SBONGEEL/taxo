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
const KEY = "taxo.driver.sound";
const KEY_NOTIFICATIONS = "taxo.driver.sound.notifications";
/** **مفتاحُ الطلب الوارد وحدَه** — انظر `offerSoundEnabled`. */
const KEY_OFFER = "taxo.driver.sound.offer";

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
  | "offer"
  | "offerExpired"
  | "collected"
  | "credited"
  | "subscriptionEnding"
  | "error"
  | "notify"
  | "signature";

/** كلُّ نغمةٍ اشتقاقٌ من الموتيف — والجدولُ هو الهوية (§9.1). */
const CUES: Record<Cue, Note[]> = {
  // **الطلبُ الوارد — الأهمُّ والأطول**: الموتيف ×3 بفواصل 250ms، وشدّةٌ
  // تتدرّج قليلاً. يُكرَّر بلا فاصلٍ مسموع حتى ينتهي العدّاد (§9.1)
  offer: [
    { hz: A4, at: 0, for: 0.2, gain: 0.42 },
    { hz: D5, at: 0.16, for: 0.2, gain: 0.42 },
    { hz: E5, at: 0.32, for: 0.24, gain: 0.42 },
    { hz: A4, at: 0.81, for: 0.2, gain: 0.5 },
    { hz: D5, at: 0.97, for: 0.2, gain: 0.5 },
    { hz: E5, at: 1.13, for: 0.24, gain: 0.5 },
    { hz: A4, at: 1.62, for: 0.2, gain: 0.58 },
    { hz: D5, at: 1.78, for: 0.2, gain: 0.58 },
    { hz: E5, at: 1.94, for: 0.26, gain: 0.58 },
  ],
  // انتهاءُ المهلة — الموتيف نازلاً
  offerExpired: [
    { hz: E5, at: 0, for: 0.18 },
    { hz: D5, at: 0.15, for: 0.18 },
    { hz: A4, at: 0.3, for: 0.2 },
  ],
  collected: [
    { hz: D5, at: 0, for: 0.16 },
    { hz: E5, at: 0.13, for: 0.18 },
  ],
  credited: [
    { hz: A5, at: 0, for: 0.14 },
    { hz: D6, at: 0.12, for: 0.18 },
  ],
  // تنبيهُ انتهاء الاشتراك — الموتيف أوكتافاً أخفض، هادئ
  subscriptionEnding: [
    { hz: A4 / 2, at: 0, for: 0.18, gain: 0.4 },
    { hz: D5 / 2, at: 0.15, for: 0.18, gain: 0.4 },
    { hz: E5 / 2, at: 0.3, for: 0.22, gain: 0.4 },
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

/** **الطلبُ الوارد لا يحكمه المفتاحُ العام** (قرارُ المالك §9.2).
 *
 * كبتنٌ يُطفئ الأصواتَ في اجتماعٍ ثم يفوّت طلباتٍ لا يعرف أنها وصلت **يخسر
 * دخلاً ويلوم التطبيق** — والعلاقةُ بين ما أطفأه وما خسره لا تظهر له. فلا
 * يُسكتها إلا من قصدها بعينها.
 */
export function offerSoundEnabled(): boolean {
  return enabled(KEY_OFFER);
}

export function setOfferSoundEnabled(on: boolean): void {
  localStorage.setItem(KEY_OFFER, on ? "on" : "off");
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
  // **الاستثناءُ الوحيد**: الطلبُ الوارد يتخطّى المفتاحَ العام
  if (cue === "offer") return offerSoundEnabled();
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


// ------------------------------------------------------- تكرارُ الطلب الوارد

let loopTimer: number | null = null;

/** يكرّر نغمةَ الطلب حتى `stopLoop()` — **بلا فاصلٍ مسموع** بين الدورات.
 *
 * الفاصلُ محسوبٌ من طول النغمة نفسِها (`durationOf`) لا رقمٌ يُكتب هنا: رقمان
 * لطولٍ واحد يفترقان أوّلَ مرةٍ تُعدَّل نغمةٌ في الجدول، فتتراكب الدورتان أو
 * تفغر بينهما فجوة.
 */
export function startOfferLoop(): void {
  stopOfferLoop();
  if (!unlocked || !allowed("offer")) return;
  play("offer");
  buzz();
  loopTimer = window.setInterval(() => {
    play("offer");
    buzz();
  }, durationOf("offer") * 1000 + 120);
}

export function stopOfferLoop(): void {
  if (loopTimer !== null) {
    window.clearInterval(loopTimer);
    loopTimer = null;
  }
}

/** اهتزازُ الطلب — **نبضٌ مزدوجٌ يُميَّز بلا نظرٍ إلى الشاشة**.
 *
 * **وهو مربوطٌ بمفتاح صوت الطلب لا بمفتاحٍ ثالث** (قرارُ المالك 2026-08-30
 * قال «أصواتٌ واهتزازٌ لكلِّ حال» شيئاً واحداً): مفتاحان لشيءٍ واحدٍ يجعلان
 * كبتناً يُطفئ الصوتَ ظنّاً أنه أطفأ الإنذارَ **فيهتزّ جيبُه بلا أن يفهم**.
 *
 * **ويُطابق نبضةَ القناة الأصليّة** (`OfferAlert`: 350/200/350) — فمن سمعه في
 * الخلفية وفي المقدّمة سمع الشيءَ نفسَه، **ونبضتان مختلفتان تُقرآن حدثين**.
 *
 * **ولا يُدَّعى أنه يعمل حيث لا يعمل**: `navigator.vibrate` غيرُ موجودةٍ في
 * سفاري وأكثرِ أجهزة iOS، **وتُرجع `false` صامتةً في كروم بلا تفاعلٍ سابق** —
 * فلا يُبنى عليها وحدَها إنذار، وهي زيادةٌ على الصوت لا بديلٌ عنه.
 */
function buzz(): void {
  if (typeof navigator === "undefined" || !("vibrate" in navigator)) return;
  try {
    navigator.vibrate([350, 200, 350]);
  } catch {
    // جهازٌ يعلن الدالّةَ ويمنعها — ولا شيءَ يُفعل، والصوتُ قائم
  }
}
