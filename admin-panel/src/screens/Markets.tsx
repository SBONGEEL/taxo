/** **«الدول»** — فتحُ الأسواق وإغلاقُها، وظهورُ المغلقة في التسجيل، ومفتاحُ «العمل خارج حدود الدول» وقائمةُ السماح
 * (SPEC §٧٤-أ/٢–٣ — لوحةُ «اللوحة — «الدول» والحدود» في Claude Design).
 *
 * **القراءةُ لطاقم اللوحة، والأفعالُ `markets.manage`** — «بصلاحية المالك»، لا يملكها أحدٌ افتراضاً: **تُعطَّل الأزرارُ لمن لا يملكها
 * والخادمُ يردّ** (§21: الإخفاءُ راحةٌ لا حماية). **ولا حالَ تُحسب هنا**: كلُّ بابٍ يعيد الصفحةَ كلَّها من الخلفية، والجاهزيّةُ منها.
 *
 * **والفتحُ يمرّ بفحص الجاهزيّة**: ٤٠٩ بما نقص ⇒ ورقةٌ تسرد النقصَ **وتطلب سبباً مكتوباً للفتح رغمه**؛ **والإغلاقُ يُسأل مرّةً** بما
 * يقع (الجاري يكتمل، ولا طلبَ جديد، والمحافظُ كما هي). **ورفعُ الحدود يطلب سبباً**، وإعادتُها بلا شرط.
 */
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  getMarkets,
  getTestAccounts,
  grantBorderAllowance,
  refillTestFunds,
  revokeBorderAllowance,
  setBorders,
  setMarketStatus,
  listSignupCountries,
  setSignupCountry,
  setSignupDisplay,
} from "@/api/endpoints";
import type { CountryCode, MarketRow, Markets, SignupCountryRow, SignupDisplay, SignupState, TestAccounts } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field, Select, Switch } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Segmented } from "@/components/ui/Segmented";
import { useCountry } from "@/lib/country";
import { day, money } from "@/lib/format";
import { useMyPermissions } from "@/lib/permissions";
import { Flag, Icon } from "@/taxo2";

/** مرآةُ `AdminPermission.MARKETS_MANAGE`. */
const MARKETS_MANAGE = "markets.manage";
const MIN_REASON = 8;

const ROLE_LABEL: Record<string, string> = { rider: "راكب", driver: "كبتن", admin: "مشرف", support: "دعم", owner: "المالك" };

/** **اختصاراتُ كلِّ دولة** — تنقل مبدّلَ الدولة إليها ثمّ تفتح الصفحة (لوحةُ «الدول»: الأسعار · الخدمات · طرق الدفع · السياسات · المالية). */
const SHORTCUTS: Array<{ label: string; to: string }> = [
  { label: "الأسعار", to: "/pricing" },
  { label: "الخدمات", to: "/settings" },
  { label: "طرق الدفع", to: "/payment-system" },
  { label: "السياسات", to: "/policies" },
  { label: "المالية", to: "/finance/country/:code" },
];

type Pending =
  | { kind: "open"; row: MarketRow; missing: string[] }
  | { kind: "close"; row: MarketRow }
  | { kind: "lift" };

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

/** **أسماءُ الحالات بلفظ المالك** (البند ٥) — مفتاحٌ لكلِّ عضوٍ في `SignupDisplay`، فعضوٌ جديدٌ لا يُرسم إنجليزيّاً */
const DISPLAY_LABEL: Record<SignupDisplay, string> = { soon: "قريباً", stopped: "متوقفة", hidden: "مخفية" };
const STATE_LABEL: Record<SignupState, string> = { open: "نشطة", soon: "قريباً", stopped: "متوقفة", hidden: "مخفية" };

