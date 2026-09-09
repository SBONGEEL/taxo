/** جلسةُ واتساب الواحدة — **الملفُّ الوحيد الذي يعرف أسلاك Baileys**.
 *
 * نفس دور `backend/app/services/whatsapp/cloud_api.py` من الجهة الأخرى: ما
 * عداه يتكلم `state()` و`sendCode()` ولا يعرف اسمَ مكتبةٍ ولا شكلَ حدث.
 *
 * **وحالُ الجلسة ثلاثٌ لا اثنتان**، وهذا هو أهمُّ ما في الملف:
 *
 * - `linked` — مرتبطةٌ وتستطيع الإرسال.
 * - `awaiting_qr` — **لم تُربط بعد**، ورمزُ الربط جاهزٌ لمن يمسحه.
 * - `disconnected` — كانت مرتبطةً فسقطت، وتحاول العودة.
 *
 * ودمجُ الأخيرتين في «غير متصلة» هو بالضبط ما يجعل جلسةً تسقط صامتة: الأولى
 * تنتظر **إنساناً يمسح رمزاً**، والثانيةُ تنتظر **الشبكةَ وحدها**. ومن يقرأ
 * «غير متصلة» لا يعرف أيَّهما، فينتظر ما لا يأتي.
 *
 * **وسقوطُ الجلسة نوعان، والفرقُ بينهما هو كلُّ خطة الطوارئ:**
 *
 * - انقطاعٌ عابر (`connectionClosed` / `timedOut` / `restartRequired`): يعود
 *   وحدَه بمهلةٍ متزايدة، ولا يحتاج أحداً.
 * - **`loggedOut` أو `forbidden`**: الرقمُ فُصل من الهاتف أو حُظر. **ولا
 *   إعادةَ اتصالٍ تنفع هنا**، ومحاولتُها إلى الأبد تُخفي الحقيقة خلف سجلٍّ
 *   يتكرر. فتُوقَف المحاولاتُ وتُرفع الحالُ `awaiting_qr` بسببٍ مكتوب — لأن
 *   المخرجَ الوحيد إنسانٌ يعيد الربط أو يبدّل القناة.
 *
 * **وحالةُ المصادقة على قرصٍ دائم** (`AUTH_DIR` على volume): إعادةُ تشغيل
 * الحاوية لا تُفقد الجلسة، وهو الفرقُ بين خدمةٍ تُعاد وخدمةٍ تحتاج هاتفاً في
 * كل مرة. وهي **مفاتيحُ حسابٍ كاملة**: من نسخها ربط نفسَه مكانَنا، فتدخل
 * النسخَ الاحتياطي مشفّرةً كما يدخله مفتاحُ Fernet — لا في المستودع أبداً.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const makeWASocket = require("@whiskeysockets/baileys").default;
const {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  generateMessageIDV2,
  Browsers,
} = require("@whiskeysockets/baileys");
const qrTerminal = require("qrcode-terminal");
const pino = require("pino");

const AUTH_DIR = process.env.WA_AUTH_DIR || "/data/auth";

// **نصُّ الرسالة واحدٌ ثابتٌ بلا روابط، ويسكن هنا لا عند من يستدعي.**
// وهذا موضعُه لا في الخلفية: خطرُ الحظر يقع على هذا الرقم، فما يُكتب على
// السلك يملكه من يملك السلك — وواجهةٌ تقبل نصّاً من الخارج تجعل «بلا روابط»
// وعداً يحرسه المستدعي، أي وعداً يُنقض أوّلَ مسارٍ جديد.
// **ولا رابطَ ولا زرّ**: الروابطُ هي أكثرُ ما يُصنّف رسائلَ الآلات مزعجةً.
const MESSAGE = (code, ttlMinutes) =>
  `رمز تأكيد رقمك في تاكسو: ${code}\n` +
  `صالح ${ttlMinutes} دقيقة. لا تشاركه مع أحد.`;

// مهلُ إعادة الاتصال — تتضاعف حتى سقفٍ، فلا يُغرق انقطاعٌ طويلٌ الخادمَ
// بمحاولاتٍ كلَّ ثانية ولا ينام ساعةً بعد وميضٍ عابر
const RECONNECT_MIN_MS = 2_000;
const RECONNECT_MAX_MS = 60_000;

// **مهلةُ إقرار الخادم** — عشرُ ثوانٍ، **وصارت تقيس ما تسمّيه**: الإقرارُ
// المنتظَر الآن عقدةُ `<ack class="message">` من خادم واتساب، وقد قِيست على
// هذا التركيب عند **١٢٢ مللي ثانية** (2026-08-18، رسالةٌ إلى 218916166400).
// فالعشرةُ تسعُ تعثّرَ شبكةٍ بثمانين ضعفاً ولا تسعُ مقبساً ساقطاً.
//
// وكانت هذه المهلةُ قبل اليوم تنتظر **إيصالَ تسليمٍ من هاتف المستقبِل**، وهو
// حدثٌ لا يملك أحدٌ عندنا سببَ وقوعه في عشر ثوانٍ: هاتفٌ نائمٌ يؤخّره دقائق.
const ACK_TIMEOUT_MS = 10_000;

// عمرُ رمز الربط عند واتساب — بعده يولّد Baileys غيرَه من نفسه، وهذا الرقم
// لعرضِ «يبقى كذا» في اللوحة لا لحساب شيء

const QR_TTL_SECONDS = 60;

// **زمنُ استئنافِ دورةِ الرمز** حين تنتهي ولم يمسحها أحد. ثانيتان: الفجوةُ
// التي يراها من يقف أمام هاتفه، ولا داعيَ لأن تطول — فما ينتظره إنسانٌ لا شبكة
const QR_CYCLE_RESTART_MS = 2_000;

// **مستوى سجلّ Baileys — ولم يعد `silent`.** كان إخراسُها كاملاً يبتلع السطرَ
// الوحيد الذي يقول إن واتساب **رفض** رسالةً بعينها
// (`'received error in ack'`)، فيصير رفضُ الخادم ومهلةُ الإقرار حادثةً واحدةً
// في السجل. `warn` افتراضاً: يبقي الضجيجَ صامتاً ويُبقي الرفضَ مرئياً.
const BAILEYS_LOG_LEVEL = process.env.WA_BAILEYS_LOG_LEVEL || "warn";

const logger = pino({
  level: process.env.WA_LOG_LEVEL || "info",
  // خدمةٌ في حاوية: السطرُ الواحد يقرؤه `docker compose logs` بلا تلوين
  transport: undefined,
});

class Session {
  constructor() {
    this._sock = null;
    this._state = "awaiting_qr";
    this._qr = null;
    this._qrAt = null;
    this._phone = null;
    this._since = null;
    this._lastError = null;
    this._fatal = false;
    this._attempt = 0;
    this._starting = false;
  }

  /** ما تقرؤه اللوحة — **وصفٌ لا يخمّن**: كلُّ حقلٍ فيه واقعةٌ مقيسة. */
  snapshot() {
    return {
      state: this._state,
      phone: this._phone,
      since: this._since,
      last_error: this._lastError,
      // **يفرّق بين «لم يُربط بعد» و«سقط ولا يعود»**: الثاني يحتاج قراراً
      // (إعادة ربطٍ أو تبديلَ قناة)، والأولُ يحتاج مسحَ رمزٍ لا أكثر
      needs_human: this._fatal || this._state === "awaiting_qr",
      qr_available: Boolean(this._qr),
      qr_age_seconds:
        this._qrAt === null ? null : Math.round((Date.now() - this._qrAt) / 1000),
    };
  }

  /** رمزُ الربط الخام — تُحوّله اللوحةُ إلى مربّعٍ في المتصفح لا نحن. */
  qr() {
    if (!this._qr) return null;
    return { qr: this._qr, ttl_seconds: QR_TTL_SECONDS };
  }

  get linked() {
    return this._state === "linked";
  }

  async start() {
    if (this._starting) return;
    this._starting = true;
    try {
      fs.mkdirSync(AUTH_DIR, { recursive: true });
      const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
      const { version } = await fetchLatestBaileysVersion();
      logger.info({ version }, "بدءُ جلسة واتساب");

      const sock = makeWASocket({
        version,
        auth: state,
        // **متصفّحٌ مسمّى**: يظهر للمالك في «الأجهزة المرتبطة» على هاتفه،
        // فيعرف ما يفصله إن أراد — جهازٌ بلا اسمٍ يُفصل بالخطأ
        browser: Browsers.ubuntu("TAXO OTP"),
        // لا نقرأ رسائلَ أحد ولا نعلن حضوراً: هذه قناةُ إرسالٍ باتجاه واحد
        markOnlineOnConnect: false,
        syncFullHistory: false,
        // **ولا استعلاماتِ تهيئة** — والقرارُ مقيسٌ لا احترازيّ (2026-08-18).
        //
        // تُطلق Baileys عند كل اتصالٍ ثلاثةَ استعلامات «مجاراةً لواتساب وِب»:
        // `props` و`blocklist` و`privacy`. وقُرئ السلكُ الخام كلُّه عند
        // `trace` فكان الجواب:
        //
        // | الاستعلام | جوابُ واتساب |
        // |---|---|
        // | `<props protocol='2'>` | **لا جوابَ أبداً** — ثم ٤٠٨ بعد ٦٠ث |
        // | `blocklist` | `<list addressing_mode='lid'/>` |
        // | `privacy` | قائمةُ الفئات كاملةً |
        // | `w:p ping` كلَّ ٣٠ث | مُجابٌ دائماً |
        //
        // **فالمقبسُ سليمٌ تماماً، والمعلّقُ استعلامٌ واحدٌ لا نقرأ جوابَه.**
        // وهذا ينفي صراحةً أن يكون هذا الـ٤٠٨ هو ما «يبتلع الرسائل»: على
        // المقبس نفسِه والـ`props` معلّقةٌ، جاء إقرارُ رسالةٍ في ١٢٢ مللي.
        // ابتلاعُ الرسائل كان سقوطَ المقبس على فشل DNS، وقد أُغلق بتثبيت
        // المُحلِّلَين في compose.
        //
        // **وما يُصلحه الإطفاء إذن ليس تسليماً بل صدقَ السجل**: استعلامٌ
        // يعلّق منتظِراً ستين ثانيةً في كل اتصال، ورفضُه داخل `Promise.all`
        // يبتلع نجاحَ الاثنين الآخرين، ويطبع `logger.error` يقرؤه من بعدنا
        // عطباً في القناة فيطارد ما ليس بعطب — وهو ثمنٌ دفعناه فعلاً.
        //
        // **وأمانُه مقيسٌ من حالتنا نفسِها**: `creds.json` لا يحمل
        // `lastPropHash` أصلاً، أي أن هذا الرقم رُبط بمسح رمزٍ و`props` لم
        // تُجَب قطُّ — فتحذيرُ Baileys («قد تُصلح فشلَ مسح الرمز») لا ينطبق
        // على تركيبٍ عاش عمرَه كلَّه بلا جوابها.
        fireInitQueries: false,
        logger: pino({ level: BAILEYS_LOG_LEVEL }),
      });

      sock.ev.on("creds.update", saveCreds);
      sock.ev.on("connection.update", (update) => this._onUpdate(update));
      // **إقرارُ التسليم** — وهو الحكمُ الوحيد الذي يُصدَّق (قرارُ المالك
      // 2026-08-17). `sendMessage` يعيد مرجعاً بمجرد **قبولِ** الرسالة في
      // مخزن Baileys، ومقبسٌ يسقط بعدها يبتلعها بلا خطأ: نظامُنا يقرأ
      // «أُرسلت» والهاتفُ صامت. وهو ما وقع فعلاً على ثلاثة أرقام.
      // **`messages.update` تُسجَّل ولا يُحكَم بها** — وهذا انقلابٌ عن السابق.
      //
      // Baileys **لا تُصدِر هذا الحدث عن إقرار الخادم إطلاقاً**: حالتُه لا
      // تأتي إلا من عقدة `<receipt>` (`Socket/messages-recv.js:525`)، وخريطتُها
      // (`Utils/generics.js:249`) ثلاثةُ مدخلاتٍ ليس فيها إقرارُ الخادم؛ أما
      // `<ack>` الناجحة فيبتلعها `handleBadAck` بلا حدث. فشرطُ `>= 2` الذي كان
      // هنا كان — بحكم المصدر — انتظاراً **لهاتف المستقبِل**.
      //
      // **وقِيس ذلك حيّاً** (2026-08-18): الذي أرضى الشرطَ كان `status=3` عند
      // ٢٥١٤ مللي، أي إيصالَ تسليمٍ من S21 مستيقظٍ في يد صاحبه؛ ولو كان نائماً
      // لتأخّر دقائق ولسقط الرمزُ الذي سُلِّم فعلاً.
      //
      // **و`0` تُطبع مع البقية**: هي `WAMessageStatus.ERROR` — رفضُ واتساب
      // مكتوباً. وترشيحُها خارجاً بشرطٍ `>= 2` كان يجعل الرفضَ والصمتَ سطراً
      // واحداً في السجل: كلاهما «لم يصل إقرار».
      sock.ev.on("messages.update", (updates) => {
        for (const item of updates || []) {
          const id = item?.key?.id;
          const status = item?.update?.status;
          if (!id || status === undefined) continue;
          logger.info(
            {
              id,
              status,
              since_send_ms: this._sinceSend(id),
              awaited: this._acks.has(id),
            },
            "messages.update",
          );
        }
      });

      // **الحكمُ هنا وحدَه: `<ack class="message">` من خادم واتساب.**
      //
      // هي جوابُ **الخادم** على رسالةٍ أرسلناها، وهي المعنى الحرفيُّ لـ«غادرت
      // الرسالةُ سلكَنا ووصلت واتساب» — وهو بالضبط ما تعِد به هذه القناة ولا
      // تعِد بأكثرَ منه. ونقرؤها **من العقدة الخام لا من `messages.update`**
      // لأن نجاحَها لا يُصدِر حدثاً أصلاً، وفشلَها يُصدِره مشتقّاً؛ فقراءةُ
      // المنبع تُغني عن مصدرين لحقيقةٍ واحدةٍ يختلفان يوماً.
      //
      // **و`attrs.error` حاضراً رفضٌ صريحٌ يرتدّ في حينه** — لا بعد عشر ثوانٍ
      // من صمتٍ لم يقع. والشرطُ `if (attrs.error)` هو نفسُه شرطُ `handleBadAck`
      // حرفياً، فلا يمكن أن نقرأ العقدةَ على غير ما تقرؤها المكتبة.
      sock.ws.on("CB:ack", (node) => {
        const attrs = node?.attrs || {};
        if (attrs.class !== "message") return;
        const id = attrs.id;
        logger.info(
          {
            id,
            from: attrs.from,
            error: attrs.error ?? null,
            since_send_ms: this._sinceSend(id),
            awaited: this._acks.has(id),
          },
          "CB:ack",
        );
        const waiter = this._acks.get(id);
        if (!waiter) return;
        this._acks.delete(id);
        if (attrs.error) waiter.reject(String(attrs.error));
        else waiter.resolve();
      });

      // **`<receipt>` تُقاس ولا يُنتظَر عليها.** هي جوابُ **جهاز المستقبِل** لا
      // الخادم: `type` غائباً ⇐ تسليم (٣)، و`read` ⇐ قراءة (٤). وانتظارُها هو
      // بعينه ما يمنعه تعليقُ هذا الملف — «انتظارُ تسليمِ الهاتف يعلّق الرمزَ
      // خلف هاتفٍ مطفأ، وذلك شأنُ صاحبه لا شأنُ قناتنا» — وكان الكودُ يفعله.
      //
      // **وتبقى مسجَّلةً لأنها الشيءُ الوحيد الذي يثبت وصولاً فعلياً**: يومَ
      // يُشكى من رمزٍ لم يصل، هذا السطرُ هو الفرق بين «سلّمناه» و«ظنناه».
      sock.ws.on("CB:receipt", (node) => {
        const attrs = node?.attrs || {};
        logger.info(
          {
            id: attrs.id,
            type: attrs.type ?? "(غائب ⇐ تسليم)",
            from: attrs.from,
            since_send_ms: this._sinceSend(attrs.id),
          },
          "CB:receipt",
        );
      });

      this._sock = sock;
    } catch (error) {
      this._lastError = String(error?.message || error);
      logger.error({ err: this._lastError }, "تعذّر بدءُ الجلسة");
      this._scheduleReconnect();
    } finally {
      this._starting = false;
    }
  }

  _onUpdate({ connection, lastDisconnect, qr }) {
    if (qr) {
      this._qr = qr;
      this._qrAt = Date.now();
      this._state = "awaiting_qr";
      // **ويُطبع في السجل أيضاً**: من يملك الخادمَ ولا يملك اللوحةَ بعد
      // (أوّلُ ربطٍ على تركيبٍ جديد) يجب أن يجد بابَه في `docker compose logs`
      qrTerminal.generate(qr, { small: true });
      logger.warn("امسح رمزَ الربط أعلاه من واتساب › الأجهزة المرتبطة");
      return;
    }

    if (connection === "open") {
      this._state = "linked";
      this._qr = null;
      this._qrAt = null;
      this._attempt = 0;
      this._fatal = false;
      this._lastError = null;
      this._since = new Date().toISOString();
      this._phone = (this._sock?.user?.id || "").split(":")[0] || null;
      logger.info({ phone: this._phone }, "الجلسةُ مرتبطة");
      return;
    }

    if (connection !== "close") return;

    const status =
      lastDisconnect?.error?.output?.statusCode ?? lastDisconnect?.error?.status;
    this._lastError = String(lastDisconnect?.error?.message || `close ${status ?? "?"}`);

    // **قطعٌ نهائيٌّ لا يُعالَج بالمحاولة**: الرقمُ فُصل أو حُظر، والمخرجُ
    // إنسان. وإعادةُ محاولةٍ إلى الأبد هنا تُخفي الحقيقةَ خلف سجلٍّ يتكرر
    if (status === DisconnectReason.loggedOut || status === DisconnectReason.forbidden) {
      this._fatal = true;
      this._state = "awaiting_qr";
      this._phone = null;
      this._since = null;
      logger.error(
        { status, err: this._lastError },
        "الجلسةُ انتهت نهائياً — يلزم ربطٌ جديد أو تبديلُ قناة",
      );
      return;
    }

    // **انتهاءُ دورة الرمز ليس انقطاعاً** — وهذا فرقٌ قِيس على هذا الجهاز لا
    // خُمِّن: Baileys يعرض نحوَ ستة رموزٍ (~دقيقتين) ثم يُغلق الاتصال بـ408
    // ورسالة `QR refs attempts ended`. أي أن معناه **«لم يمسحه أحدٌ بعد»**، لا
    // أن الشبكةَ سقطت.
    //
    // ومعاملتُه انقطاعاً تُحدث عطبين معاً، وكلاهما يقع على من يقف أمام هاتفه:
    // الحالُ تُقرأ `disconnected` فتقول اللوحةُ «تحاول العودة» بينما هي تنتظره
    // هو؛ **والمهلةُ المتزايدة تطول بطول انتظاره** — بلغت دقيقةً كاملةً بلا رمزٍ
    // على الشاشة، أي أن الجلسةَ تصير **أصعبَ ربطاً كلما تأخّر**، وهو عكسُ
    // المطلوب تماماً.
    //
    // فالقاعدة: **التراجعُ التدريجيُّ لجلسةٍ كانت مرتبطةً فسقطت**؛ وجلسةٌ لم
    // تُربط قطُّ تعود فوراً وتبقى `awaiting_qr`، لأن ما تنتظره إنسانٌ لا شبكة.
    if (!this._since) {
      this._state = "awaiting_qr";
      this._attempt = 0;
      logger.info("انتهت دورةُ الرمز ولم يُمسح — يُعرض رمزٌ جديد");
      setTimeout(() => void this.start(), QR_CYCLE_RESTART_MS);
      return;
    }

    this._state = "disconnected";
    logger.warn({ status, err: this._lastError }, "انقطعت الجلسة — إعادةُ محاولة");
    this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (this._fatal) return;
    this._attempt += 1;
    const delay = Math.min(
      RECONNECT_MAX_MS,
      RECONNECT_MIN_MS * 2 ** Math.min(this._attempt - 1, 5),
    );
    logger.info({ attempt: this._attempt, delay }, "إعادةُ الاتصال بعد");
    setTimeout(() => void this.start(), delay);
  }

  /** يرسل الرمز — ويرمي بنصٍّ صريح إن لم تكن الجلسةُ قادرة.
   *
   * **ورفضُه هنا خيرٌ من محاولةٍ تعلق**: الخلفيةُ تنتظر جواباً لتقرّر الارتداد
   * إلى القناة التالية، ونداءٌ يعلّق حتى المهلة يترك المستخدمَ أمام شاشةٍ
   * تدور — وهو ما وُجد الارتدادُ ليمنعه.
   */
  /** منتظرو الإقرار: مُعرِّفُ الرسالة ← دالةُ إيقاظ. **خريطةٌ في الذاكرة لا
   *  حالةٌ تُحفظ**: عمرُها ثوانٍ، وبوابةٌ تُعاد تشغيلُها تُسقط ما فيها — وهو
   *  الصحيح: من انتظر إقراراً ومات الانتظارُ يُعامَل فشلاً فيرتدّ. */
  _acks = new Map();

  /** لحظةُ خروجِ كلِّ رسالةٍ على السلك — **للقياس وحدَه**: بها يُقرأ كلُّ سطرٍ
   *  لاحقٍ بفارقه عن الإرسال، فيُفصل «صمتٌ تامّ» عن «وصل بعد ثلاثين ثانية».
   *  خريطةٌ في الذاكرة تُقلَّم بعد دقيقتين — أطولَ من كل ما يُنتظر. */
  _sentAt = new Map();

  /** عمرُ الرسالة على السلك بالمللي — `null` لما لا نعرفه. للسجل وحدَه. */
  _sinceSend(id) {
    const at = this._sentAt.get(id);
    return at === undefined ? null : Date.now() - at;
  }

  /** **أهذا الرقم على واتساب؟ — سؤالٌ لا يُرسل شيئاً.**
   *
   * **وفُصل عن `sendCode` في 2026-08-31 ولم يُنسخ**: السؤالُ كان يسكن داخل
   * مسار الإرسال، **فلا سبيلَ إلى جوابه إلا بأن تُشرَع الرسالة** — ومن أراد
   * أن يعرف قبل أن يرسل لم يجد باباً. **والتجربةُ الجافّة لا تبلغه**: ترتدّ
   * قبله، فتقول ماذا كان سيخرج ولا تقول أيصل.
   *
   * **وبيتٌ واحدٌ لا نسختان**: `sendCode` ينادي هذه، **فلا يفترق الفحصُ عن
   * الإرسال يوماً** — ونسختان تفترقان بحرفٍ تجعلان بابين يجيبان جوابين عن
   * سؤالٍ واحد.
   */
  async checkNumber(to) {
    if (!this.linked || !this._sock) {
      const why = this._fatal
        ? "الجلسةُ انتهت — يلزم ربطٌ جديد"
        : `الجلسةُ ${this._state}`;
      const error = new Error(why);
      error.sessionState = this._state;
      throw error;
    }

    const digits = String(to).replace(/[^0-9]/g, "");
    const jid = `${digits}@s.whatsapp.net`;

    // **يُسأل واتساب أوّلاً: هل هذا الرقم عليه أصلاً؟** رسالةٌ إلى رقمٍ ليس
    // على واتساب لا تصل ولا تفشل بوضوح — فتُقرأ «أُرسلت» ويبقى صاحبُها ينتظر.
    //
    // **ولا يمرّ إلا بإقرارٍ صريح `exists === true`** (قرارُ المالك
    // 2026-08-17): «لم يُنفَ» ليس «أُثبت». وقيمةٌ ملتبسة — `1` أو `"true"` أو
    // حقلٌ غائبٌ في نسخةٍ لاحقة من المكتبة — كانت ستمرّ بفحصٍ يقبل كلَّ ما
    // ليس كاذباً، فتُرسل رسالةٌ إلى رقمٍ لا يستقبلها.
    //
    // **والصمتُ يُفرَّق عن النفي**، وهذا هو الأهمّ: مقبسٌ متعثّرٌ يعيد قائمةً
    // فارغةً لا لأن الرقمَ غيرُ مسجَّل بل لأن السؤالَ لم يُجَب. ولو خُلطا
    // لقلنا لصاحب رقمٍ صحيح **«رقمُك ليس على واتساب»** — وهي جملةٌ كاذبةٌ
    // يصدّقها فيذهب يبحث عن عطبٍ في هاتفه، والعطبُ عندنا.
    let answer;
    try {
      answer = await this._sock.onWhatsApp(digits);
    } catch (cause) {
      const error = new Error("تعذّر سؤالُ واتساب عن الرقم — القناةُ لا تُجيب");
      error.cause = cause;
      throw error; // ٥٠٣: عطبُ قناةٍ فترتدّ الخلفيةُ إلى التالية
    }
    if (!Array.isArray(answer) || answer.length === 0) {
      // **لا جوابَ ≠ جوابٌ بالنفي** — فلا يُقال «رقمُك ليس على واتساب».
      //
      // **ولا يُقال «القناةُ لا تُجيب» أيضاً** (قِيس ٢٠٢٦-٠٩-٠٩): المقبسُ
      // ردّ، والجلسةُ مرتبطة، **ورسالةٌ خرجت وسُلِّمت في الثانية نفسِها** —
      // فدعوى السقوط تكذّبها السطورُ المجاورةُ في السجلّ نفسِه. وهي «خطأٌ
      // يسمّي غيرَ سببه»: من يقرأها ينتظر عودةَ خدمةٍ لم تغب.
      //
      // **فالحالُ ثالثةٌ باسمها**: سُئل واتساب عن هذا الرقم فلم يُجب عنه.
      const error = new Error("لم يُجب واتساب عن هذا الرقم");
      error.numberUnanswered = true;
      throw error;
    }
    const [known] = answer;
    if (known?.exists !== true) {
      const error = new Error("هذا الرقم ليس على واتساب");
      error.notOnWhatsApp = true;
      throw error;
    }

    return { digits, jid };
  }

  async sendCode(to, code, ttlMinutes, text = null) {
    // **السؤالُ قبل الإرسال — وهو الموضعُ نفسُه الذي يناديه منفذُ الفحص**
    const { digits, jid } = await this.checkNumber(to);

    // **المُعرِّفُ يُولَّد هنا قبل الإرسال، ولا يُنتظَر أن تعيده المكتبة.**
    // وليس تنظيماً: الإقرارُ قِيس عند ١٢٢ مللي ثانية، و`sendMessage` لا تعود
    // إلا بعد كتابة البايتات — فبين عودتها وتسجيلِ المنتظِر فجوةٌ يستطيع
    // الإقرارُ أن يسبقها، فيُقرأ إقرارٌ وصل «إقراراً لم يصل». وهو بالضبط شكلُ
    // العطب الذي نُصلحه اليوم، فلا يُستبدل بشكلٍ منه أضيق.
    const id = generateMessageIDV2(this._sock.user?.id);

    // والمنتظِرُ **قبل أن يخرج بايتٌ واحد**
    const settled = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._acks.delete(id);
        const error = new Error(
          "لم يُقرّ خادمُ واتساب باستلام الرسالة — القناةُ لا تنقل الآن",
        );
        error.noAck = true;
        reject(error);
      }, ACK_TIMEOUT_MS);
      this._acks.set(id, {
        resolve: () => {
          clearTimeout(timer);
          resolve();
        },
        // **رفضُ الخادم يرتدّ في حينه** — لا بعد عشر ثوانٍ من صمتٍ لم يقع.
        // ونصُّه يحمل رمزَ الخطأ كما كتبه واتساب: «٤٠١» و«٤٠٣» ليسا واحداً
        // لمن يقرأ السجل بعد شهر، وأحدُهما وحدَه يعني أن الرقمَ حُظر.
        reject: (why) => {
          clearTimeout(timer);
          const error = new Error(`رفض واتساب الرسالة (${why})`);
          error.rejectedByServer = why;
          reject(error);
        },
      });
    });

    // **حارسُ الرفض المبكّر**: الإقرارُ قد يسبق عودةَ `sendMessage` نفسِها،
    // ورفضٌ لا مستمعَ له في تلك اللحظة **يُسقط العملية كلَّها** على Node 22
    // (`unhandled rejection` = خروج). فيُعلَّق مستمعٌ فارغٌ الآن، و`await`
    // اللاحقةُ تأخذ النتيجةَ نفسَها — تعليقٌ لا يبتلع شيئاً.
    settled.catch(() => {});

    this._sentAt.set(id, Date.now());
    setTimeout(() => this._sentAt.delete(id), 120_000).unref?.();

    try {
      await this._sock.sendMessage(
        known.jid || jid,
        // **`text` مفحوصٌ سلفاً في `index.js`**، و`null` يعني أنه خالف أو لم
        // يُرسل أصلاً — فيصوغ هذا السطرُ نصَّ البوابةِ المدمج، وهو آخرُ ما
        // يُعتمد عليه كي لا تسقط قناةُ التسجيل بنصٍّ محرَّرٍ خطأً
        { text: text || MESSAGE(code, ttlMinutes) },
        { messageId: id },
      );
    } catch (cause) {
      this._acks.delete(id);
      throw cause;
    }
    logger.info(
      { id, to: digits.slice(-4) },
      "خرجت الرسالةُ على السلك — بانتظار إقرار الخادم",
    );

    // **ولا يُقال «أُرسلت» قبل إقرار الخادم** — والإقرارُ الآن هو إقرارُ
    // الخادم فعلاً، لا إيصالُ تسليمٍ من هاتفٍ لا نملك إيقاظه.
    //
    // **والمهلةُ فشلٌ لا نجاح**: قناةٌ صمتت عشرَ ثوانٍ عن إقرارٍ يقع في أعشار
    // الثانية قناةٌ لا تنقل، والشكُّ يُفسَّر لمصلحة من ينتظر الرمز.
    await settled;
    return id;
  }

  /** يفصل الجلسةَ ويمحو حالتَها — البابُ الوحيد لإعادة الربط برقمٍ آخر.
   *
   * **والمحوُ بعد الفصل لا قبله**: فصلٌ بلا محوٍ يترك مفاتيحَ جلسةٍ ميتة يعود
   * الخادمُ فيقرؤها، ومحوٌ بلا فصلٍ يترك الجهازَ معلّقاً في هاتف المالك.
   */
  async logout() {
    try {
      if (this._sock) await this._sock.logout();
    } catch (error) {
      logger.warn({ err: String(error?.message || error) }, "تعذّر الفصلُ النظيف");
    }
    try {
      fs.rmSync(AUTH_DIR, { recursive: true, force: true });
      fs.mkdirSync(AUTH_DIR, { recursive: true });
    } catch (error) {
      logger.error({ err: String(error?.message || error) }, "تعذّر محوُ الحالة");
    }
    this._sock = null;
    this._state = "awaiting_qr";
    this._fatal = false;
    this._attempt = 0;
    this._phone = null;
    this._since = null;
    this._qr = null;
    this._lastError = "فُصلت الجلسةُ بطلبٍ من الإدارة";
    await this.start();
  }
}

module.exports = { Session, logger, AUTH_DIR, MESSAGE, authDirPath: () => path.resolve(AUTH_DIR) };
