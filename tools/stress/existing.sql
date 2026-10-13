-- بصمةُ **الصفوف القائمة قبل الاختبار** (SPEC §٧٥-أ: «يقف إن تغيّر صفٌّ قائم») — **قراءةٌ وحدَها**، تُشغَّل بين الدرجات أثناء الحمل.
-- لكلِّ جدولٍ فيه `created_at`: صفوفُه التي أُنشئت **قبل** بدء الاختبار (`__T0__`) — فصفٌّ قائمٌ تغيّر حرفاً يغيّر بصمتَها، **وصفوفُ
-- الاختبار الجديدةُ لا تدخلها**. **وما لا `created_at` فيه** يُقصر على ما لا يخصّ حساباتِ الحمل (`user_id` أو `driver_id` ليس منها) —
-- **وكان يُبصم كلُّه فأنذر كذباً** (قِيس ٢٠٢٦-١٠-١٣: `user_roles` و`driver_activity_days` زادت صفوفَ الاختبار وصفوفُها القائمةُ كما هي).
-- وما لا هذا ولا ذاك يُبصم كلُّه. ولا قيمةَ صفٍّ تُطبع.
BEGIN TRANSACTION READ ONLY;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
WITH filters AS (
  SELECT t.tablename,
         CASE
           WHEN ca.column_name IS NOT NULL THEN format('WHERE x.created_at < %L::timestamptz', '__T0__')
           WHEN cu.column_name IS NOT NULL THEN
             'WHERE x.user_id IS NULL OR x.user_id NOT IN (SELECT id FROM users WHERE phone LIKE ''+962719%'')'
           WHEN cd.column_name IS NOT NULL THEN
             'WHERE x.driver_id IS NULL OR x.driver_id NOT IN (SELECT d.id FROM drivers d JOIN users u ON u.id = d.user_id WHERE u.phone LIKE ''+962719%'')'
           ELSE ''
         END AS cond
  FROM pg_tables t
  LEFT JOIN information_schema.columns ca ON ca.table_schema = 'public' AND ca.table_name = t.tablename AND ca.column_name = 'created_at'
  LEFT JOIN information_schema.columns cu ON cu.table_schema = 'public' AND cu.table_name = t.tablename AND cu.column_name = 'user_id'
  LEFT JOIN information_schema.columns cd ON cd.table_schema = 'public' AND cd.table_name = t.tablename AND cd.column_name = 'driver_id'
  WHERE t.schemaname = 'public' AND t.tablename <> 'spatial_ref_sys'
)
SELECT f.tablename,
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I x %s', f.tablename, f.cond), false, true, '')))[1]::text AS rows,
       (xpath('/row/c/text()', query_to_xml(format(
           'SELECT md5(coalesce(string_agg(h, %L ORDER BY h), %L)) AS c FROM (SELECT md5(x::text) AS h FROM %I x %s) s',
           '', '', f.tablename, f.cond), false, true, '')))[1]::text AS md5
FROM filters f
ORDER BY f.tablename;
ROLLBACK;
