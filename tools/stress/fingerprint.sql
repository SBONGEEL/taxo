-- بصمةُ القاعدة كلِّها (SPEC §٧٥) — **قراءةٌ وحدَها**، SQL خالصٌ يُشغَّل كما هو على الإنتاج وعلى النسخة المستعادة فيُقارَن السطرُ بالسطر.
-- لكلِّ جدولٍ: عددُ صفوفه **وبصمةٌ لا تتبع الترتيب** (md5 كلِّ صفٍّ بنصّه، مرتَّبةً، ثمّ md5 واحد). ولا قيمةَ صفٍّ تُطبع.
BEGIN TRANSACTION READ ONLY;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT t.tablename,
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I', t.tablename), false, true, '')))[1]::text AS rows,
       (xpath('/row/c/text()', query_to_xml(format(
           'SELECT md5(coalesce(string_agg(h, %L ORDER BY h), %L)) AS c FROM (SELECT md5(x::text) AS h FROM %I x) s',
           '', '', t.tablename), false, true, '')))[1]::text AS md5
FROM pg_tables t
WHERE t.schemaname = 'public' AND t.tablename <> 'spatial_ref_sys'
ORDER BY t.tablename;
ROLLBACK;
