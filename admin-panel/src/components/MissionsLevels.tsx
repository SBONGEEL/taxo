/** المهامُّ والمستوياتُ والشارات في اللوحة (البند ٥٣، §٦).
 *
 * **ولا زرَّ «ارفع مستوى هذا الكبتن» هنا ولا في أي مكان**: المستوى حكمٌ آليٌّ
 * على أداءٍ مقيس، وزرٌّ يرفعه بيدٍ يجعله محاباةً في **ترتيب التوزيع** — أي في
 * المال. ومن أراد تقديراً فبابُه الشارة، وهي لا تدخل التوزيع أصلاً.
 *
 * **وحقلُ الأثر يقول ما يفعله بالأمتار**: «١٠٠م» رقمٌ يُقاس، وقائمةٌ مكتوب
 * فيها «أولوية عالية» تجعل المشرفَ يظنّ أنه يوزّع طلباتٍ لا أمتاراً.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createBadge,
  createMission,
  getLevelOverview,
  deleteBadge,
  deleteMission,
  listBadges,
  listMissions,
  setLevelEffect,
  updateMission,
} from "@/api/endpoints";
import type { Badge as BadgeRow, LevelOverview, Mission } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { ConfirmDelete } from "@/components/ui/ConfirmDelete";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { day } from "@/lib/format";
import { digits } from "@/lib/utils";

const LEVEL_LABEL = ["مبتدئ", "فضّي", "ذهبي", "ماسيّ"];

/** **معياران لا ثلاثة**: `active_hours` يحتاج التقاطاً جديداً لا يوجد اليوم،
 *  ومعيارٌ يقيس من لا شيء يُعرض للكباتن ولا يُنجَز أبداً. */
const METRICS: { value: string; label: string }[] = [
  { value: "completed_rides", label: "رحلات مكتملة" },
  { value: "min_rating", label: "حدٌّ أدنى للتقييم" },
];

function thisMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

/** سلَّمُ مستويات الكبتن — **مرآةُ `MAX_LEVEL = 3` في `models/mission.py`**.
 *
 * **ثابتُ خلفيةٍ لا إعداد**: لا بابَ ينشره ولا شاشةَ تضبطه، **ومفتاحٌ في
 * `/config` له كان سيَعِد بضبطٍ لا يقع**. ومكانُه هنا لا في `labels.ts` —
 * **وذلك الملفُّ يقول بنفسه إن ثوابتَ الخلفية لا تسكنه**.
 *
 * **وبيتُه واحدٌ منذ اليومَ**: كان مكتوباً هنا `[0, 1, 2, 3]` **ويُكتب رقماً
 * حرّاً في متجر المركبات** — فمن كتب `7` هناك صنع مركبةً لا يبلغها أحدٌ أبداً،
 * **ولا يصيح شيء**: الخلفيةُ تقبل كلَّ `> 0`.
 */
export const DRIVER_LEVELS = [0, 1, 2, 3];

