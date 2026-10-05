/** **بلاغٌ واحدٌ لا اثنان** — وطريقان قد يحملانه (SPEC §٦١-ل/٣، ٢٠٢٦-١٠-٠٥).
 *
 * الخلفيةُ لا ترسل الإشعارَ لجهازٍ أمامَ صاحبه، **وترسل بلاغَ المقبس** — فلا
 * يلتقيان إلا في لحظةٍ واحدة: **حين يعود صاحبُه إلى التطبيق والإشعارُ في
 * الطريق**. فيُرسم ما وصل أوّلاً، **وعنوانٌ ونصٌّ رُسما في الثواني العشر الأخيرة
 * لا يُرسمان ثانية** — وهما ما يراه المستخدمُ، فتكرارُهما هو التكرارُ عنده.
 *
 * **ونسخةٌ منه في التطبيق الآخر حرفاً** (`driver-app/src/lib/notice.ts`).
 */

const WINDOW_MS = 10_000;
const seen = new Map<string, number>();

/** `true` لأوّل رؤيةٍ لهذا البلاغ في النافذة — وإلا `false`، فلا يُرسم ولا يُسمع ثانية. */
export function firstSighting(title: string, body?: string): boolean {
  const now = Date.now();
  for (const [key, at] of seen) {
    if (now - at > WINDOW_MS) seen.delete(key);
  }
  const key = `${title}\u0000${body ?? ""}`;
  if (seen.has(key)) return false;
  seen.set(key, now);
  return true;
}
