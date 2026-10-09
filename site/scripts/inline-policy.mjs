/** يخبز نصَّ الوثيقة في HTML **وقت البناء** — قرارُ المالك ٢٠٢٦-٠٩-٠٧.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة
 *
 * `/privacy` و`/terms` كانتا تجيبان **٢٠٠ ونصُّهما ليس فيهما**: HTML الخام
 * يحمل `data-doc` و«جارٍ تحميل النصّ…»، **والنصُّ يُجلب بجافاسكربت**.
 * **ومراجعُ المتجر بشرٌ يراه، وزاحفٌ آليٌّ يرى صفحةً بلا سياسة** — وGoogle Play
 * يشترط أن **تكون** السياسةُ على الرابط لا أن تُجلب إليه.
 *
 * **ولمَ لا `<noscript>` يحمل النصّ** (الفرع «ب» المرفوض، بنصِّ المالك): ذاك
 * **يُري الزاحفَ نصّاً لا يراه الإنسان** — **وهو بذاته ما يُقرأ حيلةً في
 * تدقيق المتجر**. **والخبزُ يجعل ما يراه الزاحفُ هو ما يراه الإنسانُ حرفاً.**
 *
 * ## وثمنُه معلَنٌ ومقبول
 *
 * **نصٌّ يُخبز يبلى**: تعديلُ الوثيقة من اللوحة **لا يبلغ الصفحةَ حتى تُبنى**.
 * **والمالكُ قَبِله صراحةً**، وشرطُ ألّا يكون خطوةً تُنسى:
 *
 * · **الخادمُ يبني `site` في كلِّ رفع** (`deploy.sh`، البوّابةُ الخامسة) —
 *   فالرفعُ هو مسارُ التحديث، **لا أمرٌ يُتذكَّر**.
 * · **والبوّابةُ السادسةُ تقارن النسخةَ المخبوزةَ بالحيّة** فتصيح إن بليت —
 *   **وقاعدةٌ تُطبَّق لا قاعدةٌ تُتذكَّر**.
 *
 * ## وما لا يفعله — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * · **لا يخترع نصّاً**: يقرأ المنشورَ من الباب العامّ. وغيابُه **يُسقط البناء**
 *   ولا يكتب صفحةً فارغة — **فصفحةُ سياسةٍ فارغةٍ أسوأُ من بناءٍ يسقط**.
 * · **ولا يهرب من `HTML`**: النصُّ عربيٌّ عاديٌّ من قاعدتنا، **ومع ذلك يُهرَّب**
 *   `& < >` — فحرفٌ واحدٌ في وثيقةٍ قانونيةٍ يكسر الصفحة.
 */

const API = process.env.TAXO_POLICY_API || "https://api.tajora.ly/api/v1/public";

//: **الصفحاتُ الأربعُ وما تحمله** — والمصدرُ هنا لا في أربعة ملفّاتِ HTML.
export const POLICY_PAGES = {
  "privacy.html": { doc: "privacy_policy", app: "rider" },
  "terms.html": { doc: "terms_of_use", app: "rider" },
  "driver-privacy.html": { doc: "privacy_policy", app: "driver" },
  "driver-terms.html": { doc: "terms_of_use", app: "driver" },
};

const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** **سطرُ القسم** — «١) …» أو كتلةٌ من سطرٍ واحدٍ قصيرٍ بلا علامةِ وقف («محادثةُ الرحلة ومكالمتُها»). */
const NUMBERED = /^[0-9٠-٩]+\)\s/;
const isHeading = (line, alone) => NUMBERED.test(line) || (alone && line.length <= 60 && !/[.:،؛!?؟—-]$/.test(line));

/** يحوّل النصَّ الخامَ إلى وسم — **والحروفُ كما كتبها المُحرِّر بلا زيادةٍ ولا نقص** (SPEC §٧١-ج/١٠: الشكلُ يتغيّر لا الصياغة).
 *
 * · **سطرٌ فارغٌ يفصل الكتل**، كما كان.
 * · **سطرُ القسم عنوانٌ** (`<h2>`): أوّلُ سطرٍ يبدأ برقمٍ وقوس، أو كتلةٌ من سطرٍ واحدٍ قصيرٍ بلا وقف.
 * · **«- » يبدأ بنداً** (`<li>`)، **والسطرُ الذي يليه بلا «- » تكملتُه** — المحرِّرُ يكسر الأسطرَ بيده عند ثمانين حرفاً،
 *   فكسرُه مسافةٌ لا `<br>`: نصٌّ مكسورٌ بيدٍ على شاشة هاتفٍ يُقرأ أسطراً مبتورة. **وكذلك في الفقرة.**
 * · **و«- » نفسُها تُنزع من البند** — النقطةُ ترسمها الورقة؛ وهذا الحرفُ وحدَه ما لا يظهر، وهو علامةٌ لا كلمة.
 */
