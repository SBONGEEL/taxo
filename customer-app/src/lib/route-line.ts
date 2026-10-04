/** قصُّ ما مضى من مسار الرحلة — تتبّعُ التقدّم بعد البدء (البند ٨).
 *
 * **حسابُ هندسةٍ لا حسابُ مال**: القسم 14 يمنع أن تحسب الواجهةُ مبلغاً أو
 * مسافةً تُسعَّر، ولا يمنعها أن ترسم. والمسافةُ التي تُسعَّر تُحسب في الخلفية من
 * `ride_route_points` كما هي، ولا تمسّها هذه الدالة بحرف — كما تُرسم ساعةُ
 * الانتظار في التطبيق ويُحسب مبلغُها في الخلفية (12-ب).
 *
 * **ولا تُعيد طلبَ المسار**: الخطُّ مجمَّدٌ على الرحلة منذ القبول، وما يتغيّر هو
 * ما يُرسم منه. فتتبّعُ التقدّم قصٌّ في المتصفح لا نداءٌ لكل حركة.
 *
 * ونسخةٌ منها في تطبيق الكبتن: التطبيقان يتشاركان نظامَ التصميم لا شيفرةً،
 * ودالّةٌ تُستورد من تطبيقٍ إلى آخر بيتٌ ثانٍ لها (قاعدةُ `BottomNav`).
 */

export interface LatLng {
  lat: number;
  lng: number;
}

/** مربّعُ المسافة بالدرجات — يكفي للمقارنة، ولا جذرَ ولا Haversine.
 *
 * الغرضُ **ترتيبُ** النقاط لا قياسُ الأمتار بينها، والجذرُ لا يغيّر ترتيباً.
 * والفارقُ في `lng` يُصحَّح بجيب تمام العرض، وإلا بدت النقاطُ الشرقية أبعدَ
 * مما هي في خطوط عرضنا (عند 32° شمالاً يساوي الطولُ ٠٫٨٥ من العرض).
 */
function near(point: number[], at: LatLng): number {
  const scale = Math.cos((at.lat * Math.PI) / 180);
  const dx = (point[0] - at.lng) * scale;
  const dy = point[1] - at.lat;
  return dx * dx + dy * dy;
}

/** المسافةُ بين نقطتين بالكيلومتر (Haversine) — **للعرض وحدَه** («الكبتن على بعد…» · «كم متبقية» في TAXO 2.0):
 *  حسابُ هندسةٍ لا يُسعَّر منه شيء، كالقصّ أدناه. */
export function distanceKm(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/** طولُ خطٍّ بالكيلومتر — نقاطُه `[lng, lat]` كما يحفظها المسار. */
export function lengthKm(points: number[][]): number {
  let km = 0;
  for (let i = 1; i < points.length; i += 1) {
    km += distanceKm({ lat: points[i - 1][1], lng: points[i - 1][0] }, { lat: points[i][1], lng: points[i][0] });
  }
  return km;
}

/** يُرجع ما بقي من المسار ابتداءً من أقرب نقطةٍ إلى `at`.
 *
 * و`null` في `at` تُرجع المسارَ كاملاً — وهي الحالُ قبل أن يتحرك الكبتن.
 * **ولا يُقصّ إلى أقلَّ من نقطتين**: خطٌّ بنقطةٍ واحدة لا يُرسم، والوصولُ إلى
 * الوجهة يجب أن يترك آخرَ قطعةٍ ظاهرةً لا أن يمسح الخطّ.
 */
export function trimRoute(points: number[][], at: LatLng | null): number[][] {
  if (!at || points.length < 2) return points;

  let closest = 0;
  let best = Infinity;
  for (let i = 0; i < points.length; i += 1) {
    const distance = near(points[i], at);
    if (distance < best) {
      best = distance;
      closest = i;
    }
  }

  if (closest >= points.length - 1) return points.slice(-2);
  return points.slice(closest);
}
