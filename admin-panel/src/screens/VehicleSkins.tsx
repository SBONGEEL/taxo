/** كتالوجُ مركبات الكراج والمتجر — إنشاءٌ ورسمةٌ وسعرٌ لكلِّ سوقٍ وإحصاء.
 *
 * **وشاشةٌ مستقلةٌ لا لوحٌ في «الاشتراكات»**: تلك تعرض ما وقع، وهذه **تُنشئ
 * منتَجاً يُباع** — سعرٌ وكميّةٌ ونافذةُ موسم. وخلطُهما يضع «أنشئ مركبة»
 * بجوار جدولِ ما بيع فيُضغط بحسبانه تسجيلاً.
 *
 * **وثلاثةُ أشياء تُرسم هنا لأنها قرارات:**
 *
 * 1. **المعاينةُ على خريطةٍ حقيقيةٍ بالحجم النهائي قبل الحفظ** — و**رسمةً
 *    معالَجةً لا خاماً**: الهوامشُ الشفافةُ تُقصّ عند الحفظ، فمعاينةُ الخام
 *    تُري المشرفَ حجماً غيرَ الذي سيُرسم فيضبط النسبةَ على ما لن يقع. وهي
 *    «التجربةُ الجافّة» التي أثبتت إصلاحَ قوالب الرسائل: نفسُ السلسلة، بلا
 *    كتابة.
 * 2. **الإطفاءُ لا الحذف**: مركبةٌ اشتراها كباتنُ يمحو حذفُها **سببَ ما
 *    دفعوه**، والمفتاحُ الأجنبيُّ `RESTRICT` يرفض قبل أن يصل الطلب. فالزرُّ
 *    «أطفئ» ولا زرَّ حذف.
 * 3. **«الأكثرُ مبيعاً» بيعٌ لا اقتناء**: الهديةُ تُقتنى ولا تُباع، وخلطُهما
 *    يضع مركبةً لم تُبَع قطُّ على رأس قائمةِ المبيعات.
 *
 * **والكتالوجُ عالميٌّ والسعرُ سوقيّ** (`models/vehicle_skin.py`)، فهذه
 * الشاشةُ **لا تتبع مبدّلَ الدولة** في قائمتها — وتبعُها له يُخفي عن المشرف
 * مركبةً بلا سعرٍ في السوق المعروض، وهي بالضبط ما جاء ليسعّرها.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  attachSkinAsset,
  createVehicleSkin,
  getSkinStats,
  listSkinAssets,
  listVehicleSkins,
  previewSkinArtwork,
  skinArtworkBlob,
  updateVehicleSkin,
  uploadSkinArtwork,
} from "@/api/endpoints";
import type {
  AdminSkin,
  BundledSkinAsset,
  CountryCode,
  SkinArtworkPreview,
  SkinRarity,
  SkinStats,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { SkinMapPreview } from "@/components/SkinMapPreview";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useConfig } from "@/lib/config";
import { useCountries } from "@/lib/countries";
import { currencyOf, money } from "@/lib/format";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const RARITY_LABEL: Record<SkinRarity, string> = {
  common: "عادية",
  premium: "مميّزة",
  rare: "نادرة",
  legendary: "أسطورية",
};

/** **النادرةُ والأسطوريةُ لا تُنشران على الخريطة الحرّة** افتراضياً — لأن
 *  **ما يُرى ويندر يصير معرّفاً** ينقض تجهيلَ §10. والحقلُ يبقى **مصرَّحاً**
 *  في الصفّ لا مستنتَجاً، وهذا مجرَّدُ اقتراحٍ على النموذج. */
const RARE = new Set<SkinRarity>(["rare", "legendary"]);

type Draft = {
  name: string;
  rarity: SkinRarity;
  prices: Record<string, string>;
  max_supply: string;
  level_required: string;
  valid_from: string;
  valid_until: string;
  is_gift: boolean;
  is_feminine: boolean;
  feminine_drivers_only: boolean;
  visible_before_accept: boolean;
  map_rotates: boolean;
  is_active: boolean;
  map_scale_percent: number;
};