export function paragraphs(body) {
  const out = [];
  for (const block of body.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean)) {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    let i = 0;
    if (isHeading(lines[0], lines.length === 1)) {
      out.push(`<h2>${esc(lines[0])}</h2>`);
      i = 1;
    }
    let para = [];
    let items = null;
    const flushPara = () => {
      if (para.length) out.push(`<p>${esc(para.join(" "))}</p>`);
      para = [];
    };
    const flushList = () => {
      if (items) out.push(`<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`);
      items = null;
    };
    for (; i < lines.length; i += 1) {
      const line = lines[i];
      if (line.startsWith("- ")) {
        flushPara();
        items = items || [];
        items.push(line.slice(2));
      } else if (items) {
        items[items.length - 1] += ` ${line}`;
      } else {
        para.push(line);
      }
    }
    flushPara();
    flushList();
  }
  return out.join("\n");
}

async function fetchPolicy({ doc, app }) {
  const url = `${API}/policy?doc_type=${doc}&app=${app}`;
  let res;
  try {
    res = await fetch(url, { signal: AbortSignal.timeout(20000) });
  } catch (err) {
    throw new Error(
      `تعذّر الوصول إلى ${url} — ${err.message}\n` +
        "  **والبناءُ يسقط ولا يكتب صفحةً فارغة.**\n" +
        "  للبناء بلا خبزٍ (تطويرٌ محليّ): TAXO_POLICY_API عنواناً يعمل.",
    );
  }
  if (!res.ok) throw new Error(`${url} أجاب ${res.status} — يُوقَف.`);
  const doc_ = await res.json();
  if (!doc_ || !doc_.body_ar) {
    throw new Error(
      `${url} أجاب بلا نصّ (null أو body_ar فارغ).\n` +
        "  **وذلك حالٌ صحيحةٌ في الباب** — وثيقةٌ غيرُ منشورةٍ أو المفتاحُ مطفأ —\n" +
        "  **لكنّها ليست صفحةً تُبنى**: رابطُ المتجر يجب أن يحمل نصّاً.",
    );
  }

  // **ويُقاس أنّ المُعطى هو المطلوب** (وقع مقيساً ٢٠٢٦-٠٩-٠٧): خادمٌ على
  // شيفرةٍ أقدمَ **يتجاهل `app` ويعطي الراكبَ دائماً** — **فخُبزت صفحةُ
  // الكبتن بنصِّ الراكب وصمتَ كلُّ شيء**. والفرقُ ٢٤١٥ حرفاً مقابل ١٦٥٤،
  // **ولم يشكُ أحد** لأن النصَّ صحيحٌ في نفسه وخاطئٌ في موضعه.
  //
  // **وصفحةُ سياسةٍ تحمل نصَّ تطبيقٍ آخر أسوأُ من صفحةٍ فارغة**: الفارغةُ
  // تُرى، وهذه تُقرأ صحيحةً في تدقيق المتجر وهي ليست وثيقةَ ذلك التطبيق.
  if (doc_.app === undefined) {
    throw new Error(
      `${url} أجاب بلا حقل \`app\` — **خادمٌ على شيفرةٍ أقدمَ من هذا البناء**.\n` +
        "  وتلك النسخةُ **تتجاهل `app` وتعطي الراكبَ دائماً**، فصفحةُ الكبتن\n" +
        "  تُخبز بنصِّ الراكب. **يُوقَف: ارفع الخلفيةَ أوّلاً ثمّ ابنِ الموقع.**",
    );
  }
  if (doc_.app !== app) {
    throw new Error(
      `${url}: طُلب \`${app}\` وأُعطي \`${doc_.app}\` — يُوقَف.`,
    );
  }
  return doc_;
}

/** ملحقُ vite — يستبدل العلامتين في كلِّ صفحةِ سياسة. */
export function inlinePolicyPlugin() {
  return {
    name: "taxo-inline-policy",
    apply: "build",
    async transformIndexHtml(html, ctx) {
      const name = (ctx.path || "").replace(/^\//, "");
      const want = POLICY_PAGES[name];
      if (!want) return html;

      const doc = await fetchPolicy(want);
      const when = String(doc.published_at || "").slice(0, 10);
      const meta =
        `النسخة <span dir="ltr" style="unicode-bidi:isolate">${doc.version}</span>` +
        (when ? ` — نُشرت <span dir="ltr" style="unicode-bidi:isolate">${when}</span>` : "");

      console.log(
        `  ✓ خُبزت ${name} · ${want.app}/${want.doc} · v${doc.version} · ${doc.body_ar.length} حرفاً`,
      );

      return html
        .replace("<!--POLICY_BODY-->", paragraphs(doc.body_ar))
        .replace("<!--POLICY_META-->", meta)
        .replace("<!--POLICY_VERSION-->", String(doc.version));
    },
  };
}
