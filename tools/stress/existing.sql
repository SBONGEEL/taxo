-- بصمةُ **الصفوف القائمة قبل الاختبار** (SPEC §٧٥-أ: «يقف إن تغيّر صفٌّ قائم») — **قراءةٌ وحدَها**، تُشغَّل بين الدرجات أثناء الحمل.
-- لكلِّ جدولٍ فيه `created_at`: عددُ صفوفه التي أُنشئت **قبل** بدء الاختبار (`__T0__`) وبصمتُها — فصفٌّ قائمٌ تغيّر حرفاً يغيّرها، **وصفوفُ
-- الاختبار الجديدةُ لا تدخلها**. وما لا `created_at` فيه يُبصم كلُّه. ولا قيمةَ صفٍّ تُطبع.
BEGIN TRANSACTION READ ONLY;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT t.tablename,
       (xpath('/row/c/text()', query_to_xml(format(
           'SELECT count(*) AS c FROM %I x %s', t.tablename,
           CASE WHEN c.column_name IS NULL THEN '' ELSE format('WHERE x.created_at < %L::timestamptz', '__T0__') END
       ), false, true, '')))[1]::text AS rows,
       (xpath('/row/c/text()', query_to_xml(format(
           'SELECT md5(coalesce(string_agg(h, %L ORDER BY h), %L)) AS c FROM (SELECT md5(x::text) AS h FROM %I x %s) s',
           '', '', t.tablename,
           CASE WHEN c.column_name IS NULL THEN '' ELSE format('WHERE x.created_at < %L::timestamptz', '__T0__') END
       ), false, true, '')))[1]::text AS md5
FROM pg_tables t
LEFT JOIN information_schema.columns c
       ON c.table_schema = 'public' AND c.table_name = t.tablename AND c.column_name = 'created_at'
WHERE t.schemaname = 'public' AND t.tablename <> 'spatial_ref_sys'
ORDER BY t.tablename;
ROLLBACK;
