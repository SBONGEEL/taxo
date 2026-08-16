/** طابورُ إرسالٍ بتباعدٍ عشوائي — **حمايةُ الرقم، لا حمايةُ الخادم**.
 *
 * ولذلك موضعُه هنا لا في الخلفية: هذا آخرُ ما يلمس السلك، والخطرُ الذي يدرأه
 * (أن يُقرأ الرقمُ آلةً فيُحظر) يقع على الرقم وحده. **وهو غيرُ السقوف**:
 * السقوفُ سياسةٌ تُقاس وتُختبر وتعيش في الخلفية على Redis، وهذا **إيقاعُ
 * إرسال** — مسألةُ أسلاكٍ لا مسألةُ قاعدة.
 *
 * **والتباعدُ عشوائيٌّ لا ثابت**: رسالةٌ كلَّ ثلاث ثوانٍ بالضبط نمطٌ أوضحُ من
 * الرشق نفسِه. ومداهُ ثانيتان إلى ستّ — أطولُ من أن يُقرأ آلةً، وأقصرُ من أن
 * يجعل الرمزَ يصل بعد أن ينسى صاحبُه أنه طلبه.
 *
 * **والطابورُ واحدٌ لكل الخدمة**: نداءان متزامنان يصطفّان ولا يخرجان معاً، وإلا
 * ضاع التباعدُ في أول لحظةِ ازدحام — وهي بالضبط اللحظة التي يُلاحَظ فيها.
 */

"use strict";

const MIN_GAP_MS = Number(process.env.WA_MIN_GAP_MS || 2_000);
const MAX_GAP_MS = Number(process.env.WA_MAX_GAP_MS || 6_000);

// سقفُ الانتظار في الطابور. من انتظر أطولَ من هذا فالأولى أن يُقال له «جرّب
// قناةً أخرى» — والخلفيةُ ترتدّ عند الخطأ، فالرفضُ الصريح مخرجٌ لا عطب
const MAX_WAIT_MS = Number(process.env.WA_MAX_WAIT_MS || 25_000);

function jitter() {
  const span = Math.max(0, MAX_GAP_MS - MIN_GAP_MS);
  return MIN_GAP_MS + Math.floor(Math.random() * (span + 1));
}

class SendQueue {
  constructor() {
    this._chain = Promise.resolve();
    this._nextAt = 0;
    this._depth = 0;
  }

  get depth() {
    return this._depth;
  }

  /** يُدخل عملاً في الطابور ويعيد نتيجته — أو يرفض إن طال الانتظار.
   *
   * **والرفضُ يقع قبل الدخول لا بعده**: من يُقبل ثم يُترك ينتظر يظنّ أن رمزَه
   * في الطريق، ومن يُرفض في ثانيته الأولى يرى زرَّ القناة الأخرى.
   */
  run(task) {
    const wait = Math.max(0, this._nextAt - Date.now());
    if (wait > MAX_WAIT_MS) {
      const error = new Error("طابورُ الإرسال مزدحم — جرّب قناةً أخرى");
      error.queueFull = true;
      return Promise.reject(error);
    }

    this._depth += 1;
    const result = this._chain.then(async () => {
      const delay = Math.max(0, this._nextAt - Date.now());
      if (delay > 0) await new Promise((resolve) => setTimeout(resolve, delay));
      try {
        return await task();
      } finally {
        // **يُحسب من لحظة الانتهاء لا من لحظة الدخول**: الفجوةُ المقصودة بين
        // رسالتين على السلك، لا بين قبولين في الذاكرة
        this._nextAt = Date.now() + jitter();
        this._depth -= 1;
      }
    });

    // السلسلةُ لا تنكسر بفشل عنصر: خطأُ رسالةٍ لا يوقف ما بعدها
    this._chain = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }
}

module.exports = { SendQueue, MIN_GAP_MS, MAX_GAP_MS, MAX_WAIT_MS };