export function MissionsLevels({
  onError,
  isAdmin,
}: {
  onError: (message: string) => void;
  isAdmin: boolean;
}) {
  const { country } = useCountry();
  const [missions, setMissions] = useState<Mission[] | null>(null);
  const [levels, setLevels] = useState<LevelOverview | null>(null);
  const [badges, setBadges] = useState<BadgeRow[]>([]);
  // **صفٌّ واحدٌ ينتظر التأكيد** — والنوعُ معه لأن الورقةَ واحدةٌ لكيانين
  const [deleting, setDeleting] = useState<
    { kind: "mission" | "badge"; id: string; name: string } | null
  >(null);

  const load = useCallback(async () => {
    const [m, l, b] = await Promise.all([
      listMissions(country),
      getLevelOverview(country),
      listBadges(),
    ]);
    setMissions(m);
    setLevels(l);
    setBadges(b);
  }, [country]);

  useEffect(() => {
    load().catch((caught) =>
      onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المهام"),
    );
  }, [load, onError]);

  if (missions === null || levels === null) return <Spinner />;

  return (
    <div className="mt-24 space-y-20">
      {/* ------------------------------------------------------ المستويات */}
      <section>
        <h2 className="mb-4 text-15 font-bold text-ink">المستويات</h2>
        <p className="mb-10 text-12 leading-relaxed text-muted">
          المستوى يُحسب كلَّ ساعة من مهامِّ الشهر — <b className="text-ink">لا يُمنح
          بيد</b>. وأثرُه <b className="text-ink">خصمٌ بالأمتار على مسافة البحث</b>:
          الأقربُ يبقى الأوّلَ، والمستوى يفصل بين المتقاربين وحدهم. والحدُّ الأقصى
          100م، وصفرٌ يعني «بلا أثر».
          {levels.last_computed_at ? (
            <> آخرُ حساب: {day(levels.last_computed_at)}.</>
          ) : (
            <> لم يُحسب بعد.</>
          )}
          {!levels.enabled ? (
            <b className="text-warn"> والمفتاحُ مطفأٌ الآن، فلا مستوىً يُحسب.</b>
          ) : null}
        </p>

        <div className="grid gap-10 md:grid-cols-4">
          {DRIVER_LEVELS.map((level) => {
            const setting = levels.settings.find((row) => row.level === level);
            return (
              <LevelCard
                key={level}
                level={level}
                meters={setting?.discount_meters ?? 0}
                count={levels.counts[String(level)] ?? 0}
                disabled={!isAdmin}
                onSaved={() => void load()}
                onError={onError}
                country={country}
              />
            );
          })}
        </div>
      </section>

      {/* -------------------------------------------------------- المهامّ */}
      <section>
        <h2 className="mb-4 text-15 font-bold text-ink">مهامُّ الشهر</h2>
        <p className="mb-10 text-12 leading-relaxed text-muted">
          معيارٌ واحدٌ لا يتكرر في شهرٍ واحد. و
          <b className="text-ink">تعديلُ الهدف يعيد تقييمَ الجميع فوراً</b> — ولا
          يمسّ صفَّ أحد: التقدّمُ مقيسٌ حيّاً لا مراكمٌ في عمود.
        </p>

        {isAdmin ? (
          <MissionComposer
            country={country}
            onCreated={() => void load()}
            onError={onError}
          />
        ) : null}

        {missions.length === 0 ? (
          <p className="rounded-13 border border-line p-14 text-12.5 text-muted">
            لا مهامَّ في هذا السوق بعد.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-13 border border-line">
            <table className="w-full min-w-[640px] text-12.5">
              <thead>
                <tr className="border-b border-line bg-surface-2 text-muted">
                  <th className="p-8 text-start font-semibold">الشهر</th>
                  <th className="p-8 text-start font-semibold">المهمة</th>
                  <th className="p-8 text-start font-semibold">المعيار</th>
                  <th className="p-8 text-start font-semibold">الهدف</th>
                  <th className="p-8 text-start font-semibold">الحالة</th>
                  <th className="p-8 text-start font-semibold" />
                </tr>
              </thead>
              <tbody>
                {missions.map((row) => (
                  <tr key={row.id} className="border-b border-line last:border-0">
                    <td className="p-8 text-muted" dir="ltr">
                      {row.month.slice(0, 7)}
                    </td>
                    <td className="p-8 font-medium text-ink">{row.title}</td>
                    <td className="p-8 text-muted">
                      {METRICS.find((m) => m.value === row.metric)?.label ??
                        row.metric}
                    </td>
                    <td className="p-8 text-ink">{digits(row.target)}</td>
                    <td className="p-8">
                      <Badge tone={row.is_active ? "ok" : "muted"}>
                        {row.is_active ? "مفعّلة" : "موقوفة"}
                      </Badge>
                    </td>
                    <td className="p-8">
                      {isAdmin ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            updateMission(row.id, { is_active: !row.is_active })
                              .then(() => void load())
                              .catch((caught) =>
                                onError(
                                  caught instanceof ApiError
                                    ? caught.message
                                    : "تعذّر الحفظ",
                                ),
                              );
                          }}
                        >
                          {row.is_active ? "أوقف" : "فعّل"}
                        </Button>
                      ) : null}
                      {/* **الحذفُ لِما لم يبدأ شهرُه** (§39٫٤): ما بدأ يعمل
                          عليه كباتنُ الآن — يُوقَف ولا يُمحى */}
                      {isAdmin ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-danger"
                          onClick={() => setDeleting({ kind: "mission", id: row.id, name: row.title })}
                        >
                          احذف
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------- الشارات */}
      <section>
        <h2 className="mb-4 text-15 font-bold text-ink">الشارات</h2>
        <p className="mb-10 text-12 leading-relaxed text-muted">
          تقديرٌ إنسانيٌّ لما لا يُقاس — <b className="text-ink">ولا تدخل ترتيبَ
          التوزيع بحال</b>. ومنحُها من صفحة الكبتن بسببٍ مكتوب يدخل سجلَّ التدقيق.
        </p>
        {isAdmin ? (
          <BadgeComposer onCreated={() => void load()} onError={onError} />
        ) : null}
        {badges.length === 0 ? (
          <p className="rounded-13 border border-line p-14 text-12.5 text-muted">
            لا شاراتٍ في الكتالوج بعد.
          </p>
        ) : (
          <div className="flex flex-wrap gap-8">
            {badges.map((badge) => (
              <span
                key={badge.id}
                className="rounded-13 border border-line bg-surface-2 px-10 py-8 text-12.5 text-ink"
              >
                {badge.label}
                <span className="ms-6 text-11 text-muted" dir="ltr">
                  {badge.key}
                </span>
                {/* **والحذفُ لِما لم يُمنح** (§39٫٤): `CASCADE` كان سيمحو
                    المنحَ معها صامتاً — ومنحةٌ ممحوّةٌ تمحو خبراً عن إنسان */}
                {isAdmin ? (
                  <button
                    type="button"
                    className="ms-8 text-11 font-bold text-danger"
                    onClick={() => setDeleting({ kind: "badge", id: badge.id, name: badge.label })}
                  >
                    احذف
                  </button>
                ) : null}
              </span>
            ))}
          </div>
        )}
      </section>

      {deleting ? (
        <ConfirmDelete
          what={
            deleting.kind === "mission"
              ? `مهمّة «${deleting.name}»`
              : `شارة «${deleting.name}»`
          }
          note={
            deleting.kind === "mission"
              ? "ولا تُحذف مهمّةٌ بدأ شهرُها — يعمل عليها كباتنُ الآن، والبديلُ إيقافُها."
              : "ولا تُحذف شارةٌ مُنحت لأحد — ومنحةٌ ممحوّةٌ تمحو خبراً عن إنسان."
          }
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            try {
              if (deleting.kind === "mission") {
                await deleteMission(deleting.id);
              } else {
                await deleteBadge(deleting.id);
              }
              setDeleting(null);
              await load();
            } catch (caught) {
              onError(
                caught instanceof ApiError ? caught.message : "تعذّر الحذف",
              );
              setDeleting(null);
            }
          }}
        />
      ) : null}
    </div>
  );
}