const EMPTY: Draft = {
  name: "",
  rarity: "common",
  prices: {},
  max_supply: "",
  level_required: "",
  valid_from: "",
  valid_until: "",
  is_gift: false,
  is_feminine: false,
  feminine_drivers_only: false,
  visible_before_accept: true,
  map_rotates: true,
  is_active: true,
  map_scale_percent: 100,
};

const onlyDigits = (value: string) => digits(value).replace(/\D/g, "");
const decimal = (value: string) => digits(value).replace(/[^0-9.]/g, "");

export function VehicleSkinsScreen() {
  const { isAdmin } = useSession();
  const { config } = useConfig();
  const { rows: markets } = useCountries();
  const form = useFormError();

  const [rows, setRows] = useState<AdminSkin[] | null>(null);
  const [stats, setStats] = useState<SkinStats | null>(null);
  const [assets, setAssets] = useState<BundledSkinAsset[]>([]);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [file, setFile] = useState<File | null>(null);
  const [assetKey, setAssetKey] = useState("");
  const [preview, setPreview] = useState<SkinArtworkPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [replacing, setReplacing] = useState<AdminSkin | null>(null);

  /** رسوماتُ الصفوف — **`blob:` لأن البابَ إداريٌّ يقرأ ترويسةَ الجلسة**،
   *  و`<img src>` لا يحملها. **ومن يفتحها يغلقها**، وإلا بقيت في الذاكرة. */
  const [art, setArt] = useState<Record<string, string>>({});
  const opened = useRef<string[]>([]);

  const token = config?.providers.mapbox?.public_token ?? null;

  const load = useCallback(async () => {
    const [catalogue, summary] = await Promise.all([
      listVehicleSkins(),
      getSkinStats(),
    ]);
    setRows(catalogue);
    setStats(summary);
  }, []);

  useEffect(() => {
    load().catch((caught) => form.capture(caught, "تعذّر قراءة الكتالوج"));
    listSkinAssets()
      .then(setAssets)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  // **الرسوماتُ تُجلب مرةً لكلِّ صفٍّ له رسمة** — وما ليس له يبقى بلا نداء
  useEffect(() => {
    if (!rows) return;
    let alive = true;
    (async () => {
      const next: Record<string, string> = {};
      for (const row of rows) {
        if (!row.map_image_url) continue;
        try {
          const url = await skinArtworkBlob(row.id, "map");
          if (!alive) {
            URL.revokeObjectURL(url);
            return;
          }
          opened.current.push(url);
          next[row.id] = url;
        } catch {
          /* رسمةٌ تعذّر فتحُها تُترك فارغة — ولا تُسقط الجدول */
        }
      }
      if (alive) setArt(next);
    })();
    return () => {
      alive = false;
    };
  }, [rows]);

  useEffect(
    () => () => {
      for (const url of opened.current) URL.revokeObjectURL(url);
      opened.current = [];
    },
    [],
  );

  const neighbours = useMemo(
    () => Object.values(art).slice(0, 4),
    [art],
  );

  /** **يُعاين قبل الحفظ**: الملفُّ يمرّ بالسلسلة كاملةً ولا يُكتب شيء. */
  async function runPreview(picked: File) {
    setFile(picked);
    setPreview(null);
    setPreviewing(true);
    form.clear();
    try {
      setPreview(await previewSkinArtwork(picked));
      setAssetKey("");
    } catch (caught) {
      form.capture(caught, "تعذّرت معاينة الرسمة");
      setFile(null);
    } finally {
      setPreviewing(false);
    }
  }

  function payloadOf(value: Draft): Record<string, unknown> {
    const prices = Object.entries(value.prices)
      .filter(([, amount]) => amount.trim() !== "")
      .map(([country_code, price]) => ({ country_code, price }));
    return {
      name: value.name.trim(),
      rarity: value.rarity,
      prices,
      max_supply: value.max_supply ? Number(value.max_supply) : null,
      level_required: value.level_required
        ? Number(value.level_required)
        : null,
      valid_from: value.valid_from ? `${value.valid_from}T00:00:00Z` : null,
      valid_until: value.valid_until ? `${value.valid_until}T23:59:59Z` : null,
      is_gift: value.is_gift,
      is_feminine: value.is_feminine,
      feminine_drivers_only: value.feminine_drivers_only,
      visible_before_accept: value.visible_before_accept,
      map_rotates: value.map_rotates,
      map_scale_percent: value.map_scale_percent,
      is_active: value.is_active,
    };
  }

  async function create() {
    setBusy(true);
    form.clear();
    setDone(null);
    try {
      const created = await createVehicleSkin(payloadOf(draft));
      // **الرسمةُ خطوةٌ ثانيةٌ بحكم العقد** (`multipart` لا JSON) — وتقع فوراً
      // فلا تبقى مركبةٌ بلا رسمةٍ في الكتالوج
      if (file) await uploadSkinArtwork(created.id, "store", file);
      else if (assetKey) await attachSkinAsset(created.id, assetKey);
      setDraft(EMPTY);
      setFile(null);
      setAssetKey("");
      setPreview(null);
      setDone(
        file || assetKey
          ? "أُضيفت المركبة برسمتها"
          : "أُضيفت المركبة — **بلا رسمةٍ بعد**، تُرفع من زرّ «بدّل الرسمة»",
      );
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر إنشاء المركبة");
    } finally {
      setBusy(false);
    }
  }

  async function patch(row: AdminSkin, payload: Record<string, unknown>, note: string) {
    try {
      await updateVehicleSkin(row.id, payload);
      setDone(note);
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر التعديل");
    }
  }

  const ready =
    draft.name.trim().length >= 2 &&
    // **مركبةٌ تُباع بلا سعرٍ في أيِّ سوقٍ لا تظهر لأحد** — والعقدُ يجعل
    // `price = null` تعني «غيرُ معروضةٍ للبيع»، وهو صحيحٌ للهدية وحدَها
    (draft.is_gift || Object.values(draft.prices).some((v) => v.trim() !== ""));

  return (
    <FormErrors value={form.field}>
      <Shell
        title="مركبات الكراج والمتجر"
        subtitle="كتالوجٌ عالميٌّ وسعرٌ لكلِّ سوق — والرسمةُ تُعاين على خريطةٍ حقيقيةٍ قبل الحفظ"
      >
        <ErrorNote message={form.message} />
        <SuccessNote message={done} />

        {stats ? (
          <section className="mb-18 grid grid-cols-3 gap-12">
            <div className="rounded-16 border border-line bg-surface p-16">
              <div className="text-11.5 text-muted">إجمالي الاقتناء</div>
              <div className="mt-4 text-24 font-bold text-ink">
                {digits(stats.total_owned)}
              </div>
            </div>
            <div className="rounded-16 border border-line bg-surface p-16">
              <div className="text-11.5 text-muted">الإيراد الكلي</div>
              <div className="mt-4 flex flex-wrap gap-10 text-17 font-bold text-ink">
                {Object.keys(stats.revenue_by_currency).length === 0 ? (
                  <span className="text-14 text-muted">لا مبيعاتٍ بعد</span>
                ) : (
                  Object.entries(stats.revenue_by_currency).map(
                    ([code, amount]) => (
                      // **العملةُ تُمرَّر خاماً**: `money` تحلّ التسميةَ بنفسها،
                      // وتمريرُ تسميةٍ محلولةٍ يطبع الرقمَ عارياً
                      <span key={code}>{money(amount, code)}</span>
                    ),
                  )
                )}
              </div>
            </div>
            <div className="rounded-16 border border-line bg-surface p-16">
              <div className="text-11.5 text-muted">الأكثر مبيعاً</div>
              <div className="mt-4 text-14 font-bold text-ink">
                {stats.top_selling[0]?.sold_count
                  ? `${stats.top_selling[0].name} · ${digits(stats.top_selling[0].sold_count)}`
                  : "لا مبيعاتٍ بعد"}
              </div>
              <p className="mt-6 text-10.5 leading-note text-muted">
                بيعٌ لا اقتناء — الهديةُ تُقتنى ولا تُباع.
              </p>
            </div>
          </section>
        ) : null}

        {isAdmin ? (
          <section className="mb-18 grid grid-cols-2 gap-18 rounded-16 border border-line bg-surface p-18">
            <div>
              <h2 className="mb-14 text-16 font-bold text-ink">مركبةٌ جديدة</h2>
              <div className="grid grid-cols-2 gap-12">
                <Field
                  label="الاسم"
                  name="name"
                  value={draft.name}
                  onChange={(e) =>
                    setDraft({ ...draft, name: e.target.value })
                  }
                />
                <Select
                  label="الندرة"
                  name="rarity"
                  value={draft.rarity}
                  onChange={(e) => {
                    const rarity = e.target.value as SkinRarity;
                    setDraft({
                      ...draft,
                      rarity,
                      visible_before_accept: !RARE.has(rarity),
                    });
                  }}
                >
                  {(Object.keys(RARITY_LABEL) as SkinRarity[]).map((key) => (
                    <option key={key} value={key}>
                      {RARITY_LABEL[key]}
                    </option>
                  ))}
                </Select>

                {(markets ?? []).map((market) => (
                  <Field
                    key={market.country_code}
                    label={`السعر في ${market.name} (${currencyOf(market.country_code as CountryCode)})`}
                    name={`price_${market.country_code}`}
                    dir="ltr"
                    inputMode="decimal"
                    value={draft.prices[market.country_code] ?? ""}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        prices: {
                          ...draft.prices,
                          [market.country_code]: decimal(e.target.value),
                        },
                      })
                    }
                  />
                ))}

                <Field
                  label="الكمية (فارغٌ = بلا حدّ)"
                  name="max_supply"
                  dir="ltr"
                  inputMode="numeric"
                  value={draft.max_supply}
                  onChange={(e) =>
                    setDraft({ ...draft, max_supply: onlyDigits(e.target.value) })
                  }
                />
                <Field
                  label="المستوى المطلوب (فارغٌ = بلا شرط)"
                  name="level_required"
                  dir="ltr"
                  inputMode="numeric"
                  value={draft.level_required}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      level_required: onlyDigits(e.target.value),
                    })
                  }
                />
                <Field
                  label="بداية الموسم"
                  name="valid_from"
                  type="date"
                  value={draft.valid_from}
                  onChange={(e) =>
                    setDraft({ ...draft, valid_from: e.target.value })
                  }
                />
                <Field
                  label="نهاية الموسم"
                  name="valid_until"
                  type="date"
                  value={draft.valid_until}
                  onChange={(e) =>
                    setDraft({ ...draft, valid_until: e.target.value })
                  }
                />
              </div>

              <div className="mt-14 grid grid-cols-2 gap-10 text-12.5 text-ink">
                <Checkbox
                  checked={draft.is_gift}
                  onChange={(next) => setDraft({ ...draft, is_gift: next })}
                >
                  هديةُ أول اشتراك
                </Checkbox>
                <Checkbox
                  checked={draft.visible_before_accept}
                  onChange={(next) =>
                    setDraft({ ...draft, visible_before_accept: next })
                  }
                >
                  تُرى على الخريطة قبل القبول
                </Checkbox>
                <Checkbox
                  checked={draft.map_rotates}
                  onChange={(next) => setDraft({ ...draft, map_rotates: next })}
                >
                  تدور مع اتجاه السير
                </Checkbox>
                <Checkbox
                  checked={draft.is_feminine}
                  onChange={(next) => setDraft({ ...draft, is_feminine: next })}
                >
                  سِمةٌ نسائية
                </Checkbox>
                <Checkbox
                  checked={draft.feminine_drivers_only}
                  onChange={(next) =>
                    setDraft({ ...draft, feminine_drivers_only: next })
                  }
                >
                  للسائقات وحدَهنّ
                </Checkbox>
                <Checkbox
                  checked={draft.is_active}
                  onChange={(next) => setDraft({ ...draft, is_active: next })}
                >
                  مفعَّلة
                </Checkbox>
              </div>

              {RARE.has(draft.rarity) && draft.visible_before_accept ? (
                <p className="mt-10 rounded-12 border border-warn bg-surface-2 px-13 py-11 text-11.5 leading-note text-warn">
                  ندرةٌ تُرى على الخريطة الحرّة تصير **معرّفاً** لصاحبها: من
                  يملك الوحيدةَ في المدينة يُتعقَّب بها، وذلك ينقض تجهيلَ
                  القسم العاشر.
                </p>
              ) : null}
            </div>

            <div>
              <label className="label" htmlFor="skin-file">
                الرسمة — صورةٌ أو SVG
              </label>
              <input
                id="skin-file"
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                className="fld"
                onChange={(e) => {
                  const picked = e.target.files?.[0];
                  if (picked) void runPreview(picked);
                }}
              />
              <p className="mt-6 text-10.5 leading-note text-muted">
                النوعُ يُقرأ من محتوى الملف لا من ترويسته، والهوامشُ الشفافةُ
                تُقصّ آلياً — فما تراه أدناه هو ما سيُرسم، لا الملفُّ الخام.
              </p>

              {assets.length > 0 ? (
                <Select
                  label="أو اختر رسمةً مشحونةً مع الخلفية"
                  name="asset_key"
                  className="mt-12"
                  value={assetKey}
                  onChange={(e) => {
                    setAssetKey(e.target.value);
                    setFile(null);
                    setPreview(null);
                  }}
                >
                  <option value="">— لا شيء —</option>
                  {assets.map((asset) => (
                    <option key={asset.key} value={asset.key}>
                      {asset.name} ({asset.key})
                    </option>
                  ))}
                </Select>
              ) : null}

              <div className="mt-14">
                {previewing ? (
                  <Spinner className="mx-auto my-38" />
                ) : (
                  <SkinMapPreview
                    token={token}
                    rotates={draft.map_rotates}
                    mapImage={preview?.map_image ?? null}
                    neighbours={neighbours}
                    scalePercent={draft.map_scale_percent}
                    onScaleChange={(next) =>
                      setDraft({ ...draft, map_scale_percent: next })
                    }
                  />
                )}
              </div>

              {preview ? (
                <div className="mt-12 flex items-start gap-12 rounded-14 border border-line bg-surface-2 p-12">
                  <img
                    src={preview.store_image}
                    alt="رسمةُ بطاقة المتجر"
                    className="size-64 shrink-0"
                  />
                  <p className="text-10.5 leading-note text-muted">
                    بطاقةُ المتجر {digits(preview.store_bytes)} بايت ·
                    الخريطة {digits(preview.map_bytes)} بايت
                    {preview.source_size
                      ? ` · الأصل ${digits(preview.source_size[0])}×${digits(preview.source_size[1])}`
                      : " · متجهيّة، فلا قصَّ ولا تصغير"}
                    {preview.trimmed
                      ? ` · قُصَّ الهامشُ الشفاف إلى ${digits(preview.trimmed.join(", "))}`
                      : ""}
                  </p>
                </div>
              ) : null}

              <Button
                className="mt-14"
                size="md"
                disabled={!ready}
                loading={busy}
                onClick={() => void create()}
              >
                أضِف المركبة
              </Button>
            </div>
          </section>
        ) : null}

        {rows === null ? (
          <Spinner className="mx-auto my-38" />
        ) : rows.length === 0 ? (
          <p className="py-30 text-center text-13 text-muted">
            لا مركباتٍ في الكتالوج بعد.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-16 border border-line">
            <table className="w-full text-13">
              <thead className="bg-surface-2 text-11.5 text-muted">
                <tr>
                  <th className="p-12 text-right">الرسمة</th>
                  <th className="p-12 text-right">المركبة</th>
                  <th className="p-12 text-right">الندرة</th>
                  <th className="p-12 text-right">السعر</th>
                  <th className="p-12 text-right">المتبقّي</th>
                  <th className="p-12 text-right">اقتناء</th>
                  <th className="p-12 text-right">بيع</th>
                  <th className="p-12 text-right">الإيراد</th>
                  <th className="p-12 text-right">الحال</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-line">
                    <td className="p-12">
                      {art[row.id] ? (
                        <img
                          src={art[row.id]}
                          alt=""
                          className="size-38"
                          style={{
                            transform: row.map_rotates
                              ? "rotate(124.9deg)"
                              : undefined,
                          }}
                        />
                      ) : (
                        // **وتقول أيَّ خانةٍ تنقص لا «بلا رسمة» صامتة**
                        // (النصفُ الثاني من قرار المالك (أ)، 2026-08-23):
                        // للمركبة **شكلان** — مجسّمٌ للمتجر وعلويّةٌ للخريطة —
                        // ورفعُ أحدهما يترك الآخرَ فارغاً. **ومن رفع للمتجر
                        // ثم رأى «بلا رسمة» يظنّ رفعتَه سقطت** فيعيدها على
                        // الخانة نفسِها، والعلويّةُ تبقى فارغةً إلى الأبد.
                        // **والعاقبةُ تُقال معها**: `SPEC` §28 — ما لا يحمل
                        // شكليه لا يُعرض في المتجر.
                        <span className="block text-11 leading-note text-warn">
                          {!row.store_image_url && !row.map_image_url
                            ? "بلا رسمة — المجسّم والعلويّة"
                            : !row.map_image_url
                              ? "تنقصها العلويّة (الخريطة)"
                              : "ينقصها المجسّم (المتجر)"}
                          <span className="block text-muted">لا تُعرض في المتجر</span>
                        </span>
                      )}
                    </td>
                    <td className="p-12">
                      <div className="font-bold text-ink">{row.name}</div>
                      <div className="mt-3 flex flex-wrap gap-6">
                        {row.is_gift ? <Badge tone="ok">هدية</Badge> : null}
                        {row.is_public_default ? (
                          <Badge tone="ink">البديلُ المنشور</Badge>
                        ) : null}
                        {row.is_feminine ? (
                          <Badge tone="ink">نسائية</Badge>
                        ) : null}
                        {row.feminine_drivers_only ? (
                          <Badge tone="ink">للسائقات</Badge>
                        ) : null}
                        {!row.visible_before_accept ? (
                          <Badge tone="muted">بعد القبول فقط</Badge>
                        ) : null}
                        {row.level_required ? (
                          <Badge tone="muted">
                            مستوى {digits(row.level_required)}
                          </Badge>
                        ) : null}
                      </div>
                    </td>
                    <td className="p-12 text-muted">
                      {RARITY_LABEL[row.rarity]}
                    </td>
                    <td className="p-12">
                      {row.prices.length === 0 ? (
                        <span className="text-muted">لا تُباع</span>
                      ) : (
                        row.prices.map((price) => (
                          <div key={price.country_code}>
                            {money(price.price, currencyOf(price.country_code))}
                          </div>
                        ))
                      )}
                    </td>
                    <td className="p-12">
                      {row.max_supply === null
                        ? "بلا حدّ"
                        : digits(
                            Math.max(0, row.max_supply - row.owners_count),
                          )}
                    </td>
                    <td className="p-12">{digits(row.owners_count)}</td>
                    <td className="p-12">{digits(row.sold_count)}</td>
                    <td className="p-12 font-bold text-ink">
                      {Object.keys(row.revenue).length === 0
                        ? "—"
                        : Object.entries(row.revenue).map(([code, amount]) => (
                            <div key={code}>{money(amount, code)}</div>
                          ))}
                    </td>
                    <td className="p-12">
                      <div className="flex items-center gap-10">
                        <Badge tone={row.is_active ? "ok" : "muted"}>
                          {row.is_active ? "تعمل" : "مُطفأة"}
                        </Badge>
                        {isAdmin ? (
                          <>
                            <button
                              type="button"
                              className="text-11.5 font-bold text-ink underline"
                              onClick={() =>
                                void patch(
                                  row,
                                  { is_active: !row.is_active },
                                  row.is_active
                                    ? "أُطفئت المركبة — ومن اقتناها احتفظ بها"
                                    : "أُعيد تشغيل المركبة",
                                )
                              }
                            >
                              {row.is_active ? "أطفئ" : "شغّل"}
                            </button>
                            <button
                              type="button"
                              className="text-11.5 font-bold text-ink underline"
                              onClick={() => setReplacing(row)}
                            >
                              بدّل الرسمة
                            </button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-14 text-11.5 leading-note text-muted">
          «المتبقّي» محسوبٌ لا مخزَّن: الكميةُ ناقصَ عددِ المالكين — وعمودُ
          عدّادٍ يُنقَص يدوياً يفترق عن الحقيقة أوّلَ منحةٍ إدارية، فيبيع
          المتجرُ ما ليس عنده أو يمنع ما عنده. ولا زرَّ حذفٍ هنا: مركبةٌ
          اشتراها كباتنُ يمحو حذفُها سببَ ما دفعوه.
        </p>

        {replacing ? (
          <ReplaceArtwork
            row={replacing}
            assets={assets}
            token={token}
            neighbours={neighbours}
            onClose={() => setReplacing(null)}
            onError={(message) => form.setMessage(message)}
            onDone={async (message) => {
              setReplacing(null);
              setDone(message);
              setArt({});
              await load();
            }}
          />
        ) : null}
      </Shell>
    </FormErrors>
  );
}

/** بديلُ رسمةٍ لمركبةٍ قائمة — **ومعاينتُها بنفس الباب**.
 *
 * ولا يُكرَّر منطقُ المعاينة: نفسُ التجربة الجافّة ونفسُ اللوح، فما يراه
 * المشرفُ هنا هو ما رآه هناك. **ونسختان من معاينةٍ تفترقان أوّلَ تعديل.**
 */
function ReplaceArtwork({
  row,
  assets,
  token,
  neighbours,
  onClose,
  onError,
  onDone,
}: {
  row: AdminSkin;
  assets: BundledSkinAsset[];
  token: string | null;
  neighbours: string[];
  onClose: () => void;
  onError: (message: string) => void;
  onDone: (message: string) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [assetKey, setAssetKey] = useState("");
  const [preview, setPreview] = useState<SkinArtworkPreview | null>(null);
  const [scale, setScale] = useState(row.map_scale_percent);
  const [busy, setBusy] = useState(false);

  async function pick(picked: File) {
    setFile(picked);
    setAssetKey("");
    try {
      setPreview(await previewSkinArtwork(picked));
    } catch (caught) {
      onError((caught as Error).message);
      setFile(null);
    }
  }

  async function save() {
    setBusy(true);
    try {
      if (file) await uploadSkinArtwork(row.id, "store", file);
      else if (assetKey) await attachSkinAsset(row.id, assetKey);
      if (scale !== row.map_scale_percent) {
        await updateVehicleSkin(row.id, { map_scale_percent: scale });
      }
      await onDone("حُفظت الرسمة ونسبةُ عرضها");
    } catch (caught) {
      onError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`رسمةُ ${row.name}`} onClose={onClose}>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        className="fld"
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) void pick(picked);
        }}
      />
      {assets.length > 0 ? (
        <Select
          label="أو رسمةٌ مشحونةٌ مع الخلفية"
          name="replace_asset_key"
          className="mt-12"
          value={assetKey}
          onChange={(e) => {
            setAssetKey(e.target.value);
            setFile(null);
            setPreview(null);
          }}
        >
          <option value="">— لا شيء —</option>
          {assets.map((asset) => (
            <option key={asset.key} value={asset.key}>
              {asset.name} ({asset.key})
            </option>
          ))}
        </Select>
      ) : null}

      <div className="mt-14">
        <SkinMapPreview
          token={token}
          rotates={row.map_rotates}
          mapImage={preview?.map_image ?? null}
          neighbours={neighbours}
          scalePercent={scale}
          onScaleChange={setScale}
        />
      </div>

      <div className="mt-16 flex gap-10">
        <Button
          size="md"
          loading={busy}
          disabled={!file && !assetKey && scale === row.map_scale_percent}
          onClick={() => void save()}
        >
          احفظ
        </Button>
        <Button size="md" variant="secondary" onClick={onClose}>
          إلغاء
        </Button>
      </div>
    </Modal>
  );
}
