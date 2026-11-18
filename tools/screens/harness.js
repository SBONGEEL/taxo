/* **مُشغِّلُ اللقطات داخل الصفحة** (أمرُ المالك ٢٠٢٦-١١-١٧) — يُحقن أوّلَ `<head>` في **حزمة اللقطات وحدَها** (`prepare-dist.mjs`)، ولا يُشحن.
 *
 * يقرأ أمراً من خادم اللقطات (`server.mjs › /__shot`) كلَّ ٤٠٠ ms وينفّذه مرّةً، ثمّ يردّ بـ`/__shot/ack`:
 *   reset {storage}   — يمحو التخزين ويضع ما يُعطى ثمّ يُعيد التحميل (الدخولُ في العرض، والسمةُ، واللغة)
 *   nav {path}        — ينتقل كما ينتقل الرابطُ في التطبيق (`pushState` + `popstate`)
 *   click {text}      — يضغط أصغرَ عنصرٍ ظاهرٍ يبدأ نصُّه بالنصّ (أو `selector`)
 *   type {text}       — يكتب في الحقل المركَّز، أو أوّلِ حقلٍ ظاهر، كما يكتب المستخدم (حدثُ `input`)
 *   back              — `history.back()`
 *   show {selector}   — يمرّر إلى العنصر بلا ضغط
 *   expect {any}      — **يقيس الشاشةَ المقصودة**: ينتظر حتى `timeout` عنصراً منها (نصّاً أو `selector`) **داخل الشاشة**، ويردّ بما وجد
 *                       أو بما يُرى بدلَه. **فالصفُّ «بلغ» بعلامةٍ من شاشته لا بنجاح ضغطة** (أمرُ المالك ٢٠٢٦-١١-١٨).
 * **ولا يقرأ شيئاً ولا يرسل شيئاً غيرَ جوابه** — يضغط ويكتب كما تضغط اليدُ وتكتب. */
