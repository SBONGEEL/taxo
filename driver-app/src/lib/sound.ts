/** الهوية الصوتية — `DESIGN.md` §9، **وأصواتُ المكتبات المؤقّتة** (`SPEC.md` §٦١-ك).
 *
 * **أكثرُها اليومَ ملفّاتٌ لا مذبذبات** (اختيارُ المالك ٢٠٢٦-١٠-٠٥): رفض النغماتِ
 * المولَّدةَ برمجياً، واختار من مكتبةٍ مرخَّصةٍ أصواتاً **مؤقّتةً** بروح مثالين
 * أرسلهما — `FILES` أدناه، ومصدرُ كلِّ ملفٍّ وترخيصُه في `design/TAXO-SOUNDS.md`
 * ووصفةُ تشطيبه في `tools/sounds/`. **وتُستبدل لاحقاً بأصواتٍ تُصنع لـTAXO وحدَها.**
 * **وما لم يُختر له صوتٌ يبقى نغمةَ الموتيف** (`CUES`) حتى يقرّر.
 *
 * **والسياقُ يُنشأ عند أول تشغيلٍ لا عند التحميل**: `AudioContext` مورِدٌ ثقيل،
 * وإنشاؤه في وحدةٍ تُستورد مع التطبيق يوقظ عتادَ الصوت لمن لن يسمع شيئاً.
 * **والملفّاتُ تُفكّ معه** (عند أوّل إيماءة) — فلا تأخيرَ لأوّل رسمٍ، **ولا تأخيرَ
 * لأوّل نغمة**: الطلبُ لا يصل قبل لمساتٍ كثيرةٍ تسبقه (الدخولُ والاتصال).
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

/** **ما اختاره المالك — يحلّ محلَّ نغمته في موضعها وتحت مفاتيحها** (§٦١-ي/١٢).
 *
 * والمساراتُ نسبةً إلى `public/` — **ملفُّ كلِّ صوتٍ واحدٌ في التطبيقين**، فما
 * يسمعه الكبتنُ لبدء الرحلة هو ما يسمعه الراكب. */
const FILES: Partial<Record<Cue, string>> = {
  // **الطلبُ الوارد — الأهمُّ والأطول**: ٢٫٢ ث بالضبط، فتوقيتُ تكراره كما كان
  // (طولُه + ١٢٠ م.ث). وأعلى من البقية بـ٢ ديسيبل في ملفّه نفسِه (−٢٠ LUFS)
  offer: "sounds/request.mp3",
  rideStarted: "sounds/started.mp3",
  // **الإنهاءُ غيرُ التحصيل** (قرارُ المالك 2026-08-30): هذه لانتهاء العمل،
  // و`collected` لوصول المال — **ونغمةٌ واحدةٌ لحدثين تجعل الكبتنَ يظنّ أنه
  // قبض وهو لم يقبض بعد**. فملفّان مختلفان، كما كانت نغمتين مختلفتين.
  rideCompleted: "sounds/ended.mp3",
  // **والتحصيلُ والإيداعُ صوتٌ واحد**: «نجح دفعٌ أو شحن» — كلاهما مالٌ وصل
  collected: "sounds/payment.mp3",
  credited: "sounds/payment.mp3",
  // **الخطأُ ليس صوتاً منفّراً**: نغمتان منخفضتان نازلتان
  error: "sounds/error.mp3",
  notify: "sounds/notify.mp3",
};

