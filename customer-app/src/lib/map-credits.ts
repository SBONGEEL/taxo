/** **نسبةُ بيانات الخرائط كاملةً** — لصفحة «حول التطبيق والتراخيص» (SPEC §١٠٥/٤)، **منسوخةٌ حرفاً في التطبيقين**.
 *
 * **ولمَ صفحةٌ لا الخريطةُ وحدَها**: نسبةُ الخريطة صارت زرَّ ⓘ يُطوى بعد ثوانٍ (`lib/map-attribution.ts`)، وإرشاداتُ OSMF تشترط
 * حينها أن «يجد المستخدمُ معلوماتِ الرخصة إن بحث عنها» — زرٌّ في زاوية الخريطة **أو صفحةٌ في «حول»**؛ فهنا الاثنان.
 * والنصوصُ كما تطلبها مصادرُها (قِيست ٢٠٢٦-١١-١٦): OSM ⇐ «© OpenStreetMap» برابط `/copyright` وذكرُ ODbL؛ OpenFreeMap ⇐
 * «OpenFreeMap © OpenMapTiles Data from OpenStreetMap» بروابطها الثلاثة. **ومصادرُ الخريطة المفتوحة** (أمرُ المالك ١٨/١١ السابع ٢-٢): Overture
 * ومزوّدوه كما تطلب صفحةُ نسبتهم، **وNOTICE لـFoursquare** — والجدولُ الكاملُ في `design/MAP-OPEN-DATA-TRAFFIC.md`.
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
    what: "أماكنُ الخريطة والبحث (Overture Places: CDLA-Permissive 2.0 وApache-2.0 وCC0 بحسب المزوّد)، والمباني (Overture Buildings: ODbL)",
    url: "https://docs.overturemaps.org/attribution/",
  },
  {
    key: "foursquare",
    name: "Foursquare Open Source Places",
    what: "جزءٌ من الأماكن عبر Overture — برخصة Apache-2.0، © Foursquare Labs, Inc.",
    url: "https://opensource.foursquare.com/os-places/",
  },
  {
    key: "msbuildings",
    name: "Microsoft Global ML Building Footprints",
    what: "آثارُ المباني عبر Overture Buildings — برخصة CDLA-Permissive 2.0",
    url: "https://github.com/microsoft/GlobalMLBuildingFootprints",
  },
  {
    key: "googlebuildings",
    name: "Google Open Buildings",
    what: "آثارُ المباني في الجزائر عبر Overture Buildings — برخصة CC-BY 4.0. (بياناتُ مبانٍ مفتوحة، لا شيءَ من خرائط Google)",
    url: "https://sites.research.google/gr/open-buildings/",
  },
  {
    key: "geofabrik",
    name: "Geofabrik",
    what: "مستخرجاتُ OpenStreetMap للأردن والجزائر وليبيا، تُحدَّث شهريّاً",
    url: "https://download.geofabrik.de",
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
