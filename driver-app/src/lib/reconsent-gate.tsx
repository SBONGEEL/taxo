/** شاشةُ إعادة القبول — **قرارُ المالك ٢٠٢٦-١٠-١٨** (SPEC §٧٦-ع/٧ البند ٣).
 *
 * **حين تكون النسخةُ التي قبلها المستخدمُ أقدمَ ممّا يُبرئ** (`min_accepted_version` للمنشورة — والناشرُ يرفعه حين يطلب إعادةَ
 * القبول): شاشةٌ واضحةٌ **بما تغيّر، والنصِّ الكامل، وزرِّ «أوافق»**. **والحكمُ كلُّه في الخلفية** (`GET /account/policies/pending`):
 * أيُّ نسخةٍ تُبرئ، وما الأسطرُ التي تغيّرت — **وهنا عرضٌ وحدَه**. و«أوافق» يكتب القبولَ بتاريخه ونسخته (`POST …/accept`).
 *
 * **ونسخةٌ واحدةٌ في التطبيقين، متطابقةٌ بايتاً** (ومعها `reconsent-gate.css`) — والتطبيقُ يُمرَّر لا يُكتب فيها.
 *
 * **وشبكةٌ ساقطةٌ لا تحجب أحداً** — كبوّابة التحديث: خطأٌ في السؤال يُقرأ «لا شيءَ ينتظر»، ويُسأل ثانيةً عند العودة إلى التطبيق.
 * **والتطبيقُ يبقى تحتها حيّاً** خلافاً لبوّابة التحديث: رحلةٌ جاريةٌ لا يُقطع مقبسُها لأن نصّاً نُشر — والشاشةُ فوقه حتى «أوافق».
 * **ومخرجٌ ثانٍ صادق**: من لا يوافق يخرج من حسابه — لا زرَّ «لاحقاً» يجعل الموافقةَ اختياريّة.
 */
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { acceptPolicies, pendingPolicies } from "@/api/endpoints";
import type { PendingPolicy } from "@/api/types";
import { language, tr } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import { Icon } from "@/taxo2";
import "./update-gate.css";
import "./reconsent-gate.css";

const TITLE: Record<string, string> = {
  privacy_policy: tr("سياسة الخصوصية"),
  terms_of_use: tr("شروط الاستخدام"),
};

/** **نصُّ لغة الهاتف إن وُجد** — والعربيُّ لما سواه، كما في التسجيل (`PolicyConsentT2`). */
function localized(doc: PendingPolicy): { body: string; changes: string[] | null } {
  if (language === "fr" && doc.body_fr) return { body: doc.body_fr, changes: doc.changes_fr };
  return { body: doc.body_ar, changes: doc.changes_ar };
}

export function ReconsentGate({ app }: { app: "rider" | "driver" }) {
  const { user, signOut } = useSession();
  const [docs, setDocs] = useState<PendingPolicy[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const userId = user?.id ?? null;

  const ask = useCallback(() => {
    if (!userId) {
      setDocs([]);
      return;
    }
    pendingPolicies(app)
      .then((answer) => setDocs(answer.pending))
      .catch(() => undefined);
  }, [app, userId]);

  useEffect(() => {
    ask();
    const onVisible = () => {
      if (document.visibilityState === "visible") ask();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [ask]);

  const agree = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const answer = await acceptPolicies(app, docs.map((doc) => doc.id));
      setDocs(answer.pending);
      setOpen(null);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : tr("تعذّر حفظ موافقتك — تحقّق من الاتصال وأعد المحاولة."));
      // **نسخةٌ أحدثُ نُشرت بين الفتح والضغط**: الخلفيةُ ترفض، والشاشةُ تعيد السؤالَ بالنصّ الحاليّ
      ask();
    } finally {
      setBusy(false);
    }
  }, [app, docs, ask]);

  if (!userId || !docs.length) return null;
  return (
    <div className="t2 t2-update t2-reconsent" role="alertdialog" aria-modal="true" aria-labelledby="t2-reconsent-title">
      <div className="t2-update-card">
        <div className="t2-update-scroll">
          <span className="t2-update-mark" aria-hidden="true">
            <Icon name="verified_user" />
          </span>
          <h1 id="t2-reconsent-title" className="t2-update-title">
            {tr("حدّثنا شروطَنا")}
          </h1>
          <p className="t2-update-text">{tr("اقرأ ما تغيّر، ثم اضغط «أوافق» للمتابعة.")}</p>
          {docs.map((doc) => {
            const { body, changes } = localized(doc);
            const shown = open === doc.id;
            return (
              <section key={doc.id} className="t2-reconsent-doc">
                <h2>
                  {TITLE[doc.doc_type] ?? doc.doc_type}
                  <span className="t2-num" dir="ltr">
                    v{doc.version}
                    {doc.published_at ? ` · ${doc.published_at.slice(0, 10)}` : ""}
                  </span>
                </h2>
                {doc.accepted_version === null ? (
                  <p className="t2-reconsent-note">{tr("لم توافق على هذه الوثيقة من قبل.")}</p>
                ) : (
                  <>
                    <p className="t2-reconsent-note">
                      {tr("ما تغيّر منذ النسخة {0} التي وافقتَ عليها:", { 0: String(doc.accepted_version) })}
                    </p>
                    {changes?.length ? (
                      <ul className="t2-reconsent-changes">
                        {changes.map((line, index) => (
                          <li key={index}>{line.replace(/^[-•]\s*/, "")}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="t2-reconsent-note">{tr("لا تغيير في المضمون سوى تاريخ التحديث.")}</p>
                    )}
                  </>
                )}
                <button
                  type="button"
                  className="t2-reconsent-full"
                  aria-expanded={shown}
                  onClick={() => setOpen(shown ? null : doc.id)}
                >
                  <Icon name={shown ? "close" : "open_in_full"} />
                  {shown ? tr("إخفاء النص الكامل") : tr("اقرأ النص الكامل")}
                </button>
                {shown ? (
                  <div className="t2-reconsent-body">
                    {body.split(/\n{2,}/).map((para, index) => (para.trim() ? <p key={index}>{para.trim()}</p> : null))}
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
        {error ? (
          <p className="t2-reconsent-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="button" className="t2-button action t2-update-go" disabled={busy} onClick={() => void agree()}>
          {tr("أوافق")}
        </button>
        <button type="button" className="t2-reconsent-out" disabled={busy} onClick={() => void signOut()}>
          {tr("لا أوافق — تسجيل الخروج")}
        </button>
      </div>
    </div>
  );
}
