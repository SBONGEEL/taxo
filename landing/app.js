/** ما يُحقن في الصفحة — **قراءةٌ محضة، ولا نداءَ يكتب** (شرطُ المالك).
 *
 * وثلاثةُ أشياءَ تُقرأ ولا تُكتب في الصفحة:
 *
 * **١) العرضُ من الخلفية** — «الشهر الأول مجاناً» **لا يُكتب نصّاً**. فعرضٌ
 * أُطفئ أو نفد سقفُه أو انتهى تاريخُه **يختفي سطرُه من نفسه**، بلا سطرٍ يُحذف
 * من هنا. وهي قاعدةُ ورقة الترحيب: **صفحةٌ تعِد بما نفد أسوأُ من صفحةٍ صامتة**.
 *
 * **٢) بيانُ الحزمة من `manifest.json`** المولَّد من الملفّ نفسِه — لا رقمَ
 * نسخةٍ مكتوبٌ بيد. **وقد قِيس أن الرقمَ وحدَه لا يفرّق**: الحزمتان تقولان
 * `1.0`، ونسختان بفارق خمسةِ أيامٍ وستةِ ميجابايت تحملان الرقمَ نفسَه. فالهويةُ
 * **بصمةٌ وتاريخ**.
 *
 * **٣) والدعمُ من `config.js`** — يُبدَّل بلا لمسِ صفحة.
 *
 * **والفشلُ صامتٌ في الثلاثة**: صفحةٌ تعريفيةٌ لا تُكسر لأن نداءً تعثّر. وما
 * لا يصل **لا يُرسم**، ولا مكانَ فارغٌ محجوز.
 */
(() => {
  const cfg = window.TAXO_LANDING ?? {};
  const $ = (id) => document.getElementById(id);

  // ــــ الدعم
  const phone = cfg.support?.phone;
  if (phone) {
    $("call").textContent = phone;
    $("call").href = `tel:${phone}`;
  }
  if (cfg.support?.whatsapp) $("wa").href = `https://wa.me/${cfg.support.whatsapp}`;

  // ــــ أزرارُ التحميل: **المصدرُ إعدادٌ لا رابطٌ مكتوب**
  const mb = (n) => (n / 1048576).toFixed(1);
  const day = (iso) =>
    new Date(iso).toLocaleDateString("ar-u-nu-latn", {
      year: "numeric", month: "long", day: "numeric",
    });

  // **مصدرٌ غائب ⇒ لا زرَّ ولا مكانَ محجوز** (شرطُ المالك 2026-08-21).
  // ويُخرَج العنوانُ معه: عنوانٌ فوق فراغٍ أسوأُ من زرٍّ معطَّل — يُقرأ عطباً.
  // **ولا يُطلب البيانُ أصلاً**: نداءٌ لا يقرؤه أحدٌ عملٌ على لا شيء.
  // **ولا يُخرَج من الدالة هنا**: تحتَها سطرُ العرضِ القائم، والصفحةُ تبقى
  // حيّةً بمحتواها — فالإخفاءُ للتحميل وحدَه.
  const DOWNLOAD_SOURCES = ["apk", "play"];
  const downloadsHidden = !DOWNLOAD_SOURCES.includes(cfg.source);
  if (downloadsHidden) {
    for (const id of ["dl-heading", "dl-rider", "meta-rider", "dl-driver",
                      "meta-driver", "install-help", "presign-note"]) {
      $(id)?.remove();
    }
  }

  if (!downloadsHidden)
  fetch("./downloads/manifest.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((manifest) => {
      for (const key of ["rider", "driver"]) {
        const btn = $(`dl-${key}`);
        const meta = $(`meta-${key}`);
        const play = cfg.play?.[key];
        if (cfg.source === "play" && play) {
          btn.href = play;
          meta.textContent = "من Google Play";
          continue;
        }
        const app = manifest?.apps?.find((a) => a.key === key);
        if (!app) {
          // **زرٌّ بلا ملفٍّ يُخفى، ولا يشير إلى لا شيء**
          btn.remove();
          meta.remove();
          continue;
        }
        btn.href = `./downloads/${app.file}`;
        btn.setAttribute("download", app.file);
        // **البصمةُ معروضةٌ لا مخفيّة**: من يشتكي نسأله عنها، ومن يحمّل يعرف
        // ما حمّل. والرقمُ وحدَه لا يفرّق بناءً عن بناء
        meta.textContent =
          `${app.version_name ?? "1.0"} · بناء ${app.sha256.slice(0, 8)} · ` +
          `${day(app.built_at)} · ${mb(app.size_bytes)} م.ب`;
      }
      // **شرحُ التثبيت يخصّ APK وحدَه**: يومَ يصير المصدرُ المتجرَ يختفي معه
      if (cfg.source === "play") {
        $("install-help")?.remove();
        // **وتنبيهُ ما قبل التوقيع يذهب معه**: يخصّ نسخةَ ما قبل المتجر
        $("presign-note")?.remove();
      }
    })
    .catch(() => {
      $("dl-rider")?.remove();
      $("dl-driver")?.remove();
      $("install-help")?.remove();
      $("presign-note")?.remove();
    });

  // ــــ العرضُ القائم
  if (!cfg.api) return;
  fetch(`${cfg.api}/public/landing?country_code=${cfg.country ?? "JO"}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      const offer = data?.offer;
      if (!offer) return; // **لا سطر** — وهو المطلوب
      const label = { JOD: "د.أ", LYD: "د.ل" }[offer.currency] ?? offer.currency;
      $("offer-title").textContent = offer.free
        ? `${offer.plan_name} مجاناً`
        : `${offer.plan_name} بـ${offer.price_after} ${label}`;
      $("offer-sub").innerHTML = offer.free
        ? offer.name
        : `${offer.name} — <span class="old">${offer.price} ${label}</span>`;
      $("offer").style.display = "block";
    })
    .catch(() => undefined);
})();
