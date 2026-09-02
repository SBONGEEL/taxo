/** بلاطاتُ الخدمات ولافتاتُ المحتوى — **تُدار من هنا بلا نشر** (`0063`/`0064`).
 *
 * ## أربعُ قواعدَ تحكم هذه الشاشة
 *
 * **١) الحذفُ للمسوّدة وحدَها** (قرارُ المالك 2026-08-31). ما عُرض مرّةً
 * **يُخفى ولا يُحذف**: حذفُه يمحو شاهداً على ما رآه الناس، ومن يقرأ بعد شهرٍ
 * «لمَ ارتفعت الضغطاتُ ذلك الأسبوع» يجد فراغاً. **والزرُّ يُرسم معطَّلاً
 * بعلّته** لا يُرسم ثمّ يرتدّ: زرٌّ يعمل ثم يرتدّ **يعلّم المشرفَ أن يعيد
 * المحاولة**، ومعطَّلٌ يقول لمَ يعلّمه أن يُخفي بدلَه.
 *
 * **٢) ولا قيمةٌ تُكتب بيدٍ حيث للخادم قائمة**: الأيقونةُ من منتقٍ يقرأ
 * `service-icons`، والمقصدُ من منتقٍ يقرأ `service-destinations` —
 * **والقائمتان تُقرآن ولا تُنسخان**، فنسختان تفترقان بحرفٍ يوماً **فيعرض
 * المنتقي ما يرفضه الباب**.
 *
 * **٣) والجمهورُ يُختار عند الإنشاء**: كانت كلُّ بلاطةٍ تُولد `all_riders`
 * نصّاً في هذا الملفّ — **فبلاطةُ كبتنٍ لم تكن تُبنى من اللوحة أصلاً**،
 * وهي «بابٌ بلا زرّ» في ثوب حقلٍ محشوّ.
 *
 * **٤) والإشعالُ بلا مقصدٍ مبنيٍّ يمنعه الخادمُ بنصّه** — والشاشةُ لا تكرّر
 * الشرط: **شرطان لقاعدةٍ واحدةٍ يفترقان**، والرسالةُ تأتي من حيث تُحرس.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createPromoBanner,
  createServiceTile,
  deleteBannerImage,
  deletePromoBanner,
  deleteServiceTile,
  listPromoBanners,
  listServiceDestinations,
  listServiceTiles,
  updatePromoBanner,
  updateServiceTile,
  uploadBannerImage,
} from "@/api/endpoints";
import type {
  CampaignAudience,
  CountryCode,
  PromoBannerRow,
  ServiceTileRow,
} from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { ConfirmDelete } from "@/components/ui/ConfirmDelete";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Table } from "@/components/Table";
import {
  BannerPreview,
  PhoneFrame,
  TilesPreview,
} from "@/components/storefront/CardPreview";
import { Glyph, IconPicker } from "@/components/storefront/IconPicker";
import { day } from "@/lib/format";

const TILE_TONE: Record<
  ServiceTileRow["status"],
  Parameters<typeof Badge>[0]["tone"]
> = { soon: "warn", active: "ok", hidden: "muted" };

const TILE_LABEL: Record<ServiceTileRow["status"], string> = {
  soon: "قريباً",
  active: "فعّالة",
  hidden: "مخفيّة",
};

const AUDIENCE_LABEL: Record<string, string> = {
  all_riders: "الركّاب",
  all_drivers: "الكباتن",
  by_country: "الاثنان",
  segment: "شريحة",
};

/** **ثلاثةٌ لا أربعة**: `segment` تُرفض في الخلفية كما تُرفض في الحملات،
 *  **فعرضُها خيارٌ يَعِد بما يُرفض**. */
const AUDIENCE_CHOICES: CampaignAudience[] = [
  "all_riders",
  "all_drivers",
  "by_country",
];

