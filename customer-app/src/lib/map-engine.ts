/** **محرّكُ الخريطة: Mapbox أو MapLibre** (SPEC §«الخرائطُ والبحثُ ببياناتٍ مفتوحة»/العرض) — **منسوخٌ حرفاً في التطبيقين**.
 *
 * **مفتاحُ `open_map_display` لسوق المستخدم يختار**: مطفأً (الافتراض) تبقى خريطةُ Mapbox كما هي حرفاً؛ ومشتعلاً تُرسم بـMapLibre
 * وبلاطاتِ OpenFreeMap بنمط TAXO (`lib/open-map-style.ts`) — بلا مفتاحٍ ولا كلفة.
 *
 * **والرجوعُ آليٌّ وفي الجلسة نفسِها**: إن لم تُحمَّل البلاطاتُ (`markOpenMapFailed`) عادت كلُّ خرائط التطبيق إلى Mapbox حتى تُغلق
 * النافذة، **ويُبلَّغ الخادمُ مرّةً** (`POST /places/health`) فيصل المالكَ إشعار. **ولا يُعاد المحاولة في الجلسة نفسِها**: خريطةٌ
 * تتأرجح بين محرّكين أسوأُ من خريطةٍ واحدةٍ ثابتة.
 *
 * **ولمَ المحرّكان معاً في الحزمة** لا تحميلٌ كسول: الخريطةُ أوّلُ ما يُرسم في الشاشة الرئيسة، والتحميلُ المؤجَّل يضيف انتظاراً
 * قبلها في كلِّ فتحة؛ وواجهتا المكتبتين واحدةٌ فيما نستعمله (الخريطة · العلامات · المصادر · الطبقات).
 */
import mapboxgl from "mapbox-gl";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useSyncExternalStore } from "react";

import { reportMapDisplayFailure } from "@/api/endpoints";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";
import { useShellOpenMap } from "@/lib/update-gate";

export const OPEN_MAP_FLAG = "open_map_display";

/** **واجهةُ Mapbox نوعاً للمحرّكين** — ما نستعمله منهما واحد، والفرقُ في الأنواع لا في السلوك. */
export type Gl = typeof mapboxgl;

export function engine(open: boolean): Gl {
  return (open ? maplibregl : mapboxgl) as unknown as Gl;
}

let failed = false;
const listeners = new Set<() => void>();

/** **البلاطاتُ لم تُحمَّل — الرجوعُ إلى Mapbox لكلِّ خرائط الجلسة**، وبلاغٌ واحدٌ للخادم. */
export function markOpenMapFailed(reason: string): void {
  if (failed) return;
  failed = true;
  console.error("[map-engine] تعذّرت خريطةُ البيانات المفتوحة — الرجوعُ إلى Mapbox:", reason);
  void reportMapDisplayFailure(reason.slice(0, 80)).catch(() => undefined);
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let webgl: boolean | null = null;

/** **أيقدر هذا الجهازُ على MapLibre؟** — سياقُ WebGL يُطلب مرّةً في الجلسة. **والرجوعُ الآليُّ لا يمسك هذا**: المكتبةُ ترمي عند
 *  الإنشاء قبل أن يُسجَّل أيُّ مستمع، فتسقط الشاشة؛ **فيُسأل قبل الاختيار**، ومن لا يقدر يبقى على Mapbox كما كان حرفاً. */
function canDrawOpenMap(): boolean {
  if (webgl !== null) return webgl;
  try {
    const canvas = document.createElement("canvas");
    webgl = Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    webgl = false;
  }
  return webgl;
}

/** **أتُرسم هذه الخريطةُ بالبيانات المفتوحة؟** — المفتاحُ لسوق المستخدم، **والغلافُ عند حدِّ لوحة الإصدارات أو فوقه**
 *  (SPEC §١٠٥/٥: الغلافُ القديمُ يبقى على Mapbox حرفاً ولو اشتعل المفتاح)، وما لم تسقط في هذه الجلسة. */
export function useOpenMap(): boolean {
  const { user } = useSession();
  const on = useFeature(user?.country_code, OPEN_MAP_FLAG);
  const down = useSyncExternalStore(subscribe, () => failed);
  const shell = useShellOpenMap();
  return on && shell && !down && canDrawOpenMap();
}
