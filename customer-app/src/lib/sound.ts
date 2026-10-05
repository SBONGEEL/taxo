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
 * **والملفّاتُ تُفكّ معه** (عند أوّل إيماءة) — فلا تأخيرَ لأوّل رسمٍ ولا لأوّل نغمة.
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
  | "approaching"
  | "arrived"
  | "started"
  | "ended"
  | "paid"
  | "topup"
  | "error"
  | "notify"
  | "signature";

/** **ما اختاره المالك — يحلّ محلَّ نغمته في موضعها وتحت مفاتيحها** (§٦١-ي/١٢).
 *
 * والمساراتُ نسبةً إلى `public/` — **ملفُّ كلِّ صوتٍ واحدٌ في التطبيقين**، فما
 * يسمعه الراكبُ لبدء الرحلة هو ما يسمعه الكبتن. */
const FILES: Partial<Record<Cue, string>> = {
  // **قبولُ كبتن — الأهم**: ثلاثُ نغماتٍ صاعدةٍ دافئة
  accepted: "sounds/accepted.mp3",
  // **«الكبتن يقترب»** (§٦١-ي/١١): نغمةٌ واحدةٌ ليّنة — تنبيهٌ لا يُقلق
  approaching: "sounds/approaching.mp3",
  arrived: "sounds/arrived.mp3",
  started: "sounds/started.mp3",
  ended: "sounds/ended.mp3",
  // **والدفعُ والشحنُ صوتٌ واحد**: «نجح دفعٌ أو شحن» — كلاهما مالٌ وصل
  paid: "sounds/payment.mp3",
  topup: "sounds/payment.mp3",
  // **الخطأُ ليس صوتاً منفّراً**: نغمتان منخفضتان نازلتان
  error: "sounds/error.mp3",
  notify: "sounds/notify.mp3",
};

/** **نغماتُ الموتيف — لما لم يُختر له صوتٌ بعد** (§9.1). */
const CUES: Partial<Record<Cue, Note[]>> = {
  // تأكيدُ الطلب — أوّلُ نغمتين
  request: [
    { hz: A4, at: 0, for: 0.16 },
    { hz: D5, at: 0.12, for: 0.16 },
  ],
  // توقيعُ العلامة — الموتيف مهلاً، وهو أوّلُ ما يُسمع (**وسؤالُه مفتوحٌ**: §٦١-ي/١٤)
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
  if (NOTIFICATION_CUES.has(cue)) return notificationSoundEnabled();
  return soundsEnabled();
}

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
  const ctx = context;
  if (!unlocked || !ctx || !allowed(cue)) return;
  if (FILES[cue]) {
    void load(cue).then((buffer) => {
      if (!buffer) return;
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start();
    });
    return;
  }
  const now = ctx.currentTime;
  for (const note of CUES[cue] ?? []) voice(ctx, note, now);
}

/** طولُ النغمة بالثواني — **من الملفّ نفسِه** حين يكون ملفّاً (صفرٌ قبل فكّه). */
export function durationOf(cue: Cue): number {
  const file = FILES[cue];
  if (file) return buffers.get(file)?.duration ?? 0;
  return (CUES[cue] ?? []).reduce((end, note) => Math.max(end, note.at + note.for), 0);
}