export function MarketsScreen() {
  const held = useMyPermissions();
  const canManage = held?.has(MARKETS_MANAGE) === true;
  const navigate = useNavigate();
  const { setCountry } = useCountry();
  const [data, setData] = useState<Markets | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [reason, setReason] = useState("");
  const [allowCountry, setAllowCountry] = useState<CountryCode>("JO");
  const [allowPhone, setAllowPhone] = useState("");
  const [allowReason, setAllowReason] = useState("");

  const load = useCallback(() => {
    getMarkets()
      .then(setData)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة الدول")));
  }, []);
  useEffect(load, [load]);

  async function run(work: () => Promise<Markets>, success: string) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      setData(await work());
      setDone(success);
      setPending(null);
      setReason("");
    } catch (caught) {
      setError(messageOf(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }

  async function tryOpen(row: MarketRow) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      setData(await setMarketStatus(row.country_code, { open: true }));
      setDone(`فُتحت ${row.name} للعموم`);
    } catch (caught) {
      // **غيرُ جاهزة** ⇒ ورقةٌ بما نقص، والفتحُ رغمه بسببٍ مكتوب
      if (caught instanceof ApiError && caught.code === "market_not_ready") {
        const missing = Array.isArray(caught.extra.missing) ? (caught.extra.missing as string[]) : row.readiness;
        setPending({ kind: "open", row, missing });
      } else setError(messageOf(caught, "تعذّر الفتح"));
    } finally {
      setBusy(false);
    }
  }

  function grant(event: FormEvent) {
    event.preventDefault();
    void run(
      () => grantBorderAllowance({ phone: allowPhone, country_code: allowCountry, reason: allowReason }),
      "أُضيف الحسابُ إلى قائمة السماح",
    ).then(() => {
      setAllowPhone("");
      setAllowReason("");
    });
  }

  const reasonShort = reason.trim().length < MIN_REASON;

  return (
    <Shell
      title="الدول"
      subtitle="فتحُ الأسواق للعموم وإغلاقُها، وظهورُ المغلقة في التسجيل، والعملُ خارج الحدود — بصلاحية المالك"
      actions={canManage ? <Badge tone="ink">صلاحيتُك: الدول والحدود</Badge> : <Badge>للقراءة — الأفعالُ بصلاحية المالك</Badge>}
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      {data === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="mt-12 flex flex-col gap-16">
          <section className="grid gap-14 lg:grid-cols-3" aria-label="الأسواق">
            {data.countries.map((row) => {
              const open = row.status === "open";
              return (
                <article key={row.country_code} className="flex flex-col gap-14 rounded-20 border border-line bg-surface p-18">
                  <div className="flex items-center gap-12">
                    <Flag code={row.country_code} label={row.name} size={36} />
                    <div className="flex flex-1 flex-col">
                      <h2 className="text-17 font-bold text-ink">{row.name}</h2>
                      <span className="text-12 text-muted">{row.currency_label}</span>
                    </div>
                    <Badge tone={open ? "ok" : "muted"}>{open ? "مفتوحة" : "مغلقة"}</Badge>
                  </div>

                  <div className="flex items-center gap-12 rounded-16 bg-surface-2 px-14 py-12">
                    <span className="flex flex-1 flex-col">
                      <span className="text-13.5 font-semibold text-ink">مفتوحة للعموم</span>
                      <span className="text-11.5 text-muted">
                        {open
                          ? "إغلاقُها: الجاري يكتمل، ولا طلبَ جديد، والمحافظُ كما هي"
                          : "الفتحُ يمرّ بفحص الجاهزيّة أوّلاً"}
                      </span>
                    </span>
                    <Switch
                      checked={open}
                      label={`${row.name} مفتوحةٌ للعموم`}
                      disabled={!canManage || busy}
                      onChange={(next) => (next ? void tryOpen(row) : setPending({ kind: "close", row }))}
                    />
                  </div>

                  <ul className="flex flex-col gap-8 text-12.5">
                    {row.readiness.length === 0 ? (
                      <li className="flex items-center gap-8 text-ok">
                        <Icon name="check_circle" fill />
                        جاهزةٌ للفتح: الأسعارُ وطريقةُ الدفع والسياساتُ والتقريب
                      </li>
                    ) : (
                      row.readiness.map((line) => (
                        <li key={line} className="flex items-center gap-8 text-danger">
                          <Icon name="cancel" fill />
                          {line}
                        </li>
                      ))
                    )}
                  </ul>

                  <div className="text-12 text-muted">
                    رحلاتٌ جاريةٌ الآن: <span className="num font-semibold text-ink">{row.active_rides}</span>
                  </div>

                  <div className="flex flex-col gap-8">
                    <span className="text-12.5 font-semibold text-ink">في التسجيل وهي مغلقة</span>
                    <Segmented<SignupDisplay>
                      label={`ظهورُ ${row.name} في التسجيل`}
                      value={row.signup_display}
                      options={[
                        { key: "soon", label: "قريباً" },
                        { key: "stopped", label: "متوقفة" },
                        { key: "hidden", label: "مخفية" },
                      ]}
                      onPick={(display) =>
                        canManage && !busy && display !== row.signup_display
                          ? void run(() => setSignupDisplay(row.country_code, display), `ظهورُ ${row.name} في التسجيل: ${DISPLAY_LABEL[display]}`)
                          : undefined
                      }
                    />
                  </div>

                  <nav aria-label={`اختصارات ${row.name}`} className="flex flex-wrap gap-6">
                    {SHORTCUTS.map((shortcut) => (
                      <Button
                        key={shortcut.to}
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setCountry(row.country_code);
                          navigate(shortcut.to.replace(":code", row.country_code));
                        }}
                      >
                        {shortcut.label}
                      </Button>
                    ))}
                  </nav>
                </article>
              );
            })}
          </section>

          <section className="flex flex-col gap-16 rounded-20 border border-line bg-surface p-18" aria-label="العمل خارج حدود الدول">
            <div className="flex flex-wrap items-start gap-16">
              <div className="flex min-w-[300px] flex-1 flex-col gap-6">
                <h2 className="text-17 font-bold text-ink">العمل خارج حدود الدول</h2>
                <p className="text-12.5 leading-relaxed text-muted">
                  مشغَّلاً: الحدودُ مفروضةٌ كما اليوم — رحلةٌ أحدُ طرفيها خارج بلد الحساب تُردّ. مطفأً: التطبيقاتُ تعمل من أيِّ مكانٍ
                  بسوق الحساب نفسِه. ورفعُ الحدود لا يفتح دولةً مغلقة.
                </p>
              </div>
              <div className="flex items-center gap-12 rounded-16 bg-surface-2 px-16 py-12">
                <span className="text-13.5 font-semibold text-ink">الحدودُ مفروضة</span>
                <Switch
                  checked={data.borders_enforced}
                  label="الحدودُ مفروضة"
                  disabled={!canManage || busy}
                  onChange={(next) =>
                    next ? void run(() => setBorders({ enforced: true }), "أُعيدت الحدود") : setPending({ kind: "lift" })
                  }
                />
              </div>
            </div>

            <div className="flex flex-col gap-10">
              <h3 className="text-14 font-bold text-ink">مسموحٌ لهم بالعمل من الخارج والحدودُ مفروضة</h3>
              {data.allowances.length === 0 ? (
                <p className="text-12.5 text-muted">لا حسابَ في القائمة.</p>
              ) : (
                <div className="overflow-x-auto rounded-14 border border-line">
                  <table className="w-full border-collapse text-12.5">
                    <thead>
                      <tr className="bg-surface-2 text-muted">
                        {["الحساب", "الهاتف", "الدور", "السوق", "السبب", "منذ", ""].map((head) => (
                          <th key={head} className="px-12 py-10 text-start font-semibold">
                            {head}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.allowances.map((row) => (
                        <tr key={row.id} className="border-t border-line">
                          <td className="px-12 py-10 font-semibold text-ink">
                            {row.name ?? "—"} {row.is_test ? <Badge tone="warn">تجربة</Badge> : null}
                          </td>
                          <td className="num px-12 py-10" dir="ltr">
                            {row.phone ?? "—"}
                          </td>
                          <td className="px-12 py-10">{ROLE_LABEL[row.role] ?? row.role}</td>
                          <td className="px-12 py-10">
                            {data.countries.find((country) => country.country_code === row.country_code)?.name ?? row.country_code}
                          </td>
                          <td className="px-12 py-10">{row.reason}</td>
                          <td className="num px-12 py-10">{day(row.granted_at)}</td>
                          <td className="px-12 py-10">
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={!canManage || busy}
                              onClick={() => void run(() => revokeBorderAllowance(row.id), "نُزع السماح")}
                            >
                              نزع
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {canManage ? (
                <form className="flex flex-wrap items-end gap-8" onSubmit={grant}>
                  <Select label="الدولة" value={allowCountry} onChange={(event) => setAllowCountry(event.target.value as CountryCode)}>
                    {data.countries.map((country) => (
                      <option key={country.country_code} value={country.country_code}>
                        {country.name}
                      </option>
                    ))}
                  </Select>
                  <Field
                    label="رقم الحساب"
                    name="allow-phone"
                    dir="ltr"
                    inputMode="tel"
                    value={allowPhone}
                    onChange={(event) => setAllowPhone(event.target.value)}
                  />
                  <div className="min-w-[220px] flex-1">
                    <Field
                      label="السبب"
                      name="allow-reason"
                      value={allowReason}
                      placeholder="لماذا يعمل من الخارج؟"
                      onChange={(event) => setAllowReason(event.target.value)}
                    />
                  </div>
                  <Button type="submit" size="md" disabled={busy || !allowPhone.trim() || allowReason.trim().length < 3}>
                    أضف إلى القائمة
                  </Button>
                </form>
              ) : null}
            </div>
          </section>
          <SignupCountriesSection canManage={canManage} />
          <TestAccountsSection canManage={canManage} countries={data.countries} />
          <p className="text-11.5 text-muted">كلُّ فتحٍ وإغلاقٍ ورفعٍ للحدود وسماحٍ ونزعٍ وإعادةِ ملءٍ يُكتب في سجلّ التدقيق باسمك.</p>
        </div>
      )}

      {pending?.kind === "open" ? (
        <Modal title={`${pending.row.name} غيرُ جاهزةٍ للفتح`} onClose={() => setPending(null)}>
          <ul className="mb-12 list-disc ps-18 text-12.5 leading-loose text-ink">
            {pending.missing.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <label htmlFor="force-reason" className="label">
            الفتحُ رغم النقص — اكتب السبب
          </label>
          <textarea
            id="force-reason"
            className="fld"
            rows={2}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="mt-12 flex gap-8">
            <Button
              disabled={busy || reasonShort}
              onClick={() =>
                void run(
                  () => setMarketStatus(pending.row.country_code, { open: true, force: true, reason }),
                  `فُتحت ${pending.row.name} رغم النقص — والسببُ في التدقيق`,
                )
              }
            >
              افتح رغم ذلك
            </Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              تراجع
            </Button>
          </div>
        </Modal>
      ) : null}

      {pending?.kind === "close" ? (
        <Modal title={`إغلاقُ ${pending.row.name}`} onClose={() => setPending(null)}>
          <p className="text-13 leading-relaxed text-ink">
            الرحلاتُ الجارية ({pending.row.active_rides}) تكتمل، ولا يطلب أحدٌ جديداً، والمحافظُ والبياناتُ كما هي — والدخولُ قائمٌ لكلِّ
            حساب. والتسجيلُ فيها يصير «{DISPLAY_LABEL[pending.row.signup_display]}».
          </p>
          <div className="mt-12 flex gap-8">
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void run(() => setMarketStatus(pending.row.country_code, { open: false }), `أُغلقت ${pending.row.name}`)}
            >
              أغلق
            </Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              تراجع
            </Button>
          </div>
        </Modal>
      ) : null}

      {pending?.kind === "lift" ? (
        <Modal title="رفعُ الحدود" onClose={() => setPending(null)}>
          <p className="mb-12 text-13 leading-relaxed text-ink">
            يعمل كلُّ حسابٍ من أيِّ مكانٍ بسوقه — بعملته وأسعاره. ولا تُفتح دولةٌ مغلقة.
          </p>
          <label htmlFor="lift-reason" className="label">
            السبب
          </label>
          <textarea id="lift-reason" className="fld" rows={2} value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="mt-12 flex gap-8">
            <Button
              variant="danger"
              disabled={busy || reasonShort}
              onClick={() => void run(() => setBorders({ enforced: false, reason }), "رُفعت الحدود — والسببُ في التدقيق")}
            >
              ارفع الحدود
            </Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              تراجع
            </Button>
          </div>
        </Modal>
      ) : null}
    </Shell>
  );
}

/** **حساباتُ التجربة** (SPEC §٧٤-أ/١٠) — سوقُ كلِّ حسابٍ ورصيدُه «رصيد تجريبي»، **وإعادةُ الملء للمالك وحدَه**: تكمّل إلى مبلغ السوق ولا تتجاوزه.
 *  **ومالُ التجربة لا يغادر المنصّة** — لا سحبَ ولا تحويلَ لغير حسابات التجربة، ولا يظهر في أيِّ صفحةٍ ماليّة. */
function TestAccountsSection({ canManage, countries }: { canManage: boolean; countries: MarketRow[] }) {
  const [data, setData] = useState<TestAccounts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    getTestAccounts()
      .then(setData)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة حسابات التجربة")));
  }, []);

  async function refill(id: string, name: string) {
    setBusy(id);
    setError(null);
    setDone(null);
    try {
      setData(await refillTestFunds(id));
      setDone(`أُعيد ملءُ رصيد التجربة لـ${name} — والقيدُ موسومٌ «رصيد تجريبي»`);
    } catch (caught) {
      setError(messageOf(caught, "تعذّر إعادة الملء"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-12 rounded-20 border border-line bg-surface p-18" aria-label="حسابات التجربة">
      <div className="flex flex-col gap-6">
        <h2 className="text-17 font-bold text-ink">حساباتُ التجربة</h2>
        <p className="text-12.5 leading-relaxed text-muted">
          تصل كلَّ سوقٍ ولو كان مغلقاً — داخلَ دولةٍ سوقُها، ومن الخارج مُختارٌ لا يراه غيرُها. ورصيدُها «رصيد تجريبي»: لا يُسحب ولا
          يُحوَّل لحسابٍ حقيقيّ، ولا يُحسب في صفحات المالية.
        </p>
      </div>
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      {data === null ? (
        error ? null : <Spinner />
      ) : data.accounts.length === 0 ? (
        <p className="text-12.5 text-muted">لا حسابَ تجربة.</p>
      ) : (
        <div className="overflow-x-auto rounded-14 border border-line">
          <table className="w-full border-collapse text-12.5">
            <thead>
              <tr className="bg-surface-2 text-muted">
                {["الحساب", "الهاتف", "الدور", "السوق", "رصيد التجربة", "من الخارج", ""].map((head) => (
                  <th key={head} className="px-12 py-10 text-start font-semibold">
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.accounts.map((row) => {
                const full = !row.refillable;
                return (
                  <tr key={row.id} className="border-t border-line">
                    <td className="px-12 py-10 font-semibold text-ink">
                      {row.name ?? "—"} {row.twin_of ? <Badge>توأم</Badge> : null}
                    </td>
                    <td className="num px-12 py-10" dir="ltr">
                      {row.phone ?? "—"}
                    </td>
                    <td className="px-12 py-10">{ROLE_LABEL[row.role] ?? row.role}</td>
                    <td className="px-12 py-10">
                      {countries.find((country) => country.country_code === row.country_code)?.name ?? row.country_code}
                    </td>
                    <td className="num px-12 py-10">
                      {money(row.balance, row.currency)}
                      <span className="text-muted"> / {money(row.target_amount, row.currency)}</span>
                    </td>
                    <td className="px-12 py-10">{row.outside_allowed ? <Badge tone="ink">مسموح</Badge> : "—"}</td>
                    <td className="px-12 py-10">
                      {canManage ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={busy !== null || full}
                          onClick={() => void refill(row.id, row.name ?? row.phone ?? "")}
                        >
                          {busy === row.id ? "…" : full ? "ممتلئ" : "إعادة ملء"}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** **دولُ مُنتقي الهاتف** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥) — العلمُ والاسمُ والرمزُ في تطبيقَي الدخول والتسجيل، **وحالُ كلِّ دولةٍ من هنا
 *  بلا تحديثِ تطبيق**. **الأسواقُ** (الأردن · الجزائر · ليبيا) حالُها من بطاقتها أعلاه؛ **وغيرُها**: «قريباً» أو «متوقفة» أو «مخفية» —
 *  **ولا تكون «نشطة»**: لا قواعدَ أرقامٍ لها، فلا رمزَ يُرسل إلى رقمها. **والمحاولاتُ عددٌ لكلِّ دولة — لا رقمَ هاتفٍ يُحفظ.** */
function SignupCountriesSection({ canManage }: { canManage: boolean }) {
  const [rows, setRows] = useState<SignupCountryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    listSignupCountries()
      .then(setRows)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة دول المُنتقي")));
  }, []);

  async function pick(code: string, display: SignupDisplay) {
    setBusy(code);
    setError(null);
    try {
      setRows(await setSignupCountry(code, display));
    } catch (caught) {
      setError(messageOf(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(null);
    }
  }

  const needle = query.trim();
  const shown = (rows ?? []).filter((row) => !needle || row.name.includes(needle) || row.dial_code.includes(needle.replace(/^\+/, "")));
  return (
    <section className="card flex flex-col gap-12 p-16" aria-labelledby="signup-countries-title">
      <h2 id="signup-countries-title" className="text-15 font-bold text-ink">
        دولُ مُنتقي الهاتف
      </h2>
      <p className="text-12.5 leading-relaxed text-muted">
        يرى المستخدمُ في الدخول والتسجيل علمَ كلِّ دولةٍ واسمَها ورمزَها. <b>نشطة</b>: تعمل كالمعتاد (تُفتح من بطاقة السوق أعلاه).{" "}
        <b>قريباً</b>: شارةٌ، وعند المتابعة «قريباً في [الدولة]» بلا رمز تحقّق. <b>متوقفة</b>: عند المتابعة «خادم الدولة متوقف حالياً» بلا
        رمز — وهي افتراضُ كلِّ دولةٍ جديدة. <b>مخفية</b>: لا تظهر. التغييرُ يصل التطبيقين فوراً بلا تحديث، والمحاولاتُ عددٌ لكلِّ دولةٍ في
        آخر 30 يوماً — لا يُحفظ أيُّ رقم هاتف.
      </p>
      <input
        className="fld"
        aria-label="ابحث عن دولة"
        placeholder="ابحث بالاسم أو الرمز"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {error ? <p className="text-12.5 text-danger">{error}</p> : null}
      {rows === null ? <p className="text-12.5 text-muted">…</p> : null}
      <ul className="flex flex-col divide-y divide-line">
        {shown.map((row) => (
          <li key={row.code} className="flex flex-wrap items-center gap-12 py-8">
            <span className="min-w-[10rem] text-13 font-semibold text-ink">{row.name}</span>
            <span className="num text-12 text-muted" dir="ltr">
              +{row.dial_code}
            </span>
            <span className="text-12 text-muted">
              محاولات: <span className="num font-semibold text-ink">{row.attempts_30d}</span>
            </span>
            {row.market ? (
              <span className="text-12 text-muted">سوق — {STATE_LABEL[row.state]} (من بطاقته أعلاه)</span>
            ) : (
              <Segmented<SignupDisplay>
                label={`حالُ ${row.name}`}
                value={row.state === "open" ? "soon" : (row.state as SignupDisplay)}
                options={[
                  { key: "soon", label: "قريباً" },
                  { key: "stopped", label: "متوقفة" },
                  { key: "hidden", label: "مخفية" },
                ]}
                onPick={(display) =>
                  canManage && busy === null && display !== row.state ? void pick(row.code, display) : undefined
                }
              />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
