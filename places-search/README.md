# places-search — بحثُ الأماكن ببياناتٍ مفتوحةٍ من القرص (قرارُ المالك ٢٠٢٦-١١-١٥)

خدمةٌ صغيرةٌ (بايثون وSQLite وحدَهما) تجيب `GET /search?q=&cc=JO|DZ|LY&lat=&lng=&limit=` من فهرس **SQLite FTS5 (trigram)** على القرص.
**لا Photon ولا OpenSearch ولا Elasticsearch**: الفهرسُ لا يُحمَّل في الذاكرة؛ عاملان واتصالان بذاكرةٍ مؤقّتةٍ ٣٢ MB لكلٍّ منهما،
**وحدُّ الحاوية الصلب ٥٠٠ MB ونصفُ معالج** (`docker-compose.prod-tunnel.yml`). وما زاد على العاملَين ينتظر ١٫٥ ث ثمّ يُردّ 503،
**والخلفيّةُ تُكمل على Mapbox** (`backend/app/services/maps.py::_open_search`).

## المصادرُ ورخصُها — وما تشترطه

| المصدر | الرخصة | الشرط | كيف نفي به |
|---|---|---|---|
| OpenStreetMap (مستخرجات Geofabrik للأردن والجزائر وليبيا) | **ODbL 1.0** — تجاريٌّ مسموح | النسبةُ «© OpenStreetMap contributors»؛ **وقاعدةُ بياناتٍ مشتقّةٌ تُستعمل علناً تُتاح بالرخصة نفسِها عند الطلب** | `attribution_text` في كلِّ جوابٍ من هنا، والتطبيقان يعرضانه تحت القائمة؛ **والفهرسُ مشتقٌّ يُعطى لمن يطلبه بالرخصة نفسِها** مع هذا المجلّد (طريقةُ بنائه) |
| Overture Maps — Places (`2026-10-21.0`) | **CDLA-Permissive-2.0** (أغلبُها: Meta وMicrosoft وغيرهما)، **Apache-2.0** (Foursquare)، **CC0** (AllThePlaces) | لا نصَّ نسبةٍ ملزماً لـCDLA؛ وApache-2.0 تشترط الإبقاءَ على إشعار Foursquare | النسبةُ «Overture Maps» في `attribution_text`، **وإشعارُ Foursquare أدناه** |
| OpenFreeMap (بلاطاتُ العرض، إن اعتُمدت) | مجّانيٌّ تجاريّاً بلا مفتاح | النسبةُ OpenFreeMap · OpenMapTiles · OpenStreetMap | يضيفها MapLibre تلقائيّاً |

> إشعارُ Foursquare (Apache-2.0): «Copyright 2024 Foursquare Labs, Inc. All rights reserved.» — وقد حُوِّلت بياناتُ Foursquare إلى مخطَّط Overture.
> وفي استخراجنا للدول الثلاث: CDLA 219,889 صفّاً · Apache-2.0 436 · CC0 466 (مقيسٌ ٢٠٢٦-١١-١٥).

## البناء — خارج خادم الإنتاج، مرّةً

```bash
python3 -m venv venv && venv/bin/pip install duckdb osmium
# ١) المستخرجات:  download.geofabrik.de/{asia/jordan,africa/algeria,africa/libya}-latest.osm.pbf → pbf/
# ٢) Overture: استعلامُ DuckDB على s3://overturemaps-us-west-2/release/<الإصدار>/theme=places/type=place/*
#    مصفّىً بـ bbox وبـ addresses[1].country IN ('JO','DZ','LY') → overture_places.parquet
venv/bin/python -I build_index.py <workdir>        # ≈ ٨ دقائق، ذروةُ ذاكرةٍ ≈ ٨٥٠ MB (مقيس)
venv/bin/python -I postprocess.py <workdir>/places.sqlite .   # الأسماءُ المطويّة وعمودُ الدولة في FTS
scp places.sqlite  الخادم:/home/taxo/places/places.sqlite     # **ثمّ إعادةُ الحاوية عبر البوّابات**
```

## الاختبار — ١٠٥ أماكن

`places_105.json`: ٣٥ لكلِّ دولة (٣٠ مكاناً + ٥ شوارع)، بالعربيّة والإنجليزيّة وبأخطاءٍ إملائيّة؛ **إصابةٌ = نتيجةٌ في الخمس الأولى ضمن نصف القطر**
(المراكزُ المتوقَّعة تقريبيّةٌ ونصفُ القطر مكتوبٌ لكلِّ حالة). `python3 -I run105.py . <places.sqlite> places_105.json --misses`.
