/** حسابي — SPEC القسم 12، **بلغة TAXO 2.0** «C23» (`design/t2-new/captain/C23-account.dc.html`) في المظهرين والورديّ.
 *
 * صفحةُ عبورٍ لا صفحةُ تحرير: ما يملك الكبتن تغييرَه من ملفه حقلٌ واحد
 * (`cliq_alias` عبر `PATCH /drivers/me`)، ومكانُه الإعدادات مع بقية ما
 * يُحفظ. أما اسمُه ورقمُه فلا منفذَ لتعديلهما — ورقمُه بالذات **هوية الدخول
 * وقد أُثبتت مرةً** (`users.phone_verified_at`)، فتغييرُه من شاشةٍ بلا إعادة
 * إثبات بابٌ لسرقة حساب. فيُعرضان ولا يُحرَّران.
 *
 * ولا مبدّلَ لغةٍ في الرأس: التطبيق عربيٌّ وحده (`DESIGN-DECISIONS` بند 18).
 *
 * **والشكلُ من عائلة TAXO 2.0** (§٦٢/٦–٧): بنيةُ «R15» حسابِ الراكب — الحرفُ في دائرةٍ والاسمُ والرقمُ، ثمّ القائمةُ، ثمّ الخروج —
 * **بصفوف «C15»** (أيقونةٌ وعنوانٌ وتلميحٌ وسهم) وبطاقةِ حالٍ بمربّعات «C12». **والمنطقُ حرفاً**: النداءُ نفسُه (`GET
 * /subscriptions/me`)، والمفاتيحُ نفسُها تحجب صفوفَها، والجملُ نفسُها، وورقةُ تأكيدِ إنهاء الجلسات قبل أن يقع.
 */

import { REQUIRED_DOCUMENTS } from "@/lib/documents";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMySubscription } from "@/api/endpoints";
import type { DriverStatus, MySubscription } from "@/api/types";
import { useCountryConfig, useFeature } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { useGarage } from "@/lib/garage";
import { forDisplay } from "@/lib/phone";
import { blockedReason, switchToRider } from "@/lib/switch-app";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

type Tone = "ok" | "warn" | "danger";

/** والنوعُ `DriverStatus` لا `string`: حالٌ جديدةٌ في الخلفية تكسر البناء
 * هنا بدل أن تخرج على الشاشة سطراً فارغاً. */
const STATUS_LINE: Record<DriverStatus, { text: string; tone: Tone; icon: string }> = {
  approved: { text: "حساب معتمد", tone: "ok", icon: "verified" },
  pending: { text: "قيد المراجعة — لا تصلك طلبات بعد", tone: "warn", icon: "hourglass_top" },
  rejected: { text: "طلبك مرفوض — راجع الدعم", tone: "danger", icon: "error" },
  suspended: { text: "حسابك موقوف — راجع الدعم", tone: "danger", icon: "error" },
  // **الإلغاءُ نهايةٌ لا إيقاف** — فنصُّه يقول ذلك ولا يَعِد بمراجعة
  deactivated: { text: "حسابك مُلغى", tone: "danger", icon: "error" },
};