/** **نغماتُ الموتيف — لما لم يُختر له صوتٌ بعد** (§9.1). */
const CUES: Partial<Record<Cue, Note[]>> = {
  // انتهاءُ المهلة — الموتيف نازلاً
  offerExpired: [
    { hz: E5, at: 0, for: 0.18 },
    { hz: D5, at: 0.15, for: 0.18 },
    { hz: A4, at: 0.3, for: 0.2 },
  ],
  // **وصولُ الكبتن — هادئ**: نغمتان من الموتيف بثلثَي الشدّة. **يقع والكبتنُ
  // يقود**، فصوتٌ يفزعه أسوأُ من صمت.
  driverArrived: [
    { hz: D5, at: 0, for: 0.14, gain: 0.34 },
    { hz: E5, at: 0.12, for: 0.18, gain: 0.34 },
  ],
  // تنبيهُ انتهاء الاشتراك — الموتيف أوكتافاً أخفض، هادئ
  subscriptionEnding: [
    { hz: A4 / 2, at: 0, for: 0.18, gain: 0.4 },
    { hz: D5 / 2, at: 0.15, for: 0.18, gain: 0.4 },
    { hz: E5 / 2, at: 0.3, for: 0.22, gain: 0.4 },
  ],
  // توقيعُ العلامة — الموتيف مهلاً، وهو أوّلُ ما يُسمع (**وسؤالُه مفتوحٌ**: §٦١-ي/١٤)
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

/** يُنادى من أول إيماءةٍ في التطبيق — وبدونها كلُّ تشغيلٍ يصمت بلا خطأ.
 *  **ومعه تُفكّ الملفّاتُ كلُّها**، فأوّلُ نغمةٍ تُعزف من الذاكرة لا من الشبكة. */
export function unlock(): void {
  if (unlocked) return;
  try {
    context ??= new AudioContext();
    void context.resume();
    unlocked = context.state === "running";
  } catch {
    unlocked = false;
  }
  if (context) for (const cue of Object.keys(FILES) as Cue[]) void load(cue);
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

// ------------------------------------------------------------- الملفّات

const buffers = new Map<string, AudioBuffer>();
const loading = new Map<string, Promise<AudioBuffer | null>>();

/** يفكّ ملفَّ النغمة مرّةً ويحفظه — **وتعذُّرُه يُكتب ولا يُبدَّل بغيره**: نغمةٌ
 *  قديمةٌ تُعزف مكانه **تُخفي أنّ الملفَّ لم يصل** (الشكلُ الثاني عشر)، والمحاولةُ
 *  تُعاد في التشغيل التالي. */
function load(cue: Cue): Promise<AudioBuffer | null> {
  const file = FILES[cue];
  const ctx = context;
  if (!file || !ctx) return Promise.resolve(null);
  const ready = buffers.get(file);
  if (ready) return Promise.resolve(ready);
  let pending = loading.get(file);
  if (!pending) {
    pending = fetch(`${import.meta.env.BASE_URL}${file}`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.arrayBuffer();
      })
      .then((data) => ctx.decodeAudioData(data))
      .then((buffer) => {
        buffers.set(file, buffer);
        return buffer;
      })
      .catch((caught: unknown) => {
        console.warn(`[sound] تعذّر تحميل ${file}`, caught);
        return null;
      })
      .finally(() => loading.delete(file));
    loading.set(file, pending);
  }
  return pending;
}

/** نغماتُ الطلب الجارية — **ليوقفها الرفضُ لحظتَه** لا في آخر دورتها. */
const offerVoices = new Set<{ source: AudioBufferSourceNode; gain: GainNode }>();

function sound(ctx: AudioContext, cue: Cue, buffer: AudioBuffer): void {
  const source = ctx.createBufferSource();
  const gain = ctx.createGain();
  source.buffer = buffer;
  source.connect(gain).connect(ctx.destination);
  if (cue === "offer") {
    const voice = { source, gain };
    offerVoices.add(voice);
    source.onended = () => offerVoices.delete(voice);
  }
  source.start();
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
  const ctx = context;
  if (!unlocked || !ctx || !allowed(cue)) return;
  if (FILES[cue]) {
    void load(cue).then((buffer) => {
      if (buffer) sound(ctx, cue, buffer);
    });
  } else {
    const now = ctx.currentTime;
    for (const note of CUES[cue] ?? []) voice(ctx, note, now);
  }
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

/** طولُ النغمة بالثواني — **من الملفّ نفسِه** حين يكون ملفّاً، فلا رقمَ ثانٍ
 *  لطولٍ واحد يفترق عنه أوّلَ مرّةٍ يُستبدل الملفّ. وصفرٌ لملفٍّ لم يُفكّ بعد. */
export function durationOf(cue: Cue): number {
  const file = FILES[cue];
  if (file) return buffers.get(file)?.duration ?? 0;
  return (CUES[cue] ?? []).reduce((end, note) => Math.max(end, note.at + note.for), 0);
}


// ------------------------------------------------------- تكرارُ الطلب الوارد

let loopTimer: number | null = null;
/** **رقمُ الحلقة الجارية** — يزيد مع كلِّ إيقاف: ملفٌّ يُفكّ بعد الرفض **لا يبدأ
 *  حلقةً لعرضٍ انتهى** (وهو بعينه عطبُ «النغمةُ تبقى بعد الرفض»، §٦١-ي/٩). */
let loopRun = 0;

/** يكرّر نغمةَ الطلب حتى `stopOfferLoop()` — **بلا فاصلٍ مسموع** بين الدورات.
 *
 * الفاصلُ محسوبٌ من طول النغمة نفسِها (`durationOf`) لا رقمٌ يُكتب هنا: رقمان
 * لطولٍ واحد يفترقان أوّلَ مرةٍ تُعدَّل نغمةٌ في الجدول، فتتراكب الدورتان أو
 * تفغر بينهما فجوة.
 */
export function startOfferLoop(): void {
  stopOfferLoop();
  if (!unlocked || !allowed("offer")) return;
  const run = loopRun;
  void load("offer").then((buffer) => {
    if (!buffer || run !== loopRun) return;
    // **والاهتزازُ يقع داخل `play`** — فلا نداءَ ثانٍ هنا
    play("offer");
    loopTimer = window.setInterval(() => play("offer"), durationOf("offer") * 1000 + 120);
  });
}

/** يوقف الحلقةَ **ونغمتَها الجاريةَ معها** — بخفوتٍ ٣٠ م.ث لا قطعٍ يُسمع نقرة. */
export function stopOfferLoop(): void {
  loopRun += 1;
  if (loopTimer !== null) {
    window.clearInterval(loopTimer);
    loopTimer = null;
  }
  const ctx = context;
  if (!ctx) return;
  for (const { source, gain } of offerVoices) {
    const now = ctx.currentTime;
    gain.gain.setValueAtTime(gain.gain.value, now);
    gain.gain.linearRampToValueAtTime(0, now + 0.03);
    try {
      source.stop(now + 0.035);
    } catch {
      // انتهت وحدَها في اللحظة نفسِها — ولا شيءَ يُوقَف
    }
  }
  offerVoices.clear();
}
