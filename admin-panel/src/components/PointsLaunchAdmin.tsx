/** **نقاطُ الالتزام · حملةُ الإطلاق · عروضُ الركّاب** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-ب/ج/د) — لكلِّ دولةٍ بمفتاحها.
 *
 * **القيمُ يضعها المالك**: نقاطُ اليوم وقيمةُ التحويل والسقوفُ ومددُ الصلاحيّة **فارغةٌ حتى يكتبها** — والخلفيّةُ ترفض الإشعالَ بلا
 * قيمها. **وكلُّ حفظٍ يُكتب في سجلّ التدقيق**، والأرصدةُ وأيّامُ الالتزام والمنحُ **من الخلفيّة** — لا جمعَ ولا طرحَ هنا.
 */

import { useCallback, useEffect, useState } from "react";

import {
  createPartnerCoupon,
  getCaptainDiscounts,
  getCommitmentDriverDays,
  getCommitmentFlags,
  getCommitmentReport,
  getCommitmentRule,
  getLaunchCampaign,
  getLaunchGrants,
  getRiderPerks,
  listPartnerCoupons,
  updateCommitmentRule,
  updateLaunchCampaign,
  updatePartnerCoupon,
  updateRiderPerks,
  type CaptainDiscounts,
  type CommitmentReportRow,
  type CommitmentRule,
  type DutyDayAdmin,
  type LaunchCampaignAdmin,
  type LaunchGrantRow,
  type PartnerCoupon,
  type RiderPerks,
} from "@/api/endpoints";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { currencyOf, money, moment } from "@/lib/format";
import { digits } from "@/lib/utils";

const numeric = (value: string) => value.replace(/[^0-9.]/g, "");
const thisMonth = () => `${new Date().toISOString().slice(0, 7)}-01`;

/** **حقولُ القاعدة الرقميّة** — والفارغُ في القابل للتفريغ يُرسل في `clear` («بلا حدّ» أو «لم يُضبط»). */
const RULE_FIELDS: { key: keyof CommitmentRule; label: string; clearable: boolean; decimal?: boolean }[] = [
  { key: "span_minutes", label: "المدّة (دقائق)", clearable: false },
  { key: "max_break_minutes", label: "أطول استراحة (دقائق)", clearable: false },
  { key: "max_total_break_minutes", label: "مجموع الاستراحات (دقائق)", clearable: false },
  { key: "points_per_day", label: "نقاط اليوم", clearable: true },
  { key: "points_per_credit_unit", label: "نقاط وحدة التحويل", clearable: true },
  { key: "credit_unit_value", label: "قيمة وحدة التحويل", clearable: true, decimal: true },
  { key: "daily_points_cap", label: "سقف يوميّ للنقاط", clearable: true },
  { key: "monthly_points_cap", label: "سقف شهريّ للنقاط", clearable: true },
  { key: "points_expiry_days", label: "صلاحيّة النقاط (أيام)", clearable: true },
  { key: "credit_expiry_days", label: "صلاحيّة الرصيد (أيام)", clearable: true },
  { key: "max_accounts_per_device", label: "حسابات كابتن لكلّ جهاز", clearable: false },
];

const STATUS_LABEL: Record<string, string> = { met: "تحقّق", not_met: "لم يتحقّق", disqualified: "أُسقط" };