export function AccountScreen() {
  const navigate = useNavigate();
  const { profile } = useDriver();
  const { signOut } = useSession();
  const country = useCountryConfig(profile?.user.country_code);
  const womenService = useFeature(
    profile?.user.country_code,
    "women_service_enabled",
  );
  // **والصفُّ صار بلا مفتاحٍ بعد التعميم**: الرمزُ واحدٌ ويعمل في برنامجين،
  // فإخفاؤه بمفتاح أحدهما يخفي الآخرَ معه — والإحالاتُ تُسجَّل على كل حال،
  // فمن دعا اليومَ يُحفظ أثرُه ليُكافأ يومَ يُحدَّد المبلغ. وما يُخفى داخل
  // الشاشة هو **المبلغُ** لا الرمز (`referrals.attach` لا تسأل عن المفتاح)

  // **والمهامُّ خلف مفتاحها** (البند ٥٣، §٧): مطفأً لا مستوىً يُحسب أصلاً،
  // فشاشةٌ تعرض «مستواك: مبتدئ» في سوقٍ لا مستوياتِ فيه تصف حالةً لا وجودَ لها
  const levelsOn = useFeature(
    profile?.user.country_code,
    "driver_levels_enabled",
  );
  // **والسلفةُ خلف مفتاحها كذلك** (البند ١٥): صفٌّ يَعِد بقرضٍ في سوقٍ لا
  // سلفَ فيه أسوأُ من غيابه — والخلفيةُ ترفض على كل حال، فالمنعُ ببابٍ
  // مغلقٍ لا برسالةِ رفض
  const advancesOn = useFeature(
    profile?.user.country_code,
    "driver_advances_enabled",
  );
  // **من الكراج لا من `useFeature` هنا**: بيتٌ واحدٌ للسؤال، فلا يفتح صفٌّ
  // باباً يغلقه المزوّدُ نفسُه
  const { enabled: skinsOn } = useGarage();
  const [subscription, setSubscription] = useState<MySubscription | null>(null);

  useEffect(() => {
    getMySubscription()
      .then(setSubscription)
      .catch(() => setSubscription(null));
  }, []);

  if (!profile) {
    return (
      <div className="t2 t2-acc t2-acc-loading">
        <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
      </div>
    );
  }

  const { driver, user, vehicles, documents } = profile;
  const status = STATUS_LINE[driver.status];
  const vehicle = vehicles[0];

  // سطرُ الاشتراك ونبرتُه — نفس الحالات الأربع في شاشة الاشتراك
  const subLine = !subscription
    ? "…"
    : subscription.is_active
      ? `ساري · باقٍ ${digits(String(subscription.days_remaining))} يوماً`
      : subscription.coverage_until
        ? "منتهٍ — جدّد للعودة للتوزيع"
        : "لا اشتراك — اشترك للبدء";
  // **ولا لونَ قبل الجواب**: كان الشريطُ أحمرَ حتى يصل النداء، فيُقرأ «منتهٍ» عن اشتراكٍ ساري — والنبرةُ بعده كما كانت
  const subTone: Tone | "" = !subscription
    ? ""
    : !subscription.is_active
      ? "danger"
      : subscription.days_remaining <= 1
        ? "warn"
        : "ok";

  // ولا يُقال «كل المستندات مقبولة» من حال الكبتن: من اعتُمد ثم رُفض مستندٌ
  // حدّثه يقرأ جملةً تكذّبها شاشةُ المستندات نفسها. والمرفوضُ ليس «بانتظار
  // المراجعة» — هو بانتظار **الكبتن**
  const rejectedDocs = documents.filter(
    (document) => document.review_status === "rejected",
  ).length;
  const pendingDocs = documents.filter(
    (document) => document.review_status === "pending",
  ).length;
  // **وصفرٌ مقروءٌ عطبٌ لا سلامة** (عطبٌ مقيسٌ ٢٠٢٦-٠٩-٠٩): العدّان أعلاه
  // صفران حين **لا مستندَ أصلاً**، فكانت الجملةُ تسقط إلى «كل المستندات
  // مقبولة» وشاشةُ المستندات تقول «لم يُرفع» في كلِّ سطر. **فالمطلوبُ يُسأل
  // لا المرفوعُ وحدَه** — والقائمةُ من بيتها الواحد لا مكتوبةً هنا ثانيةً.
  const missingDocs = REQUIRED_DOCUMENTS.filter(
    (docType) =>
      !documents.some(
        (document) =>
          document.doc_type === docType &&
          document.review_status !== "rejected",
      ),
  ).length;
  const docsNote =
    rejectedDocs > 0
      ? `${digits(String(rejectedDocs))} مستند مرفوض — يحتاج رفعاً جديداً`
      : missingDocs > 0
        ? `${digits(String(missingDocs))} مستند لم يُرفع بعد`
        : pendingDocs > 0
          ? `${digits(String(pendingDocs))} مستند قيد المراجعة`
          : "كل المستندات مقبولة";
  // **المرفوضُ أحمرُ والناقصُ كهرمانيّ** — ما ينتظر الكبتنَ يُرى، وما ينتظر الإدارةَ خافت
  const docsTone = rejectedDocs > 0 ? "danger" : missingDocs > 0 ? "warn" : "";

  return (
    <div className="t2 t2-acc">
      <div className="t2-acc-prof">
        <span className="t2-acc-avatar" aria-hidden="true">
          {user.name.trim().slice(0, 1)}
        </span>
        <div className="t2-acc-main">
          <div className="t2-acc-name">{user.name}</div>
          {/* الرقم كما هو: معرّفٌ يُقارَن ويُملى، لا كمّيةٌ تُقرأ — نفس
              قاعدة `Cards.tsx` و`Vehicle.tsx` (`CLAUDE.md`) */}
          <div dir="ltr" className="t2-acc-phone">
            {/* `null` نظرياً (المشرف) ولا مشرفَ هنا — و«—» أصدقُ من
                فراغٍ يُقرأ عطباً في الرسم */}
            {user.phone
              ? country
                ? forDisplay(user.phone, country.dial_code)
                : user.phone
              : "—"}
          </div>
        </div>
        <span className="t2-acc-rate" aria-label={`تقييمك ${digits(driver.rating_avg)}`}>
          <Icon name="star" fill />
          <span className="t2-acc-rate-num" dir="ltr">
            {digits(driver.rating_avg)}
          </span>
        </span>
      </div>

      {/* **بطاقةُ الحال**: حالُ الحساب ومستنداته، ثمّ الاشتراكُ بنبرته — بابُه إلى «الاشتراك» */}
      <div className="t2-list">
        <div className="t2-acc-state">
          <span className={`t2-ax-tile ${status.tone}`} aria-hidden="true">
            <Icon name={status.icon} />
          </span>
          <span className="t2-acc-state-main">
            <span className="t2-acc-state-title">{status.text}</span>
            <span className={docsTone ? `t2-acc-state-sub ${docsTone}` : "t2-acc-state-sub"}>
              {docsNote}
            </span>
          </span>
        </div>
        <button
          type="button"
          onClick={() => navigate("/subscription")}
          className="t2-acc-state"
        >
          <span className={subTone ? `t2-ax-tile ${subTone}` : "t2-ax-tile"} aria-hidden="true">
            <Icon name="card_membership" />
          </span>
          <span className="t2-acc-state-main">
            <span className="t2-acc-state-title">الاشتراك</span>
            <span className="t2-acc-state-sub">{subLine}</span>
          </span>
          <Icon name="chevron_left" className="t2-ax-chev" />
        </button>
      </div>

      {/* توثيقُ الجنس (المرحلة 10-ج): تقرؤه الكبتنة لتعرف أنه **مثبَّتٌ من
          الإدارة عن هويتها** ومتى — لا حقلٌ نسيت ملأه. وقبل التثبيت لا
          تصلها الطلبات المجنّسة أصلاً، وقولُ ذلك هنا يمنع سؤال «لماذا لا
          تصلني طلبات النساء». ولا يُعدَّل من التطبيق */}
      {womenService ? (
        <div className="t2-list">
          <div className="t2-acc-gender">
            <div className="t2-acc-gender-top">
              <span
                className={user.gender === "female" ? "t2-ax-tile women" : "t2-ax-tile"}
                aria-hidden="true"
              >
                <Icon name={user.gender === "female" ? "woman" : "person"} />
              </span>
              <span className="t2-acc-gender-label">الجنس</span>
              <span
                className={
                  user.gender === "female"
                    ? "t2-acc-gender-value women"
                    : "t2-acc-gender-value"
                }
              >
                {user.gender === "female"
                  ? "أنثى"
                  : user.gender === "male"
                    ? "ذكر"
                    : "غير مثبَّت"}
              </span>
            </div>
            <p className="t2-acc-gender-note">
              {user.gender_verified_at
                ? `موثّق من الهوية بواسطة الإدارة · ${new Date(
                    user.gender_verified_at,
                  ).toLocaleDateString(DISPLAY_LOCALE, {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}`
                : "قبل التثبيت لا تصلك الطلبات التي تحدّد جنساً — لا كطلباتٍ مرفوضة، بل لا تُعرض أصلاً."}
            </p>
            <p className="t2-acc-gender-note">
              لا يُعدَّل من التطبيق. للتصحيح راسل الدعم.
            </p>
          </div>
        </div>
      ) : null}

      <div className="t2-list">
        <Row
          icon="directions_car"
          label="المركبة والمستندات"
          sub={
            vehicle
              ? `${vehicle.make} ${vehicle.model}`
              : "لم تُسجّل مركبة بعد"
          }
          onClick={() => navigate("/account/vehicle")}
        />
        <Row
          icon="credit_card"
          label="البطاقات المحفوظة"
          sub="بطاقاتُ الدفع التي حفظتَها"
          onClick={() => navigate("/account/cards")}
        />
        {/* **بلا مفتاح ولا شرط**: شاشةُ حالٍ تُقرأ في أيِّ وقت — ومن
            سُحب إذنُه من إعدادات الهاتف لا يمرّ بنا ليُعرض له بابُها */}
        <Row
          icon="verified_user"
          label="أذونات الجهاز"
          sub="ما يمنع وصول الطلبات إليك، وما يُضعفه"
          onClick={() => navigate("/account/permissions")}
        />
        {/* **بلا مفتاح**: الدَّينُ ينشأ من العمل نفسِه لا من ميزةٍ تُشغَّل،
            **ومن عليه مستحقٌّ يُمنع** — فبابٌ يظهر بشرطٍ يجعل الممنوعَ لا
            يجد أين يسدّد. والشاشةُ تعمل بصفر وتقول «لا مستحقّات عليك». */}
        <Row
          icon="toll"
          label="المستحقّات"
          sub="ما عليك من عمولة رحلات قبضتَ أجرتها نقداً"
          onClick={() => navigate("/account/debt")}
        />
        {advancesOn ? (
          <Row
            icon="request_quote"
            label="السلفة"
            sub="سلفةٌ تُقتطع من أرباح رحلاتك"
            onClick={() => navigate("/account/advances")}
          />
        ) : null}
        {/* **مركباتي قبل المهام**: كلاهما يُفتح عن قصد، وهذه يُفتح بابُها
            في كلِّ فتحةٍ للتطبيق (المفعَّلةُ على الخريطة أمام عينه).
            **وخلف مفتاحها**: صفٌّ يَعِد بمتجرٍ في سوقٍ لا متجرَ فيه أسوأُ
            من غيابه — والخلفيةُ ترفض على كلِّ حال */}
        {skinsOn ? (
          <Row
            icon="garage"
            label="مركباتي"
            sub="مركبتك على الخريطة والمتجر"
            onClick={() => navigate("/account/garage")}
          />
        ) : null}
        {levelsOn ? (
          <Row
            icon="flag"
            label="مهامّي ومستواي"
            sub="مهامُّ الشهر وشاراتي"
            onClick={() => navigate("/account/missions")}
          />
        ) : null}
        <Row
          icon="redeem"
          label="أَحِلْ صديقك"
          sub="رمزك ومن سجّل به"
          onClick={() => navigate("/account/referrals")}
        />
        <Row
          icon="settings"
          label="الإعدادات"
          sub="الإشعارات · المظهر · alias كليك"
          onClick={() => navigate("/account/settings")}
        />
        {/* **آخرُ الصفوف وأشدُّها أثراً** (البند ١٣): ما يخصّ الحساب يسكن هنا
            لا في «الإعدادات» — تلك للجهاز. ولا يُخفى خلف تحذير: من يريد
            الخروج يجد بابَه، والمراجعةُ هي ما يحمي لا صعوبةُ العثور */}
        <Row
          icon="delete"
          label="حذف الحساب"
          sub="يُحذف نهائياً بعد 30 يوماً — واسحب رصيدك خلالها"
          onClick={() => navigate("/account/delete")}
        />
      </div>

      {/* **في «حسابي» لا في شريطٍ سفليٍّ ولا على الرئيسية** (§23): تبديلٌ
          لا يُضغط يومياً، وموضعُه بين ما يُفتح عن قصد */}
      <SwitchRow />

      <button
        type="button"
        onClick={() => void signOut()}
        className="t2-acc-out"
      >
        تسجيل الخروج
      </button>

      <SignOutEverywhereRow />
    </div>
  );
}

