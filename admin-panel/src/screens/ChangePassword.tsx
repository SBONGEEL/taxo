/** **«غيّر كلمة مروري»** — لكلِّ مشرفٍ داخل، **وبوّابةُ أوّل دخول** (قرارُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-م/٢).
 *
 * **بلغة شاشة الدخول نفسِها** (`ad-login` وقطعُ `taxo2/Auth`): من يُلزَم بها يصلها بعد الدخول مباشرةً، وغلافُ اللوحة حولها يرسم أقساماً
 * كلُّ بابٍ خلفها مردودٌ حتى يغيّر — فالشاشةُ خارج الغلاف عمداً.
 *
 * **والقواعدُ ثلاث، وكلُّها تُفحص في الخلفية أيضاً**: الحاليّةُ صحيحة، والجديدةُ بقواعد التسجيل (`validate_password`: ٨ خاناتٍ فأكثر،
 * وليست شائعة)، وتختلف عن الحاليّة. **والتطابقُ هنا وحدَه** — «مرّتين» حمايةٌ من خطأ الإصبع، لا شرطٌ يعرفه الخادم.
 * **والتغييرُ يُخرج الجلساتِ الأخرى ويُبقي هذه، ويُكتب في سجلّ التدقيق بلا الكلمة.**
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { changeAdminPassword, getAdminAccount } from "@/api/endpoints";
import { ErrorNote } from "@/components/ui/Feedback";
import { useSession } from "@/lib/session";
import { AuthBlock, AuthConditions, AuthSecret, AuthTitle, Wordmark } from "@/taxo2";

const MIN_LENGTH = 8;

export function ChangePasswordScreen() {
  const navigate = useNavigate();
  const { passwordChangeRequired, passwordChanged, signOut } = useSession();
  const [forced, setForced] = useState(passwordChangeRequired);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **الإلزامُ يُقرأ من الخلفية** لا من مسارٍ جاء منه: من فتح الشاشةَ برابطٍ مباشرٍ أوّلَ دخولٍ مُلزَمٌ أيضاً
  useEffect(() => {
    void getAdminAccount()
      .then((account) => setForced(account.must_change_password))
      .catch(() => undefined);
  }, []);

  const conditions = [
    { key: "length", label: `${MIN_LENGTH} خانات على الأقل`, ok: next.length >= MIN_LENGTH },
    { key: "differs", label: "تختلف عن الحالية", ok: next.length > 0 && next !== current },
    { key: "match", label: "الكلمتان متطابقتان", ok: next.length > 0 && next === again },
  ];
  const ready = current.length > 0 && conditions.every((item) => item.ok);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await changeAdminPassword({ current_password: current, new_password: next });
      // **الكلماتُ لا تبقى في الذاكرة بعد أن أدّت دورَها**
      setCurrent("");
      setNext("");
      setAgain("");
      passwordChanged();
      navigate("/overview", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التغيير — أعد المحاولة");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ad-login">
      <div className="ad-login-art" aria-hidden="true">
        <span className="ad-login-bar a" />
        <span className="ad-login-bar b" />
      </div>

      <div className="ad-login-col">
        <div className="ad-login-form">
          <div className="ad-login-brand">
            <Wordmark size={26} />
            <span className="ad-login-tag">لوحة التحكم</span>
          </div>

          <AuthTitle
            title="غيّر كلمة المرور"
            sub={
              forced
                ? "أُنشئ حسابُك بكلمةٍ لم تضعها أنت — غيّرها قبل المتابعة في اللوحة."
                : "تُخرج الجلساتِ الأخرى على أجهزتك وتُبقي هذه، ويُكتب التغييرُ في سجلّ التدقيق بلا الكلمة."
            }
          />

          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (ready) void submit();
            }}
          >
            <AuthBlock label="كلمة المرور الحالية" htmlFor="current-password">
              <AuthSecret
                id="current-password"
                autoComplete="current-password"
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
              />
            </AuthBlock>
            <AuthBlock label="كلمة المرور الجديدة" htmlFor="new-password">
              <AuthSecret
                id="new-password"
                autoComplete="new-password"
                value={next}
                onChange={(event) => setNext(event.target.value)}
              />
            </AuthBlock>
            <AuthBlock label="أعد كتابة الجديدة" htmlFor="new-password-again">
              <AuthSecret
                id="new-password-again"
                autoComplete="new-password"
                value={again}
                invalid={again.length > 0 && again !== next}
                onChange={(event) => setAgain(event.target.value)}
              />
            </AuthBlock>
            <AuthConditions items={conditions} />

            {error ? (
              <div className="mt-16">
                <ErrorNote message={error} />
              </div>
            ) : null}

            <button type="submit" className="t2-button primary ad-login-submit" disabled={busy || !ready}>
              {busy ? "…" : "غيّر كلمة المرور"}
            </button>

            <div className="ad-login-links">
              {forced ? (
                <button
                  type="button"
                  className="ad-login-back"
                  onClick={() => void signOut().then(() => navigate("/login"))}
                >
                  خروج
                </button>
              ) : (
                <button type="button" className="ad-login-back" onClick={() => navigate(-1)}>
                  رجوع إلى اللوحة
                </button>
              )}
            </div>
          </form>

          <p className="ad-login-foot">
            وكلمةٌ نُسيت لا تُستعاد من هنا — تُعاد من الخادم وحدَه.
          </p>
        </div>
      </div>
    </div>
  );
}
