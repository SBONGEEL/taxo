/** علمُ الدولة — **رسمٌ لا محرفُ نظام** (SPEC §٧٤-أ/٤، ولوحةُ «مختار الدولة» في Claude Design).
 *
 * **لا `🇯🇴`**: محارفُ «المؤشِّر الإقليميّ» يرسمها النظامُ علماً إن عرفها **وحرفين إن لم يعرفها** — وقع («JO الأردن» في متصفّح، `lib/phone.ts`).
 * **والاسمُ من المُنادي** (`/config` ينشره بلغة الطلب) — فلا بيتَ ثانياً لأسماء الدول هنا. **وسوقٌ يُضاف بلا رسمٍ** يُرسم له مستطيلٌ
 * محايدٌ برمزه — لا علمٌ مخترع، ولا فراغ.
 */
import type { ReactNode } from "react";

/** **الرسومُ جدولٌ بالرمز لا شرطٌ عليه** — والمقاسُ نسبةُ كلِّ علمٍ الرسميّة (الأردن وليبيا ١:٢، والجزائر ٢:٣). */
const DRAWN: Record<string, { box: string; body: ReactNode }> = {
  JO: {
    box: "0 0 28 14",
    body: (
      <>
        <rect width="28" height="4.67" fill="#000000" />
        <rect y="4.67" width="28" height="4.67" fill="#ffffff" />
        <rect y="9.33" width="28" height="4.67" fill="#007a3d" />
        <path d="M0 0L14 7L0 14Z" fill="#ce1126" />
        <circle cx="4.6" cy="7" r="1.25" fill="#ffffff" />
      </>
    ),
  },
  LY: {
    box: "0 0 28 14",
    body: (
      <>
        <rect width="28" height="3.5" fill="#e70013" />
        <rect y="3.5" width="28" height="7" fill="#000000" />
        <rect y="10.5" width="28" height="3.5" fill="#239e46" />
        <circle cx="13.6" cy="7" r="2.1" fill="#ffffff" />
        <circle cx="14.2" cy="7" r="1.7" fill="#000000" />
        <circle cx="16.3" cy="7" r="0.75" fill="#ffffff" />
      </>
    ),
  },
  DZ: {
    box: "0 0 30 20",
    body: (
      <>
        <rect width="15" height="20" fill="#006233" />
        <rect x="15" width="15" height="20" fill="#ffffff" />
        <circle cx="15" cy="10" r="5" fill="#d21034" />
        <circle cx="16.3" cy="10" r="4" fill="#ffffff" />
        <circle cx="17.6" cy="10" r="1.4" fill="#d21034" />
      </>
    ),
  },
};

export function Flag({ code, label, size = 26, muted = false }: { code: string; label: string; size?: number; muted?: boolean }) {
  const height = Math.round((size * 2) / 3);
  const className = muted ? "t2-flag muted" : "t2-flag";
  const drawn = DRAWN[code];
  if (!drawn) {
    return (
      <span className={`${className} blank`} role="img" aria-label={label} style={{ width: size, height }}>
        {code}
      </span>
    );
  }
  return (
    <svg className={className} width={size} height={height} viewBox={drawn.box} role="img" aria-label={label} preserveAspectRatio="none">
      {drawn.body}
    </svg>
  );
}