/** **إنهاءُ كلِّ الجلسات** (SPEC §60-ب/١، قرارُ المالك ٢٠٢٦-١٠-٠٤) — لهاتفٍ أو
 *  حاسوبٍ ضاع. **ويُسأل قبل أن يقع** بورقةِ تأكيد (C23b): يُخرج الكبتنَ من هذا
 *  الجهاز أيضاً، وفعلٌ يُخرج من كلِّ مكانٍ لا يقع بلمسةٍ عابرة. */
function SignOutEverywhereRow() {
  const { signOutEverywhere } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await signOutEverywhere();
    } catch (caught) {
      // نصُّ الخلفية كما هو (§17) — ولا عربيةَ ثانيةٌ هنا
      setError(caught instanceof Error ? caught.message : "تعذّر إنهاء الجلسات — أعد المحاولة");
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="t2-acc-endall"
      >
        إنهاء كل الجلسات
      </button>
      {confirming ? (
        <div
          className="t2-ax-sheet"
          onClick={() => !busy && setConfirming(false)}
        >
          <div
            className="t2-ax-sheet-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="t2-acc-endall-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="t2-ax-grab" aria-hidden="true" />
            <h2 id="t2-acc-endall-title" className="t2-ax-sheet-title">
              إنهاء كل الجلسات
            </h2>
            <p className="t2-ax-sheet-body">
              تخرج من حسابك على كلِّ جهازٍ دخلتَ منه — وهذا منها — ولا تصل
              إشعاراتُ حسابك ولا طلباتُ الرحلات إلى أيٍّ منها. استعمله إن ضاع
              هاتفٌ أو حاسوب.
            </p>
            {error ? (
              <p className="t2-note danger" role="alert">
                <Icon name="error" />
                {error}
              </p>
            ) : null}
            <div className="t2-ax-sheet-actions">
              <button
                type="button"
                className="t2-ax-danger"
                disabled={busy}
                onClick={() => void confirm()}
              >
                {busy ? "…" : "إنهاء كل الجلسات"}
              </button>
              <button
                type="button"
                className="t2-ax-quiet"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                رجوع
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

/** صفٌّ في القائمة — **صفُّ «C15»** (`t2-srow`): أيقونةٌ وعنوانٌ وتلميحٌ وسهم. */
function Row({
  icon,
  label,
  sub,
  onClick,
}: {
  icon: string;
  label: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="t2-srow">
      <Icon name={icon} className="t2-srow-icon" />
      <span className="t2-srow-main">
        <span className="t2-srow-title">{label}</span>
        <span className="t2-srow-hint">{sub}</span>
      </span>
      <Icon name="chevron_left" className="t2-ax-chev" />
    </button>
  );
}


/** صفُّ التبديل إلى تطبيق الراكب — **يقول سببَه إن مُنع**. */
function SwitchRow() {
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);

  async function press() {
    setBusy(true);
    setBlocked(null);
    try {
      // `false` تعني **غير مثبَّت** — والصفحةُ تشرح وتعطي رابطَ التنزيل
      if (!(await switchToRider())) window.location.href = "/account/switch/rider-not-installed";
    } catch (caught) {
      // **لا رسالةَ إلا للمنع المعلن** — والفتحُ نفسُه لا يفشل
      setBlocked(blockedReason(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-list">
      <button
        type="button"
        disabled={busy}
        onClick={() => void press()}
        className="t2-srow"
      >
        <Icon name="swap_horiz" className="t2-srow-icon" />
        <span className="t2-srow-main">
          <span className="t2-srow-title">تبديل إلى تطبيق الراكب</span>
          <span className="t2-srow-hint">نفس الحساب — تنتقل جلستك بلا تسجيل دخول</span>
        </span>
        <Icon name="chevron_left" className="t2-ax-chev" />
      </button>
      {blocked ? <p className="t2-acc-blocked">{blocked}</p> : null}
    </div>
  );
}
