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
/** **مفتاحُ ما عدا الطلب** — واسمُ التخزين بقي `notifications` لأن تبديلَه
 *  **يُطفئ الصوتَ عند من أشعله**: المفتاحُ محفوظٌ على جهازه، ومفتاحٌ جديدٌ
 *  يُقرأ غيابُه «مفعّل» فيعود الصوتُ لمن أطفأه. **والاسمُ في الشيفرة يقول
 *  الفئةَ، واسمُ التخزين يحفظ الاختيار.** */
const KEY_OTHER = "taxo.driver.sound.notifications";
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
  | "rideStarted"
  | "driverArrived"
  | "rideCompleted"
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
  // **بدءُ الرحلة — الموتيف صاعداً وقد اكتمل**: `A4 → D5 → E5` بلا تكرار،
  // فهو إعلانُ انطلاقٍ لا نداءٌ ينتظر جواباً.
  rideStarted: [
    { hz: A4, at: 0, for: 0.16 },
    { hz: D5, at: 0.13, for: 0.16 },
    { hz: E5, at: 0.26, for: 0.22 },
  ],
  // **وصولُ الكبتن — هادئ**: نغمتان من الموتيف بثلثَي الشدّة. **يقع والكبتنُ
  // يقود**، فصوتٌ يفزعه أسوأُ من صمت.
  driverArrived: [
    { hz: D5, at: 0, for: 0.14, gain: 0.34 },
    { hz: E5, at: 0.12, for: 0.18, gain: 0.34 },
  ],
  // **إنهاءُ الرحلة — الموتيف تامّاً ثم ينحلّ إلى الأوكتاف**: أطولُ ما في
  // الجدول بعد الطلب، **لأنه خاتمةٌ لا خبرٌ عابر**.
  //
  // **وغيرُ `collected` عمداً** (قرارُ المالك 2026-08-30): تلك للتحصيل — أي
  // **لوصول المال**؛ وهذه لانتهاء العمل. **ونغمةٌ واحدةٌ لحدثين تجعل الكبتنَ
  // يظنّ أنه قبض وهو لم يقبض بعد.**
  rideCompleted: [
    { hz: A4, at: 0, for: 0.16 },
    { hz: D5, at: 0.13, for: 0.16 },
    { hz: E5, at: 0.26, for: 0.16 },
    { hz: A5, at: 0.4, for: 0.28 },
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

/** **فئاتٌ ثلاثٌ لا نغمةٌ واحدة** (قرارُ المالك 2026-08-30).
 *
 * **وكان `NOTIFICATION_CUES = {notify}`** — مفتاحٌ يحكم **نغمةً واحدة**
 * واسمُه يَعِد بفئة. فمن أطفأ «أصوات الإشعارات» ظنّ أنه أسكت ما عدا الطلب،
 * **وأسكت واحدةً من ثمان** — والباقياتُ تحت المفتاح العام معه.
 *
 * **والثلاثُ الآن**: الطلبُ وحدَه · وما عداه · والعامُّ فوقهما. **فسؤال
 * «أيُطفئ كلٌّ ما يخصّه؟» صار له جوابٌ يُقاس.**
 */
const OFFER_CUES: ReadonlySet<Cue> = new Set<Cue>(["offer", "offerExpired"]);

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

export function otherSoundsEnabled(): boolean {
  return enabled(KEY_OTHER);
}

export function setSoundsEnabled(on: boolean): void {
  localStorage.setItem(KEY, on ? "on" : "off");
}

export function setOtherSoundsEnabled(on: boolean): void {
  localStorage.setItem(KEY_OTHER, on ? "on" : "off");
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
  // **الطلبُ الوارد يتخطّى المفتاحَ العام** — ومعه نغمةُ انقضائه: من قصد
  // إسكاتَ الطلب قصد إسكاتَ طرفَيه، **ونصفُ حدثٍ مسموعٌ أربكُ من صامتٍ كلِّه**
  if (OFFER_CUES.has(cue)) return offerSoundEnabled();
  // **وما عداه فئةٌ واحدةٌ تحت مفتاحها، وكلاهما تحت العام**: إطفاءُ العامِّ
  // يُسكت الفئتين، وإطفاءُ فئةٍ لا يمسّ الأخرى
  return soundsEnabled() && otherSoundsEnabled();
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

/** يعزف نغمةً — ويصمت بلا خطأ إن كان الصوتُ مطفأً أو لم تقع إيماءةٌ بعد.
 *
 * **والاهتزازُ معها لا في مسارٍ ثانٍ** (قرارُ المالك 2026-08-30): بابٌ واحدٌ
 * يقرّر «أيُسمَع؟» — **ومناداةُ الاهتزاز من مواضعَ متفرّقةٍ تجعل نغمةً تُطفأ
 * ويبقى جيبُه يهتزّ**، وهو ما لا يفسّره له شيء.
 */
export function play(cue: Cue): void {
  if (!unlocked || !context || !allowed(cue)) return;
  const now = context.currentTime;
  for (const note of CUES[cue]) voice(context, note, now);
  buzz(cue);
}

/** نبضتان لا واحدة — **وطلبٌ يفوت أثقلُ من إشعارٍ يفوت** (قرارُ المالك).
 *
 * **والطويلةُ تطابق نبضةَ القناة الأصليّة** (`OfferAlert`: 350/200/350) — فمن
 * سمعه في الخلفية وفي المقدّمة أحسّ الشيءَ نفسَه، **ونبضتان مختلفتان لحدثٍ
 * واحدٍ تُقرآن حدثين**.
 *
 * **ولا يُدَّعى أنه يعمل حيث لا يعمل**: `navigator.vibrate` غائبةٌ في سفاري
 * وأكثرِ أجهزة iOS، **وتُرجع `false` صامتةً في كروم بلا تفاعلٍ سابق** — فهو
 * زيادةٌ على الصوت لا بديلٌ عنه.
 */
function buzz(cue: Cue): void {
  if (typeof navigator === "undefined" || !("vibrate" in navigator)) return;
  try {
    navigator.vibrate(
      cue === "offer" ? [350, 200, 350] : [120],
    );
  } catch {
    // جهازٌ يعلن الدالّةَ ويمنعها — ولا شيءَ يُفعل، والصوتُ قائم
  }
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
  // **والاهتزازُ يقع داخل `play`** — فلا نداءَ ثانٍ هنا
  play("offer");
  loopTimer = window.setInterval(
    () => play("offer"),
    durationOf("offer") * 1000 + 120,
  );
}

export function stopOfferLoop(): void {
  if (loopTimer !== null) {
    window.clearInterval(loopTimer);
    loopTimer = null;
  }
}

