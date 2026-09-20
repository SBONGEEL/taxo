/** آخرُ رقمٍ مرجعيٍّ رآه العميل — **الخيطُ الذي يصل عطباً في هاتفٍ بسطرٍ في السجل**.
 *
 * الخلفيةُ تُصدر `X-Request-Id` لكلِّ طلب (`core/request_id.py`) وتكتبه في
 * سطر السجل حين يقع استثناء. **وهذا الملفُّ يمسك آخرَ ما وصل** فيُرفَق بتقرير
 * العطب — فيصير سؤالُ «لماذا سقط طلبُه» بحثاً نصّياً واحداً بدل تخمينِ ساعات.
 *
 * ## ولمَ ملفٌّ وحدَه، لا متغيّرٌ في `api/client.ts`
 *
 * **كسراً لدورةِ استيراد**: `crash-reports` يستورد `api/endpoints`،
 * و`endpoints` يستورد `api/client` — فلو أمسك العميلُ الرقمَ بنفسه لاحتاج
 * `crash-reports`، وصارت الدورةُ ثلاثيّة. **وحدةٌ بلا مستوردات لا تُدخِل أحداً
 * في دورة**، وتُقرأ من الطرفين.
 */

let last: string | null = null;

/** يُنادى من `api/client.ts` على كلِّ ردّ. */
export function captureRequestId(value: string | null): void {
  if (value) last = value.slice(0, 32);
}

/** يُقرأ عند بناء تقرير العطب. */
export function lastRequestId(): string | null {
  return last;
}