(function () {
  var SERVER = "http://127.0.0.1:8787";
  var DONE = "taxo.shot.done";

  // **إذنُ الإشعارات يُجاب «مرفوضاً» قبل أن يبلغ الطبقةَ الأصليّة** — في حزمة اللقطات وحدَها.
  // مقيسٌ في أوّل تشغيلين: نافذةُ iOS الأصليّة غطّت كلَّ لقطة (و`simctl` لا يمنح هذا الإذن)، وعلى أندرويد أغلق التسجيلُ التطبيقَ
  // في غلاف التصحيح بلا Firebase. **فالشاشاتُ تُرسم كما تُرسم لمن رفض الإشعارات** — ولا شيءَ غيرُ هذا الإذن يُمسّ.
  function quietPush() {
    var cap = window.Capacitor;
    if (!cap || typeof cap.nativePromise !== "function" || cap.__shotQuiet) return !!(cap && cap.__shotQuiet);
    var real = cap.nativePromise;
    cap.nativePromise = function (plugin, method, options) {
      if (plugin === "PushNotifications" && (method === "checkPermissions" || method === "requestPermissions")) {
        return Promise.resolve({ receive: "denied" });
      }
      if (plugin === "PushNotifications" && method === "register") return Promise.resolve();
      return real.apply(cap, arguments);
    };
    cap.__shotQuiet = true;
    return true;
  }
  if (!quietPush()) {
    var tries = 0;
    var timer = setInterval(function () {
      if (quietPush() || ++tries > 200) clearInterval(timer);
    }, 5);
  }

  function done() {
    try {
      return Number(sessionStorage.getItem(DONE) || "0");
    } catch (e) {
      return 0;
    }
  }
  function mark(id) {
    try {
      sessionStorage.setItem(DONE, String(id));
    } catch (e) {}
  }
  function reply(id, ok, note) {
    var x = new XMLHttpRequest();
    x.open("POST", SERVER + "/__shot/ack");
    x.setRequestHeader("Content-Type", "application/json");
    x.send(JSON.stringify({ id: id, ok: ok, note: note || "", path: location.pathname }));
  }
  function visible(el) {
    var r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    var s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.05;
  }
  /** **داخل الشاشة لا في الشجرة وحدها** — زرُّ «خيارات» في ورقةٍ انزلقت تحت حافّة iPhone SE كان «ظاهراً» وضُغط، والصورةُ خريطةٌ فارغة
   *  (التشغيل 44140812843): `visible` يقيس أن له حجماً، وهذا يقيس أن العينَ تراه. */
  function inView(el) {
    var r = el.getBoundingClientRect();
    var h = window.visualViewport ? window.visualViewport.height : innerHeight;
    return r.bottom > 4 && r.top < h - 4 && r.right > 4 && r.left < innerWidth - 4;
  }
  /** **ما يُرى بدلَ العلامة** — عنوانٌ أو أوّلُ نصٍّ ظاهر، ليُكتب تحت الصفّ الأحمر فيُعرف أين وقف التطبيق. */
  function seen() {
    var heads = Array.prototype.filter.call(document.querySelectorAll("h1,h2,[role=heading],[role=status],button"), function (el) {
      return visible(el) && inView(el) && (el.innerText || "").trim();
    });
    return heads.slice(0, 3).map(function (el) { return el.innerText.trim().replace(/\s+/g, " ").slice(0, 30); }).join(" | ");
  }
  /** **لمسةٌ كاملةٌ كما تلمس الإصبع**: ضغطٌ ثمّ رفعٌ ثمّ نقرة، في وسط العنصر — فما يستمع للضغط (أوراقٌ تُسحب) يرى ما تراه اليد.
   *  **وليست هي علّةَ سقوط «خيارات»** — العلّةُ كانت العنصرَ المختار (انظر الترتيبَ في `find`)، وقِيس ذلك قبل أن يُكتب هذا. */
  function tap(el) {
    var r = el.getBoundingClientRect();
    var o = { bubbles: true, cancelable: true, composed: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
      pointerId: 1, pointerType: "touch", isPrimary: true, button: 0 };
    var P = window.PointerEvent || MouseEvent;
    el.dispatchEvent(new P("pointerdown", o));
    el.dispatchEvent(new MouseEvent("mousedown", o));
    el.dispatchEvent(new P("pointerup", o));
    el.dispatchEvent(new MouseEvent("mouseup", o));
    el.click();
  }
  function find(cmd) {
    if (cmd.selector) {
      var list = Array.prototype.filter.call(document.querySelectorAll(cmd.selector), visible);
      return list[cmd.nth || 0] || null;
    }
    var want = cmd.text;
    var all = Array.prototype.filter.call(document.querySelectorAll("body *"), function (el) {
      var own = (el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || "").trim();
      // **اسمُ أيقونة Material يسبق النصَّ في الزرّ** («check قبول») — يُنزع ثمّ يُطابَق (مقيسٌ: «قبول» لم يُوجد على أندرويد)
      var bare = own.replace(/^([a-z_]+\s+)+/, "");
      return own && (own.indexOf(want) === 0 || bare.indexOf(want) === 0) && visible(el);
    });
    // **ما يُضغط أوّلاً، ثمّ الأقصرُ نصّاً** — صفُّ «خيارات» (`div.t2-v2-options`) وزرُّه بداخله يحملان النصَّ نفسَه بطوله، فاختير الصفُّ
    // و`closest` يصعد لا ينزل، فنُقر صندوقٌ لا يفعل شيئاً والجوابُ ✓ (قِيس في Chrome على الحزمة نفسِها ٢٠٢٦-١١-١٨ — وهو سقوطُ «خيارات» على أندرويد).
    var CLICKABLE = "button,a,[role=button],[role=option],[role=tab],label,input,textarea";
    var rank = function (el) {
      return el.matches(CLICKABLE) || el.closest(CLICKABLE) ? 0 : 1;
    };
    all.sort(function (a, b) {
      return rank(a) - rank(b) || (a.innerText || "").length - (b.innerText || "").length;
    });
    var hit = all[cmd.nth || 0];
    if (!hit) return null;
    return hit.closest("button,a,[role=button],[role=option],[role=tab],label,input,textarea") || hit;
  }
  function typeInto(text) {
    var el = document.activeElement;
    if (!el || !/INPUT|TEXTAREA/.test(el.tagName)) {
      el = Array.prototype.filter.call(document.querySelectorAll("input:not([type=hidden]),textarea"), visible)[0];
    }
    if (!el) return false;
    el.focus();
    var proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }
  function run(cmd) {
    if (!cmd || !cmd.id || cmd.id <= done()) return;
    mark(cmd.id);
    try {
      if (cmd.kind === "reset") {
        localStorage.clear();
        var storage = cmd.storage || {};
        for (var k in storage) localStorage.setItem(k, storage[k]);
        reply(cmd.id, true, "reset");
        setTimeout(function () {
          location.replace(cmd.path || "/");
        }, 150);
        return;
      }
      if (cmd.kind === "nav") {
        history.pushState({}, "", cmd.path);
        dispatchEvent(new PopStateEvent("popstate", { state: {} }));
        return reply(cmd.id, true, cmd.path);
      }
      if (cmd.kind === "back") {
        // **الجوابُ قبل الرجوع** — رجوعٌ يغادر الوثيقةَ يقطع طلبَ الجواب فيُقرأ «لا جواب» (كالإعادة أعلاه)
        reply(cmd.id, true, "back");
        setTimeout(function () {
          history.back();
        }, 150);
        return;
      }
      if (cmd.kind === "click") {
        // **ينتظر العنصرَ حتى ٦ ث** — ورقةٌ تنزلق ببطءٍ على iPhone SE لم تكن قد رُسمت بعد ٩٠٠ ms (مقيسٌ: بقي SE على الدبوس)
        var started = Date.now();
        var attempt = function () {
          var el = find(cmd);
          if (!el) {
            // **الاختياريُّ ينتظر أقلّ ولا يُسقط الخطوة** — ورقةٌ تظهر في جهازٍ ولا تظهر في آخر (أذوناتُ أندرويد الأولى)
            if (Date.now() - started < (cmd.optional ? 2500 : 6000)) return setTimeout(attempt, 250);
            if (cmd.optional) return reply(cmd.id, true, "— لا " + (cmd.text || cmd.selector));
            return reply(cmd.id, false, "لا عنصرَ: " + (cmd.text || cmd.selector));
          }
          // **واللمسةُ تأخذ التركيزَ من الحقل كما تأخذه الإصبع** — `click()` البرمجيُّ لا يفعل، فبقيت لوحةُ المفاتيح مفتوحةً بعد اختيار النتيجة
          // على iPhone SE وانزلقت ورقةُ الطلب تحت الحافّة (التشغيل 44140812843). فيُرفع التركيزُ ويُنتظر نزولُ اللوحة قبل الضغط.
          var focused = document.activeElement;
          var typing = focused && focused !== el && /INPUT|TEXTAREA/.test(focused.tagName);
          if (typing) focused.blur();
          // **يُمرَّر إليه أوّلاً كما تمرّر اليد** — «خيارات» تحت حافّة الورقة على أندرويد فضُغط ولم تظهر ورقتُه (التشغيل 44120859563)
          setTimeout(function () {
            el.scrollIntoView({ block: "center" });
            setTimeout(function () {
              tap(el);
              reply(cmd.id, true, (el.innerText || el.tagName).trim().slice(0, 40));
            }, 300);
          }, typing ? 900 : 0);
        };
        return attempt();
      }
      if (cmd.kind === "type") return reply(cmd.id, typeInto(cmd.text), cmd.text);
      // **يُمرَّر إلى عنصرٍ بلا ضغط** — كما يمرّر الكبتنُ الرئيسيّةَ ليبلغ زرَّ الاتصال تحت بطاقة الأذونات على iPhone SE
      if (cmd.kind === "show") {
        var shown = find(cmd);
        if (!shown) return reply(cmd.id, false, "لا عنصرَ: " + (cmd.text || cmd.selector));
        shown.scrollIntoView({ block: "center" });
        return reply(cmd.id, true, "show " + (cmd.text || cmd.selector));
      }
      if (cmd.kind === "expect") {
        var since = Date.now();
        var look = function () {
          for (var i = 0; i < cmd.any.length; i++) {
            var hit = find(cmd.any[i]);
            if (hit && inView(hit)) return reply(cmd.id, true, "علامة: " + (cmd.any[i].text || cmd.any[i].selector));
          }
          if (Date.now() - since < (cmd.timeout || 10000)) return setTimeout(look, 300);
          reply(cmd.id, false, "لا علامةَ لـ«" + cmd.any.map(function (m) { return m.text || m.selector; }).join("» أو «") + "» — يُرى: " + seen());
        };
        return look();
      }
      reply(cmd.id, true, "noop");
    } catch (error) {
      reply(cmd.id, false, String(error));
    }
  }
  setInterval(function () {
    var x = new XMLHttpRequest();
    x.open("GET", SERVER + "/__shot");
    x.onload = function () {
      try {
        run(JSON.parse(x.responseText));
      } catch (e) {}
    };
    x.send();
  }, 400);
})();
