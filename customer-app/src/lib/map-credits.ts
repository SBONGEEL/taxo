/** **نسبةُ بيانات الخرائط كاملةً** — لصفحة «حول التطبيق والتراخيص» (SPEC §١٠٥/٤)، **منسوخةٌ حرفاً في التطبيقين**.
 *
 * **ولمَ صفحةٌ لا الخريطةُ وحدَها**: نسبةُ الخريطة صارت زرَّ ⓘ يُطوى بعد ثوانٍ (`lib/map-attribution.ts`)، وإرشاداتُ OSMF تشترط
 * حينها أن «يجد المستخدمُ معلوماتِ الرخصة إن بحث عنها» — زرٌّ في زاوية الخريطة **أو صفحةٌ في «حول»**؛ فهنا الاثنان.
 * والنصوصُ كما تطلبها مصادرُها (قِيست ٢٠٢٦-١١-١٦): OSM ⇐ «© OpenStreetMap» برابط `/copyright` وذكرُ ODbL؛ OpenFreeMap ⇐
 * «OpenFreeMap © OpenMapTiles Data from OpenStreetMap» بروابطها الثلاثة.
 */

export interface MapCredit {
  key: string;
  name: string;
  /** ما أخذناه منه وبأيِّ رخصة — بالعربيّة */
  what: string;
  url: string;
}

export const MAP_CREDITS: MapCredit[] = [
  {
    key: "osm",
    name: "© OpenStreetMap",
    what: "بياناتُ الخريطة والطرق والأماكن — من مساهمي OpenStreetMap، برخصة قاعدة البيانات المفتوحة (ODbL)",
    url: "https://www.openstreetmap.org/copyright",
  },
  {
    key: "openmaptiles",
    name: "© OpenMapTiles",
    what: "مخطّطُ بلاطات الخريطة المتّجهة",
    url: "https://www.openmaptiles.org/",
  },
  {
    key: "openfreemap",
    name: "OpenFreeMap",
    what: "خدمةُ بلاطات الخريطة",
    url: "https://openfreemap.org",
  },
  {
    key: "overture",
    name: "Overture Maps Foundation",
    what: "بياناتُ الأماكن في البحث — برخصة CDLA-Permissive 2.0",
    url: "https://overturemaps.org",
  },
  {
    key: "maplibre",
    name: "MapLibre GL JS",
    what: "محرّكُ رسم الخريطة — رخصة BSD-3-Clause",
    url: "https://maplibre.org",
  },
  {
    key: "mapbox",
    name: "© Mapbox",
    what: "الخريطةُ والبحثُ الاحتياطيّان حين لا تجيب الخريطةُ المفتوحة",
    url: "https://www.mapbox.com/about/maps/",
  },
];