/** **الأدوارُ التي يراها هذا الجمهور** — و`by_country` تعني الاثنين. */
function rolesOf(audience: CampaignAudience): string[] {
  if (audience === "by_country") return ["rider", "driver"];
  if (audience === "all_drivers") return ["driver"];
  if (audience === "all_riders") return ["rider"];
  return [];
}

/** حقلُ التاريخ — **يُقرأ ويُكتب `YYYY-MM-DD`** كما يقبله العقد. */
function dateValue(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "";
}

/** **`datetime-local` بلا منطقة** — والخادمُ يقرأ ISO، فتُبنى هنا بمنطقة
 *  المتصفح صراحةً بدل أن تُرسل عاريةً فتُقرأ UTC وتُزيح النافذةَ ثلاثَ ساعات. */
function localValue(iso: string): string {
  const at = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}` +
    `T${pad(at.getHours())}:${pad(at.getMinutes())}`
  );
}

export function Storefront({
  country,
  onError,
}: {
  country: CountryCode;
  onError: (message: string) => void;
}) {
  const [tiles, setTiles] = useState<ServiceTileRow[]>([]);
  const [banners, setBanners] = useState<PromoBannerRow[]>([]);
  const [destinations, setDestinations] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [editingTile, setEditingTile] = useState<ServiceTileRow | null>(null);
  const [editingBanner, setEditingBanner] = useState<PromoBannerRow | null>(
    null,
  );
  const [draft, setDraft] = useState<{
    key: string;
    title: string;
    icon: string;
    audience: CampaignAudience;
  }>({ key: "", title: "", icon: "package", audience: "all_riders" });

  const fail = useCallback(
    (caught: unknown, fallback: string) =>
      onError(caught instanceof ApiError ? caught.message : fallback),
    [onError],
  );

  const load = useCallback(() => {
    Promise.all([listServiceTiles(country), listPromoBanners(country)])
      .then(([t, b]) => {
        setTiles(t);
        setBanners(b);
      })
      .catch((caught) => fail(caught, "تعذّر التحميل"));
  }, [country, fail]);

  useEffect(load, [load]);

  useEffect(() => {
    let cancelled = false;
    listServiceDestinations()
      .then((table) => !cancelled && setDestinations(table))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function patchTile(row: ServiceTileRow, changes: Partial<ServiceTileRow>) {
    setBusy(row.id);
    try {
      await updateServiceTile(row.id, changes);
      load();
    } catch (caught) {
      // **رسالةُ الخادم كما هي** — هو من يعرف لمَ مُنع
      fail(caught, "تعذّر الحفظ");
    } finally {
      setBusy(null);
    }
  }

  // **ولم يكن للحذف استئذانٌ قطّ** (البند ٤): كان يقع بضغطةٍ واحدة على صفٍّ
  // في جدول — **وضغطةٌ على الصفِّ الخطأ لا رجعةَ فيها**. والورقةُ واحدةٌ
  // مشتركة (`ConfirmDelete`) لا نسخةٌ هنا.
  const [deleting, setDeleting] = useState<
    { kind: "tile" | "banner"; id: string; name: string; run: () => Promise<void> } | null
  >(null);

  async function removeTile(row: ServiceTileRow) {
    setBusy(row.id);
    try {
      await deleteServiceTile(row.id);
      load();
    } catch (caught) {
      fail(caught, "تعذّر الحذف");
    } finally {
      setBusy(null);
    }
  }

  async function removeBanner(row: PromoBannerRow) {
    setBusy(row.id);
    try {
      await deletePromoBanner(row.id);
      load();
    } catch (caught) {
      fail(caught, "تعذّر الحذف");
    } finally {
      setBusy(null);
    }
  }

  const livePreview = tiles.filter((row) => row.status !== "hidden");

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">خدمات الشاشة الرئيسة</h2>
      <p className="mb-12 text-12 text-muted">
        بلاطاتُ الرئيسية للراكب والكبتن — تُضاف وتُشعل وتُخفى من هنا بلا نشر.
        و«قريباً» تظهر بعلامتها ولا تفتح باباً. و«فعّالة» لا تُقبل بلا مقصد
        مبنيّ في التطبيق — يمنعها الخادم بعلّته.
      </p>

      <Table
        height="compact"
        columns="0.7fr 1fr 0.5fr 0.7fr 0.5fr 1fr 1.5fr"
        headers={[
          "المفتاح",
          "العنوان",
          "الأيقونة",
          "الجمهور",
          "الترتيب",
          "المقصد",
          "",
        ]}
        rows={tiles}
        keyOf={(row) => row.id}
        empty={{ title: "لا خدمات", hint: "لم تُضف بلاطةٌ لهذا السوق بعد." }}
        render={(row) => (
          <>
            <span className="font-mono text-11.5">{row.key}</span>
            <span className="text-12 text-ink">{row.title}</span>
            <Glyph name={row.icon} className="size-16 text-muted" />
            <span className="text-11.5 text-muted">
              {AUDIENCE_LABEL[row.audience] ?? row.audience}
            </span>
            <span className="text-12 text-muted">{row.sort_order}</span>
            <span className="text-11.5 text-muted">{row.destination ?? "—"}</span>
            <div className="flex items-center gap-8">
              <span className="flex items-center gap-6">
                <Badge tone={TILE_TONE[row.status]}>{TILE_LABEL[row.status]}</Badge>
              </span>
              <Select
                name={`status-${row.id}`}
                value={row.status}
                disabled={busy === row.id}
                onChange={(event) =>
                  void patchTile(row, {
                    status: event.target.value as ServiceTileRow["status"],
                  })
                }
              >
                <option value="hidden">مخفيّة</option>
                <option value="soon">قريباً</option>
                <option value="active">فعّالة</option>
              </Select>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setEditingTile(row)}
              >
                حرّر
              </Button>
              {/* **معطَّلٌ بعلّته لا زرٌّ يرتدّ** — والعنوانُ يقول ما يُفعل بدلَه */}
              <Button
                size="sm"
                variant="danger"
                disabled={row.first_shown_at !== null || busy === row.id}
                title={
                  row.first_shown_at
                    ? "عُرضت على الناس — تُخفى ولا تُحذف"
                    : "مسوّدةٌ لم يرَها أحد"
                }
                onClick={() =>
                  setDeleting({
                    kind: "tile",
                    id: row.id,
                    name: row.title,
                    run: () => removeTile(row),
                  })
                }
              >
                احذف
              </Button>
            </div>
          </>
        )}
      />

      {/* ───────────────────────────────── إضافةُ بلاطة */}
      <div className="mt-14 flex items-end gap-8 border-t border-line pt-14">
        <Field
          name="tile_key"
          label="مفتاح"
          value={draft.key}
          onChange={(event) =>
            setDraft((d) => ({ ...d, key: event.target.value }))
          }
        />
        <Field
          name="tile_title"
          label="العنوان"
          value={draft.title}
          onChange={(event) =>
            setDraft((d) => ({ ...d, title: event.target.value }))
          }
        />
        <Select
          name="tile_audience"
          label="الجمهور"
          value={draft.audience}
          onChange={(event) =>
            setDraft((d) => ({
              ...d,
              audience: event.target.value as CampaignAudience,
            }))
          }
        >
          {AUDIENCE_CHOICES.map((value) => (
            <option key={value} value={value}>
              {AUDIENCE_LABEL[value]}
            </option>
          ))}
        </Select>
        <Button
          size="sm"
          disabled={!draft.key.trim() || !draft.title.trim()}
          onClick={() => {
            // **تُنشأ مخفيّةً دائماً** — فلا تظهر بلاطةٌ نصفُ مضبوطةٍ لأحد
            createServiceTile({
              country_code: country,
              key: draft.key.trim(),
              title: draft.title.trim(),
              icon: draft.icon.trim() || "layout-grid",
              audience: draft.audience,
              status: "hidden",
            })
              .then((created) => {
                setDraft({
                  key: "",
                  title: "",
                  icon: "package",
                  audience: "all_riders",
                });
                load();
                // **وتُفتح للتحرير فوراً**: أُنشئت بثلاثة حقولٍ من سبعة،
                // **وبلاطةٌ تُترك نصفَ مضبوطةٍ تُنسى مخفيّةً في الجدول**
                setEditingTile(created);
              })
              .catch((caught) => fail(caught, "تعذّرت الإضافة"));
          }}
        >
          أضف خدمة
        </Button>
      </div>

      {/* ───────────────────────────────── المعاينة */}
      <div className="mt-20 flex flex-wrap items-start gap-16 border-t border-line pt-16">
        <PhoneFrame>
          <TilesPreview tiles={livePreview} />
          {banners
            .filter((row) => row.is_active)
            .slice(0, 1)
            .map((row) => (
              <BannerPreview key={row.id} banner={row} />
            ))}
        </PhoneFrame>
        <p className="max-w-prose text-11.5 leading-note text-muted">
          المعاينةُ بالبطاقة نفسِها التي يرسمها التطبيق — لا بتقريبٍ لها،
          و<code className="font-mono">check:storefront-card</code> يوقف البناءَ
          إن افترقت. وتعرض ما ليس مخفيّاً: «قريباً» بعلامتها، و«جديد» مدّتها،
          واللافتةُ المشتعلةُ الأولى بصورتها إن رُفعت.
        </p>
      </div>

      {/* ───────────────────────────────── اللافتات */}
      <h3 className="mb-6 mt-20 text-13 font-bold text-ink">لافتات المحتوى</h3>
      <p className="mb-10 text-11 leading-snug text-muted">
        بطاقةٌ في الرئيسية بنافذةِ عرضٍ إلزاميّة — تختفي بانقضائها بلا نشر.
        والنافذةُ تُقاس في الخادم لا في الجهاز.
      </p>
      <Table
        height="compact"
        columns="1.2fr 0.7fr 0.9fr 0.9fr 1.6fr"
        headers={["العنوان", "الجمهور", "من", "إلى", ""]}
        rows={banners}
        keyOf={(row) => row.id}
        empty={{ title: "لا لافتات", hint: "لم تُضف لافتةٌ لهذا السوق بعد." }}
        render={(row) => (
          <>
            <span className="text-12 text-ink">{row.title}</span>
            <span className="text-11.5 text-muted">
              {AUDIENCE_LABEL[row.audience] ?? row.audience}
            </span>
            <span className="text-11.5 text-muted">{day(row.starts_at)}</span>
            <span className="text-11.5 text-muted">{day(row.ends_at)}</span>
            <div className="flex items-center gap-8">
              <Button
                size="sm"
                variant="secondary"
                loading={busy === row.id}
                onClick={() => {
                  setBusy(row.id);
                  updatePromoBanner(row.id, { is_active: !row.is_active })
                    .then(load)
                    .catch((caught) => fail(caught, "تعذّر التبديل"))
                    .finally(() => setBusy(null));
                }}
              >
                {row.is_active ? "أطفئ" : "أشعل"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setEditingBanner(row)}
              >
                حرّر
              </Button>
              <Button
                size="sm"
                variant="danger"
                disabled={row.first_shown_at !== null || busy === row.id}
                title={
                  row.first_shown_at
                    ? "عُرضت على الناس — تُطفأ ولا تُحذف"
                    : "مسوّدةٌ لم يرَها أحد"
                }
                onClick={() =>
                  setDeleting({
                    kind: "banner",
                    id: row.id,
                    name: row.title,
                    run: () => removeBanner(row),
                  })
                }
              >
                احذف
              </Button>
            </div>
          </>
        )}
      />
      <p className="mt-10 text-11 leading-note text-muted">
        ولإضافة لافتة: تُنشأ من هنا بعنوانٍ ونافذة — وزرُّ الإضافة يفتحها
        مطفأةً حتى تُضبط، ثم تُحرَّر من «حرّر».
      </p>
      <Button
        className="mt-10"
        size="sm"
        onClick={() => {
          const now = new Date();
          const end = new Date(now.getTime() + 30 * 86400000);
          createPromoBanner({
            country_code: country,
            title: "لافتة جديدة",
            audience: "all_riders",
            starts_at: now.toISOString(),
            ends_at: end.toISOString(),
            link_kind: "none",
            is_active: false,
          })
            .then((created) => {
              load();
              setEditingBanner(created);
            })
            .catch((caught) => fail(caught, "تعذّرت الإضافة"));
        }}
      >
        أضف لافتة
      </Button>

      {deleting ? (
        <ConfirmDelete
          what={
            deleting.kind === "tile"
              ? `بلاطة «${deleting.name}»`
              : `لافتة «${deleting.name}»`
          }
          note="ولا يُحذف ما عُرض على الناس — يُخفى بدل ذلك، فحذفُه يمحو شاهداً على ما رأوه."
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            const run = deleting.run;
            setDeleting(null);
            await run();
          }}
        />
      ) : null}

      {editingTile ? (
        <TileEditor
          tile={editingTile}
          destinations={destinations}
          onClose={() => setEditingTile(null)}
          onSaved={() => {
            setEditingTile(null);
            load();
          }}
          onError={onError}
        />
      ) : null}

      {editingBanner ? (
        <BannerEditor
          banner={editingBanner}
          destinations={destinations}
          onClose={() => setEditingBanner(null)}
          onSaved={() => {
            setEditingBanner(null);
            load();
          }}
          onError={onError}
        />
      ) : null}
    </section>
  );
}

// ═══════════════════════════════════════════════════ محرّرُ البلاطة — ٧ حقول

function TileEditor({
  tile,
  destinations,
  onClose,
  onSaved,
  onError,
}: {
  tile: ServiceTileRow;
  destinations: Record<string, string[]>;
  onClose: () => void;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState({
    title: tile.title,
    subtitle: tile.subtitle ?? "",
    icon: tile.icon,
    audience: tile.audience,
    sort_order: tile.sort_order,
    destination: tile.destination ?? "",
    new_until: dateValue(tile.new_until),
  });
  const [saving, setSaving] = useState(false);

  // **ولا يُعرض مقصدٌ لا يراه جمهورُها**: `/account/bookings` مبنيٌّ عند
  // الراكب وحدَه، **وبلاطةُ كبتنٍ تشير إليه تقع على صفحةٍ مفقودة**
  const needed = rolesOf(form.audience);
  const usable = Object.entries(destinations)
    .filter(([, roles]) => needed.every((role) => roles.includes(role)))
    .map(([path]) => path);

  const preview: ServiceTileRow = {
    ...tile,
    title: form.title,
    subtitle: form.subtitle || null,
    icon: form.icon,
    new_until: form.new_until || null,
  };

  return (
    <Modal title={`تحرير «${tile.key}»`} onClose={onClose}>
      <div className="grid grid-cols-2 gap-12">
        <Field
          name="title"
          label="العنوان"
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
        <Field
          name="subtitle"
          label="سطرٌ تحته (اختياريّ)"
          value={form.subtitle}
          onChange={(e) => setForm((f) => ({ ...f, subtitle: e.target.value }))}
        />
        <Select
          name="audience"
          label="الجمهور"
          value={form.audience}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              audience: e.target.value as CampaignAudience,
              // **وتبديلُ الجمهور قد يُبطل المقصد** — فيُفرَّغ ولا يُترك
              // ليُرفض في الباب
              destination: destinations[f.destination]?.includes(
                e.target.value === "all_drivers" ? "driver" : "rider",
              )
                ? f.destination
                : "",
            }))
          }
        >
          {AUDIENCE_CHOICES.map((value) => (
            <option key={value} value={value}>
              {AUDIENCE_LABEL[value]}
            </option>
          ))}
        </Select>
        <Field
          name="sort_order"
          label="الترتيب"
          type="number"
          value={form.sort_order}
          onChange={(e) =>
            setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))
          }
        />
        <Select
          name="destination"
          label="المقصد"
          value={form.destination}
          onChange={(e) =>
            setForm((f) => ({ ...f, destination: e.target.value }))
          }
        >
          <option value="">— بلا مقصد («قريباً») —</option>
          {usable.map((path) => (
            <option key={path} value={path}>
              {path}
            </option>
          ))}
        </Select>
        <Field
          name="new_until"
          label="«جديد» حتى"
          type="date"
          value={form.new_until}
          onChange={(e) => setForm((f) => ({ ...f, new_until: e.target.value }))}
        />
      </div>

      <div className="mt-12">
        <IconPicker
          value={form.icon}
          onPick={(icon) => setForm((f) => ({ ...f, icon: icon ?? f.icon }))}
        />
      </div>

      <div className="mt-16 flex items-start gap-16">
        <PhoneFrame>
          <TilesPreview tiles={[preview]} />
        </PhoneFrame>
      </div>

      <div className="mt-16 flex gap-8">
        <Button
          loading={saving}
          onClick={() => {
            setSaving(true);
            updateServiceTile(tile.id, {
              title: form.title,
              subtitle: form.subtitle || null,
              icon: form.icon,
              audience: form.audience,
              sort_order: form.sort_order,
              destination: form.destination || null,
              new_until: form.new_until || null,
            })
              .then(onSaved)
              .catch((caught) =>
                onError(
                  caught instanceof ApiError ? caught.message : "تعذّر الحفظ",
                ),
              )
              .finally(() => setSaving(false));
          }}
        >
          احفظ
        </Button>
        <Button variant="ghost" onClick={onClose}>
          إلغاء
        </Button>
      </div>
    </Modal>
  );
}

// ═══════════════════════════════════════════════════ محرّرُ اللافتة — ٩ حقول

function BannerEditor({
  banner,
  destinations,
  onClose,
  onSaved,
  onError,
}: {
  banner: PromoBannerRow;
  destinations: Record<string, string[]>;
  onClose: () => void;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState({
    title: banner.title,
    body: banner.body ?? "",
    icon: banner.icon,
    audience: banner.audience,
    sort_order: banner.sort_order,
    starts_at: localValue(banner.starts_at),
    ends_at: localValue(banner.ends_at),
    link_kind: banner.link_kind,
    link: banner.link ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [imageAt, setImageAt] = useState(0);

  const preview: PromoBannerRow = {
    ...banner,
    title: form.title,
    body: form.body || null,
    icon: form.icon,
  };

  return (
    <Modal title="تحرير اللافتة" onClose={onClose}>
      <div className="grid grid-cols-2 gap-12">
        <Field
          name="title"
          label="العنوان"
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
        <Field
          name="body"
          label="النص (اختياريّ)"
          value={form.body}
          onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
        />
        <Select
          name="audience"
          label="الجمهور"
          value={form.audience}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              audience: e.target.value as CampaignAudience,
            }))
          }
        >
          {AUDIENCE_CHOICES.map((value) => (
            <option key={value} value={value}>
              {AUDIENCE_LABEL[value]}
            </option>
          ))}
        </Select>
        <Field
          name="sort_order"
          label="الترتيب"
          type="number"
          value={form.sort_order}
          onChange={(e) =>
            setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))
          }
        />
        <Field
          name="starts_at"
          label="من"
          type="datetime-local"
          value={form.starts_at}
          onChange={(e) => setForm((f) => ({ ...f, starts_at: e.target.value }))}
        />
        <Field
          name="ends_at"
          label="إلى (إلزاميّة)"
          type="datetime-local"
          value={form.ends_at}
          onChange={(e) => setForm((f) => ({ ...f, ends_at: e.target.value }))}
        />
        <Select
          name="link_kind"
          label="ما تفتحه"
          value={form.link_kind}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              link_kind: e.target.value as PromoBannerRow["link_kind"],
              link: e.target.value === "none" ? "" : f.link,
            }))
          }
        >
          <option value="none">لا شيء</option>
          <option value="internal">شاشةٌ في التطبيق</option>
          <option value="external">رابطٌ خارجيّ</option>
        </Select>
        {form.link_kind === "internal" ? (
          <Select
            name="link"
            label="الشاشة"
            value={form.link}
            onChange={(e) => setForm((f) => ({ ...f, link: e.target.value }))}
          >
            <option value="">— اختر —</option>
            {Object.keys(destinations).map((path) => (
              <option key={path} value={path}>
                {path}
              </option>
            ))}
          </Select>
        ) : form.link_kind === "external" ? (
          <Field
            name="link"
            label="العنوان"
            dir="ltr"
            value={form.link}
            onChange={(e) => setForm((f) => ({ ...f, link: e.target.value }))}
          />
        ) : (
          <div />
        )}
      </div>

      <div className="mt-12">
        <IconPicker
          value={form.icon}
          clearable
          onPick={(icon) => setForm((f) => ({ ...f, icon }))}
        />
      </div>

      {/* ─────────────── الصورة: رفعٌ ونزع */}
      <div className="mt-14 border-t border-line pt-14">
        <div className="label">صورةُ اللافتة</div>
        <div className="mt-6 flex items-center gap-8">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="text-11.5 text-muted"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              uploadBannerImage(banner.id, file)
                // **ومفتاحُ المعاينة يتغيّر** — وإلا عرض المتصفحُ الصورةَ
                // القديمةَ من ذاكرته تحت العنوان نفسِه
                .then(() => setImageAt((n) => n + 1))
                .catch((caught) =>
                  onError(
                    caught instanceof ApiError ? caught.message : "تعذّر الرفع",
                  ),
                );
            }}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              deleteBannerImage(banner.id)
                .then(() => setImageAt((n) => n + 1))
                .catch((caught) =>
                  onError(
                    caught instanceof ApiError ? caught.message : "لا صورة",
                  ),
                );
            }}
          >
            انزع الصورة
          </Button>
        </div>
        <p className="mt-6 text-11 leading-note text-muted">
          تمرّ بالفحص نفسِه الذي تمرّ به المستندات: النوعُ من بايتات الملفّ لا
          من اسمه، والحجمُ بالقراءة. وتظهر في المعاينة أسفلَه.
        </p>
      </div>

      <div className="mt-16">
        <PhoneFrame>
          <BannerPreview key={imageAt} banner={preview} />
        </PhoneFrame>
      </div>

      <div className="mt-16 flex gap-8">
        <Button
          loading={saving}
          onClick={() => {
            setSaving(true);
            updatePromoBanner(banner.id, {
              title: form.title,
              body: form.body || null,
              icon: form.icon,
              audience: form.audience,
              sort_order: form.sort_order,
              starts_at: new Date(form.starts_at).toISOString(),
              ends_at: new Date(form.ends_at).toISOString(),
              link_kind: form.link_kind,
              link: form.link || null,
            })
              .then(onSaved)
              .catch((caught) =>
                onError(
                  caught instanceof ApiError ? caught.message : "تعذّر الحفظ",
                ),
              )
              .finally(() => setSaving(false));
          }}
        >
          احفظ
        </Button>
        <Button variant="ghost" onClick={onClose}>
          إلغاء
        </Button>
      </div>
    </Modal>
  );
}
