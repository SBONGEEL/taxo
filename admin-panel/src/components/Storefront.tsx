/** بلاطاتُ الخدمات ولافتاتُ المحتوى — **تُدار من هنا بلا نشر** (`0063`).
 *
 * **ولا زرَّ حذف**: البلاطةُ تُخفى واللافتةُ تُطفأ — **وحذفُ صفٍّ يمحو ما
 * بُني عليه ترتيبٌ وقياس**، وهي قاعدةُ «الإيقافُ تعليقٌ لا حذف» نفسُها.
 *
 * **والإشعالُ بلا مقصدٍ مبنيٍّ يمنعه الخادمُ بنصّه** — والشاشةُ لا تكرّر
 * الشرط: **شرطان لقاعدةٍ واحدةٍ يفترقان**، والرسالةُ تأتي من حيث تُحرس.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createPromoBanner,
  createServiceTile,
  listPromoBanners,
  listServiceTiles,
  updatePromoBanner,
  updateServiceTile,
} from "@/api/endpoints";
import type { CountryCode, PromoBannerRow, ServiceTileRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Table } from "@/components/Table";
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

export function Storefront({
  country,
  onError,
}: {
  country: CountryCode;
  onError: (message: string) => void;
}) {
  const [tiles, setTiles] = useState<ServiceTileRow[]>([]);
  const [banners, setBanners] = useState<PromoBannerRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [draft, setDraft] = useState({ key: "", title: "", icon: "package" });

  const load = useCallback(() => {
    Promise.all([listServiceTiles(country), listPromoBanners(country)])
      .then(([t, b]) => {
        setTiles(t);
        setBanners(b);
      })
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [country, onError]);

  useEffect(load, [load]);

  async function patchTile(row: ServiceTileRow, changes: Partial<ServiceTileRow>) {
    setBusy(row.id);
    try {
      await updateServiceTile(row.id, changes);
      load();
    } catch (caught) {
      // **رسالةُ الخادم كما هي** — هو من يعرف لمَ مُنع
      onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">خدمات الشاشة الرئيسة</h2>
      <p className="mb-12 text-12 text-muted">
        بلاطاتُ الرئيسية للراكب والكبتن — تُضاف وتُشعل وتُخفى من هنا بلا نشر.
        و«قريباً» تظهر بعلامتها ولا تفتح باباً. و«فعّالة» لا تُقبل بلا مقصد
        مبنيّ في التطبيق — يمنعها الخادم بعلّته.
      </p>

      <Table
        columns="0.8fr 1.1fr 0.8fr 0.7fr 1.2fr 1.4fr"
        headers={["المفتاح", "العنوان", "الجمهور", "الترتيب", "المقصد", ""]}
        rows={tiles}
        keyOf={(row) => row.id}
        empty={{ title: "لا خدمات", hint: "لم تُضف بلاطةٌ لهذا السوق بعد." }}
        render={(row) => (
          <>
            <span className="font-mono text-11.5">{row.key}</span>
            <span className="text-12 text-ink">{row.title}</span>
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
            </div>
          </>
        )}
      />

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
        <Field
          name="tile_icon"
          label="أيقونة lucide"
          value={draft.icon}
          onChange={(event) =>
            setDraft((d) => ({ ...d, icon: event.target.value }))
          }
        />
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
              audience: "all_riders",
              status: "hidden",
            })
              .then(() => {
                setDraft({ key: "", title: "", icon: "package" });
                load();
              })
              .catch((caught) =>
                onError(
                  caught instanceof ApiError ? caught.message : "تعذّرت الإضافة",
                ),
              );
          }}
        >
          أضف خدمة
        </Button>
      </div>

      <h3 className="mb-6 mt-20 text-13 font-bold text-ink">لافتات المحتوى</h3>
      <p className="mb-10 text-11 leading-snug text-muted">
        بطاقةٌ في الرئيسية بنافذةِ عرضٍ إلزاميّة — تختفي بانقضائها بلا نشر.
        والنافذةُ تُقاس في الخادم لا في الجهاز.
      </p>
      <Table
        columns="1.4fr 0.8fr 1fr 1fr 0.9fr"
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
            <Button
              size="sm"
              variant="secondary"
              loading={busy === row.id}
              onClick={() => {
                setBusy(row.id);
                updatePromoBanner(row.id, { is_active: !row.is_active })
                  .then(load)
                  .catch((caught) =>
                    onError(
                      caught instanceof ApiError
                        ? caught.message
                        : "تعذّر التبديل",
                    ),
                  )
                  .finally(() => setBusy(null));
              }}
            >
              {row.is_active ? "أطفئ" : "أشعل"}
            </Button>
          </>
        )}
      />
      <p className="mt-10 text-11 leading-note text-muted">
        ولإضافة لافتة: تُنشأ من هنا بعنوانٍ ونافذة — وزرُّ الإضافة يفتحها
        مطفأةً حتى تُضبط.
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
            .then(load)
            .catch((caught) =>
              onError(
                caught instanceof ApiError ? caught.message : "تعذّرت الإضافة",
              ),
            );
        }}
      >
        أضف لافتة
      </Button>
    </section>
  );
}