function CommitmentSection({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const [rule, setRule] = useState<CommitmentRule | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [hours, setHours] = useState({ start: "", end: "" });
  const [report, setReport] = useState<CommitmentReportRow[]>([]);
  const [flags, setFlags] = useState<DutyDayAdmin[]>([]);
  const [days, setDays] = useState<{ driver: string; rows: DutyDayAdmin[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const currency = currencyOf(country);

  const fill = (row: CommitmentRule) => {
    setRule(row);
    setDraft(Object.fromEntries(RULE_FIELDS.map((f) => [f.key, row[f.key] === null ? "" : String(row[f.key])])));
    setHours({ start: row.window_start.slice(0, 5), end: row.window_end.slice(0, 5) });
  };

  const load = useCallback(() => {
    getCommitmentRule(country).then(fill).catch((caught: Error) => onError(caught.message));
    getCommitmentReport(country, thisMonth()).then(setReport).catch((caught: Error) => onError(caught.message));
    getCommitmentFlags(country).then(setFlags).catch((caught: Error) => onError(caught.message));
  }, [country, onError]);
  useEffect(load, [load]);

  const save = (extra: Record<string, unknown> = {}) => {
    if (!rule) return;
    const payload: Record<string, unknown> = { ...extra };
    const clear: string[] = [];
    for (const field of RULE_FIELDS) {
      const value = draft[field.key] ?? "";
      const before = rule[field.key] === null ? "" : String(rule[field.key]);
      if (value === before) continue;
      if (value === "") {
        if (field.clearable) clear.push(field.key);
        continue;
      }
      payload[field.key] = field.decimal ? value : Number(value);
    }
    if (hours.start && hours.start !== rule.window_start.slice(0, 5)) payload.window_start = hours.start;
    if (hours.end && hours.end !== rule.window_end.slice(0, 5)) payload.window_end = hours.end;
    payload.clear = clear;
    setBusy(true);
    updateCommitmentRule(country, payload)
      .then(fill)
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  const openDays = (driverId: string) =>
    getCommitmentDriverDays(driverId)
      .then((rows) => setDays({ driver: driverId, rows }))
      .catch((caught: Error) => onError(caught.message));

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="commitment-admin-title">
      <h2 id="commitment-admin-title" className="text-15 font-bold text-ink">
        نقاط الالتزام{" "}
        {rule ? <Badge tone={rule.is_enabled ? "ok" : "muted"}>{rule.is_enabled ? "مشتعل" : "مطفأ"}</Badge> : null}
      </h2>
      <p className="mt-4 text-11 leading-snug text-muted">
        يومٌ يُحتسب لمن عمل المدّةَ متّصلةً داخل النافذة، باستراحاتٍ لا تتجاوز حدَّيها — ولو بلا رحلة. النقاطُ تتحوّل إلى «رصيد اشتراك»
        يدفع اشتراك TAXO وحدَه، لا يُسحب ولا يُحوَّل. يُسقط اليومُ بمحاكٍ أو موقعٍ وهميّ أو جهازٍ بأكثر من الحدّ من الحسابات، وتُعلَّم
        الأيّامُ المريبة هنا. لا يُشعَل قبل كتابة نقاط اليوم وقيمة التحويل.
      </p>
      {rule ? (
        <div className="mt-12 grid grid-cols-2 gap-10 md:grid-cols-4">
          <Field name="cm_window_start" label="بداية النافذة" dir="ltr" value={hours.start} disabled={!isAdmin}
            onChange={(e) => setHours({ ...hours, start: e.target.value })} />
          <Field name="cm_window_end" label="نهاية النافذة" dir="ltr" value={hours.end} disabled={!isAdmin}
            onChange={(e) => setHours({ ...hours, end: e.target.value })} />
          {RULE_FIELDS.map((field) => (
            <Field
              key={field.key}
              name={`cm_${field.key}`}
              label={field.key === "credit_unit_value" && currency ? `${field.label} (${currency})` : field.label}
              dir="ltr"
              inputMode={field.decimal ? "decimal" : "numeric"}
              value={draft[field.key] ?? ""}
              disabled={!isAdmin}
              onChange={(e) => setDraft({ ...draft, [field.key]: numeric(e.target.value) })}
            />
          ))}
        </div>
      ) : null}
      {rule && isAdmin ? (
        <div className="mt-10 flex flex-wrap gap-8">
          <Button size="sm" loading={busy} onClick={() => save()}>
            حفظ القواعد
          </Button>
          <Button size="sm" variant="secondary" loading={busy}
            onClick={() => save({ require_service_area: !rule.require_service_area })}>
            {rule.require_service_area ? "إلغاء شرط منطقة الخدمة" : "اشتراط منطقة الخدمة"}
          </Button>
          <Button size="sm" variant={rule.is_enabled ? "secondary" : undefined} loading={busy}
            onClick={() => save({ is_enabled: !rule.is_enabled })}>
            {rule.is_enabled ? "إطفاء" : "إشعال"}
          </Button>
        </div>
      ) : null}

      <h3 className="mt-16 text-13 font-bold text-ink">تقرير الشهر لكلّ كابتن</h3>
      <ul className="mt-8 space-y-6">
        {report.map((row) => (
          <li key={row.driver_id} className="flex flex-wrap items-center justify-between gap-8 border-t border-line pt-6 text-12">
            <span>
              <span className="font-semibold text-ink">{row.driver_name ?? row.driver_id.slice(0, 8)}</span>{" "}
              تحقّق {digits(String(row.met))} · أُسقط {digits(String(row.disqualified))} · لم يتحقّق {digits(String(row.not_met))}
              {row.flagged ? ` · مُعلَّم ${digits(String(row.flagged))}` : ""} · نقاط {digits(String(row.points_balance))} · رصيد{" "}
              {money(row.credit_balance, currency)}
            </span>
            <Button size="sm" variant="secondary" onClick={() => void openDays(row.driver_id)}>
              الأيّام
            </Button>
          </li>
        ))}
        {report.length === 0 ? <li className="text-12 text-muted">لا أيّامَ هذا الشهر.</li> : null}
      </ul>
      {days ? (
        <ul className="mt-8 space-y-4 rounded-card bg-canvas p-10 text-11">
          {days.rows.map((day) => (
            <li key={day.id}>
              {digits(day.day)} · {STATUS_LABEL[day.status] ?? day.status} · {digits(String(day.online_minutes))} دقيقة متّصلاً ·
              استراحات {digits(String(day.total_break_minutes))} · رحلات {digits(String(day.rides_completed))}
              {day.reason ? ` · ${day.reason}` : ""}
              {day.flags.length ? ` · ⚑ ${day.flags.join("، ")}` : ""}
            </li>
          ))}
        </ul>
      ) : null}

      <h3 className="mt-16 text-13 font-bold text-ink">أيّامٌ مُعلَّمة</h3>
      <ul className="mt-8 space-y-4 text-11">
        {flags.map((day) => (
          <li key={day.id}>
            {digits(day.day)} · {day.driver_id.slice(0, 8)} · {STATUS_LABEL[day.status] ?? day.status} · ⚑ {day.flags.join("، ")}
          </li>
        ))}
        {flags.length === 0 ? <li className="text-muted">لا شيء.</li> : null}
      </ul>
    </section>
  );
}

function LaunchSection({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const [campaign, setCampaign] = useState<LaunchCampaignAdmin | null>(null);
  const [form, setForm] = useState({ date: "", pre: "", post: "" });
  const [grants, setGrants] = useState<LaunchGrantRow[]>([]);
  const [busy, setBusy] = useState(false);

  const fill = (row: LaunchCampaignAdmin) => {
    setCampaign(row);
    setForm({ date: row.launch_date, pre: String(row.pre_launch_free_days), post: String(row.post_launch_free_days) });
  };
  const load = useCallback(() => {
    getLaunchCampaign(country).then(fill).catch((caught: Error) => onError(caught.message));
    getLaunchGrants(country).then(setGrants).catch((caught: Error) => onError(caught.message));
  }, [country, onError]);
  useEffect(load, [load]);

  const save = (extra: Record<string, unknown> = {}) => {
    setBusy(true);
    updateLaunchCampaign(country, {
      launch_date: form.date,
      pre_launch_free_days: Number(form.pre),
      post_launch_free_days: Number(form.post),
      ...extra,
    })
      .then(fill)
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="launch-admin-title">
      <h2 id="launch-admin-title" className="text-15 font-bold text-ink">
        حملة الإطلاق{" "}
        {campaign ? <Badge tone={campaign.enabled ? "ok" : "muted"}>{campaign.enabled ? "مشتعلة" : "مطفأة"}</Badge> : null}
      </h2>
      <p className="mt-4 text-11 leading-snug text-muted">
        كابتنٌ اعتُمد قبل الإطلاق: اشتراكٌ مجّانيٌّ من يوم الإطلاق. وبعده: من يوم اعتماده. بلا مالٍ، وبعمولة صفر إن اختير ذلك، ويُكتب كلُّ
        منحٍ في السجلّ. وفي الفترة المجّانية يتحمّل الكابتنُ خصومَ عروض الركّاب بعد إقراره في التطبيق.
      </p>
      {campaign ? (
        <>
          <div className="mt-12 grid grid-cols-2 gap-10 md:grid-cols-3">
            <Field name="lc_date" label="يوم الإطلاق" dir="ltr" value={form.date} disabled={!isAdmin}
              onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <Field name="lc_pre" label="أيام قبل الإطلاق" dir="ltr" inputMode="numeric" value={form.pre} disabled={!isAdmin}
              onChange={(e) => setForm({ ...form, pre: numeric(e.target.value) })} />
            <Field name="lc_post" label="أيام بعد الإطلاق" dir="ltr" inputMode="numeric" value={form.post} disabled={!isAdmin}
              onChange={(e) => setForm({ ...form, post: numeric(e.target.value) })} />
          </div>
          <p className="mt-8 text-12 text-ink">«{campaign.banner}»</p>
          {isAdmin ? (
            <div className="mt-10 flex flex-wrap gap-8">
              <Button size="sm" loading={busy} onClick={() => save()}>
                حفظ
              </Button>
              <Button size="sm" variant="secondary" loading={busy}
                onClick={() => save({ zero_commission: !campaign.zero_commission })}>
                {campaign.zero_commission ? "عمولة صفر: نعم" : "عمولة صفر: لا"}
              </Button>
              <Button size="sm" variant="secondary" loading={busy} onClick={() => save({ show_banner: !campaign.show_banner })}>
                {campaign.show_banner ? "إخفاء اللافتة" : "إظهار اللافتة"}
              </Button>
              <Button size="sm" variant={campaign.enabled ? "secondary" : undefined} loading={busy}
                onClick={() => save({ is_enabled: !campaign.enabled })}>
                {campaign.enabled ? "إطفاء" : "إشعال"}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
      <h3 className="mt-16 text-13 font-bold text-ink">المنح</h3>
      <ul className="mt-8 space-y-4 text-11">
        {grants.map((grant) => (
          <li key={grant.driver_id}>
            {grant.driver_name ?? grant.driver_id.slice(0, 8)} · {grant.kind === "pre" ? "قبل الإطلاق" : "بعد الإطلاق"} ·{" "}
            {moment(grant.starts_at)} ← {moment(grant.ends_at)}
            {grant.has_subscription ? "" : " · بلا اشتراك (مانعٌ عند الكابتن)"}
          </li>
        ))}
        {grants.length === 0 ? <li className="text-muted">لا منحَ بعد.</li> : null}
      </ul>
    </section>
  );
}

function RiderOffersSection({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const [perks, setPerks] = useState<RiderPerks | null>(null);
  const [perkForm, setPerkForm] = useState({ cancel: "", premium: "" });
  const [coupons, setCoupons] = useState<PartnerCoupon[]>([]);
  const [coupon, setCoupon] = useState({ shop: "", area: "", title: "", details: "", code: "", until: "" });
  const [lookup, setLookup] = useState({ driver: "", month: thisMonth() });
  const [discounts, setDiscounts] = useState<CaptainDiscounts | null>(null);
  const [busy, setBusy] = useState(false);
  const currency = currencyOf(country);

  const fillPerks = (row: RiderPerks) => {
    setPerks(row);
    setPerkForm({
      cancel: row.free_cancel_seconds === null ? "" : String(row.free_cancel_seconds),
      premium: row.premium_after_rides === null ? "" : String(row.premium_after_rides),
    });
  };
  const load = useCallback(() => {
    getRiderPerks(country).then(fillPerks).catch((caught: Error) => onError(caught.message));
    listPartnerCoupons(country).then(setCoupons).catch((caught: Error) => onError(caught.message));
  }, [country, onError]);
  useEffect(load, [load]);

  const savePerks = (extra: Record<string, unknown> = {}) => {
    const payload: Record<string, unknown> = { ...extra };
    const clear: string[] = [];
    if (perkForm.cancel) payload.free_cancel_seconds = Number(perkForm.cancel);
    else clear.push("free_cancel_seconds");
    if (perkForm.premium) payload.premium_after_rides = Number(perkForm.premium);
    else clear.push("premium_after_rides");
    payload.clear = clear;
    setBusy(true);
    updateRiderPerks(country, payload)
      .then(fillPerks)
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  const addCoupon = () => {
    setBusy(true);
    createPartnerCoupon(country, {
      shop_name: coupon.shop.trim(),
      shop_area: coupon.area.trim() || null,
      title: coupon.title.trim(),
      details: coupon.details.trim() || null,
      coupon_code: coupon.code.trim() || null,
      valid_until: coupon.until ? new Date(coupon.until).toISOString() : null,
    })
      .then(() => {
        setCoupon({ shop: "", area: "", title: "", details: "", code: "", until: "" });
        load();
      })
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="rider-offers-admin-title">
      <h2 id="rider-offers-admin-title" className="text-15 font-bold text-ink">
        عروض الركّاب
      </h2>
      <p className="mt-4 text-11 leading-snug text-muted">
        «خصم الافتتاح» و«أول رحلة» و«ادعُ صديقك» تُنشأ من «الكوبونات» بنوعها ومن يتحمّلها بعد الفترة المجّانية — وكلُّها مطفأةٌ حتى تُشعَل،
        ولا يجتمع عرضان في رحلة. وفي فترة الكابتن المجّانية يتحمّل الكابتنُ الخصمَ إلزاماً. وتحت هذا: الإلغاءُ المجّانيّ وشارةُ «راكب مميّز»
        وكوبوناتُ المحلّات (الخصمُ على المحلّ).
      </p>
      {perks ? (
        <>
          <div className="mt-12 grid grid-cols-2 gap-10">
            <Field name="rp_cancel" label="إلغاء مجّانيّ خلال (ثوانٍ)" dir="ltr" inputMode="numeric" value={perkForm.cancel}
              disabled={!isAdmin} onChange={(e) => setPerkForm({ ...perkForm, cancel: numeric(e.target.value) })} />
            <Field name="rp_premium" label="«راكب مميّز» بعد (رحلات)" dir="ltr" inputMode="numeric" value={perkForm.premium}
              disabled={!isAdmin} onChange={(e) => setPerkForm({ ...perkForm, premium: numeric(e.target.value) })} />
          </div>
          {isAdmin ? (
            <div className="mt-10 flex flex-wrap gap-8">
              <Button size="sm" loading={busy} onClick={() => savePerks()}>
                حفظ
              </Button>
              <Button size="sm" variant="secondary" loading={busy}
                onClick={() => savePerks({ premium_priority: !perks.premium_priority })}>
                {perks.premium_priority ? "أولويّة المطابقة للمميّز: نعم" : "أولويّة المطابقة للمميّز: لا"}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}

      <h3 className="mt-16 text-13 font-bold text-ink">كوبونات المحلّات الشريكة</h3>
      {isAdmin ? (
        <div className="mt-8 grid grid-cols-2 gap-10 md:grid-cols-3">
          <Field name="cp_shop" label="المحلّ" value={coupon.shop} onChange={(e) => setCoupon({ ...coupon, shop: e.target.value })} />
          <Field name="cp_area" label="المنطقة" value={coupon.area} onChange={(e) => setCoupon({ ...coupon, area: e.target.value })} />
          <Field name="cp_title" label="العرض" value={coupon.title} onChange={(e) => setCoupon({ ...coupon, title: e.target.value })} />
          <Field name="cp_details" label="التفاصيل" value={coupon.details} onChange={(e) => setCoupon({ ...coupon, details: e.target.value })} />
          <Field name="cp_code" label="الرمز" dir="ltr" value={coupon.code} onChange={(e) => setCoupon({ ...coupon, code: e.target.value })} />
          <Field name="cp_until" label="حتى (YYYY-MM-DD)" dir="ltr" value={coupon.until} onChange={(e) => setCoupon({ ...coupon, until: e.target.value })} />
          <div className="flex items-end">
            <Button size="sm" loading={busy} disabled={!coupon.shop.trim() || !coupon.title.trim()} onClick={addCoupon}>
              إضافة
            </Button>
          </div>
        </div>
      ) : null}
      <ul className="mt-8 space-y-6 text-12">
        {coupons.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-8 border-t border-line pt-6">
            <span>
              <span className="font-semibold text-ink">{row.shop_name}</span> · {row.title}
              {row.valid_until ? ` · حتى ${moment(row.valid_until)}` : ""}{" "}
              <Badge tone={row.is_active ? "ok" : "muted"}>{row.is_active ? "ظاهر" : "مخفيّ"}</Badge>
            </span>
            {isAdmin ? (
              <Button size="sm" variant="secondary"
                onClick={() =>
                  updatePartnerCoupon(country, row.id, { is_active: !row.is_active })
                    .then(load)
                    .catch((caught: Error) => onError(caught.message))
                }>
                {row.is_active ? "إخفاء" : "إظهار"}
              </Button>
            ) : null}
          </li>
        ))}
        {coupons.length === 0 ? <li className="text-muted">لا كوبونات.</li> : null}
      </ul>

      <h3 className="mt-16 text-13 font-bold text-ink">خصوم تحمّلها كابتن</h3>
      <div className="mt-8 grid grid-cols-2 gap-10 md:grid-cols-3">
        <Field name="cd_driver" label="معرّف الكابتن" dir="ltr" value={lookup.driver}
          onChange={(e) => setLookup({ ...lookup, driver: e.target.value.trim() })} />
        <Field name="cd_month" label="الشهر (YYYY-MM-01)" dir="ltr" value={lookup.month}
          onChange={(e) => setLookup({ ...lookup, month: e.target.value })} />
        <div className="flex items-end">
          <Button size="sm" variant="secondary" disabled={!lookup.driver}
            onClick={() =>
              getCaptainDiscounts(lookup.driver, lookup.month)
                .then(setDiscounts)
                .catch((caught: Error) => onError(caught.message))
            }>
            عرض
          </Button>
        </div>
      </div>
      {discounts ? (
        <ul className="mt-8 space-y-4 text-11">
          {discounts.rides.map((row) => (
            <li key={row.ride_id}>
              {row.completed_at ? moment(row.completed_at) : "—"} · {row.label} · خصم {money(row.discount, row.currency)}
              {row.fare ? ` · الأجرة ${money(row.fare, row.currency)}` : ""}
            </li>
          ))}
          <li className="font-semibold text-ink">
            المجموع {money(discounts.total, discounts.rides[0]?.currency ?? currency)} · {digits(String(discounts.count))} رحلة
          </li>
        </ul>
      ) : null}
    </section>
  );
}

export function PointsLaunchAdmin({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  return (
    <>
      <CommitmentSection onError={onError} isAdmin={isAdmin} />
      <LaunchSection onError={onError} isAdmin={isAdmin} />
      <RiderOffersSection onError={onError} isAdmin={isAdmin} />
    </>
  );
}