function LevelCard({
  level,
  meters,
  count,
  disabled,
  country,
  onSaved,
  onError,
}: {
  level: number;
  meters: number;
  count: number;
  disabled: boolean;
  country: Parameters<typeof setLevelEffect>[0];
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [value, setValue] = useState(String(meters));
  const [busy, setBusy] = useState(false);

  useEffect(() => setValue(String(meters)), [meters]);

  return (
    <div className="rounded-13 border border-line p-12">
      <p className="text-13 font-bold text-ink">{LEVEL_LABEL[level]}</p>
      <p className="mt-2 text-11 text-muted">
        {digits(String(count))} كبتناً
      </p>
      <Field
        className="mt-8"
        label="الأثر (متر)"
        dir="ltr"
        inputMode="numeric"
        value={value}
        disabled={disabled}
        onChange={(event) => setValue(event.target.value.replace(/[^0-9]/g, ""))}
      />
      <Button
        className="mt-8 w-full"
        size="sm"
        variant="ghost"
        disabled={disabled || value === "" || value === String(meters)}
        loading={busy}
        onClick={() => {
          setBusy(true);
          setLevelEffect(country, level, Number(value))
            .then(onSaved)
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </div>
  );
}

function MissionComposer({
  country,
  onCreated,
  onError,
}: {
  country: Parameters<typeof createMission>[0];
  onCreated: () => void;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [metric, setMetric] = useState(METRICS[0].value);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div className="mb-12 grid gap-10 rounded-13 border border-line p-14 md:grid-cols-4">
      <Field
        label="عنوان المهمة"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <Select
        label="المعيار"
        value={metric}
        onChange={(event) => setMetric(event.target.value)}
      >
        {METRICS.map((row) => (
          <option key={row.value} value={row.value}>
            {row.label}
          </option>
        ))}
      </Select>
      <Field
        label="الهدف"
        dir="ltr"
        inputMode="decimal"
        value={target}
        onChange={(event) => setTarget(event.target.value.replace(/[^0-9.]/g, ""))}
      />
      <Button
        className="self-end"
        size="sm"
        disabled={title.trim().length < 2 || target === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          createMission(country, {
            month: thisMonth(),
            title: title.trim(),
            metric,
            target,
          })
            .then(() => {
              setTitle("");
              setTarget("");
              onCreated();
            })
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الإنشاء"),
            )
            .finally(() => setBusy(false));
        }}
      >
        أضف لهذا الشهر
      </Button>
    </div>
  );
}

function BadgeComposer({
  onCreated,
  onError,
}: {
  onCreated: () => void;
  onError: (message: string) => void;
}) {
  const [key, setKey] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div className="mb-12 grid gap-10 rounded-13 border border-line p-14 md:grid-cols-3">
      <Field
        label="المفتاح (لاتيني)"
        dir="ltr"
        value={key}
        onChange={(event) =>
          setKey(event.target.value.replace(/[^a-zA-Z0-9_]/g, "").toLowerCase())
        }
      />
      <Field
        label="الاسم المعروض"
        value={label}
        onChange={(event) => setLabel(event.target.value)}
      />
      <Button
        className="self-end"
        size="sm"
        disabled={key.length < 2 || label.trim().length < 2}
        loading={busy}
        onClick={() => {
          setBusy(true);
          createBadge({ key, label: label.trim() })
            .then(() => {
              setKey("");
              setLabel("");
              onCreated();
            })
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الإنشاء"),
            )
            .finally(() => setBusy(false));
        }}
      >
        أضف شارة
      </Button>
    </div>
  );
}
