/* **مُشغِّلُ اللقطات داخل الصفحة** (أمرُ المالك ٢٠٢٦-١١-١٧) — يُحقن أوّلَ `<head>` في **حزمة اللقطات وحدَها** (`prepare-dist.mjs`)، ولا يُشحن.
 *
 * يقرأ أمراً من خادم اللقطات (`server.mjs › /__shot`) كلَّ ٤٠٠ ms وينفّذه مرّةً، ثمّ يردّ بـ`/__shot/ack`:
 *   reset {storage}   — يمحو التخزين ويضع ما يُعطى ثمّ يُعيد التحميل (الدخولُ في العرض، والسمةُ، واللغة)
 *   nav {path}        — ينتقل كما ينتقل الرابطُ في التطبيق (`pushState` + `popstate`)
 *   click {text}      — يضغط أصغرَ عنصرٍ ظاهرٍ يبدأ نصُّه بالنصّ (أو `selector`)
 *   type {text}       — يكتب في الحقل المركَّز، أو أوّلِ حقلٍ ظاهر، كما يكتب المستخدم (حدثُ `input`)
 *   back              — `history.back()`
 *   show {selector}   — يمرّر إلى العنصر بلا ضغط
 *   tiles {timeout}   — **ينتظر بلاطاتِ الخريطة** حتى يسكن عاملُها: لا طلبَ معلّقٌ ولا جديدٌ ١٫٥ ث (أمرُ المالك ٢٠٢٦-١١-١٨ —
 *                       خريطةٌ فارغةٌ خلف ورقة المسار في لوحات 44287823952)
 *   native {plugin, method, options, after}
 *                     — **ينادي ملحقاً أصليّاً بالجسر نفسِه** الذي ينادي به التطبيق (`Capacitor.nativePromise`) ببياناتِ تجربة:
 *                       النشاطُ الحيُّ والمكالمةُ واختصاراتُ الأيقونة تُرسم من شيفرتها الحقيقيّة (`tools/screens/native/`). و`after` يؤجّله
 *                       بالمللي ثانية — لمكالمةٍ تصل والجهازُ مقفل
 *   expect {any}      — **يقيس الشاشةَ المقصودة**: ينتظر حتى `timeout` عنصراً منها (نصّاً أو `selector`) **داخل الشاشة**، ويردّ بما وجد
 *                       أو بما يُرى بدلَه. **فالصفُّ «بلغ» بعلامةٍ من شاشته لا بنجاح ضغطة** (أمرُ المالك ٢٠٢٦-١١-١٨).
 * **ولا يقرأ شيئاً ولا يرسل شيئاً غيرَ جوابه** — يضغط ويكتب كما تضغط اليدُ وتكتب. */
(function () {
  var SERVER = "http://127.0.0.1:8787";
  var DONE = "taxo.shot.done";

  // **شبكةُ عامل الخريطة تُعدّ** — MapLibre يجلب البلاطاتِ والخطوطَ داخل عاملٍ من `blob:` لا تراه الصفحة. فيُلفّ العاملُ بمقدّمةٍ
  // تعدّ طلباته وتبثّها على قناةٍ (`BroadcastChannel`) لا على رسائله — فلا يُمسّ بروتوكولُه. **وفي حزمة اللقطات وحدَها.**
  var net = { pending: 0, last: 0, seen: 0 };
  try {
    var channel = new BroadcastChannel("shots-net");
    channel.onmessage = function (e) {
      net.last = Date.now();
      if (e.data === "s") { net.pending++; net.seen++; }
      else if (e.data === "e") net.pending = Math.max(0, net.pending - 1);
    };
    var RealWorker = window.Worker;
    var Wrapped = function (url, options) {
      if (typeof url === "string" && url.indexOf("blob:") === 0 && !(options && options.type === "module")) {
        var prelude = "(function(){var c=new BroadcastChannel('shots-net');var f=self.fetch;if(f){self.fetch=function(){c.postMessage('s');" +
          "return f.apply(this,arguments).then(function(r){c.postMessage('e');return r;},function(x){c.postMessage('e');throw x;});};}})();" +
          "importScripts(" + JSON.stringify(url) + ");";
        url = URL.createObjectURL(new Blob([prelude], { type: "text/javascript" }));
      }
      return new RealWorker(url, options);
    };
    Wrapped.prototype = RealWorker.prototype;
    window.Worker = Wrapped;
  } catch (e) {}

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
  /** **فوقَ غيره لا تحته** — خانةُ `#password` كانت في الصفحة تحت شاشة الترحيب («وقتك بيدك») وتحت «غيرُ متاحٍ في منطقتك»، فقُرئت العلامةُ ✓
   *  والصورةُ شاشةٌ أخرى؛ واختير زرُّ «دخول» المعطَّلُ في النموذج المحجوب بدلَ زرِّ الترحيب (لوحاتُ 44255793642). فيُسأل المتصفّحُ: ما الذي
   *  تحت مركز العنصر حقّاً؟ */
  function onTop(el) {
    var r = el.getBoundingClientRect();
    var h = window.visualViewport ? window.visualViewport.height : innerHeight;
    var x = Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1);
    var y = Math.min(Math.max(r.top + r.height / 2, 1), h - 1);
    var hit = document.elementFromPoint(x, y);
    if (!hit) return false;
    return el === hit || el.contains(hit) || (hit.contains(el) && hit !== document.body && hit !== document.documentElement);
  }
  /** **أخطاءُ الصفحة تُحفظ لتُكتب تحت الصفّ الأحمر** — شاشةُ «حدث خطأ في هذه الشاشة» بعد «قبول» لم يكن لها أثرٌ في logcat ولا في
   *  سجلّ iPhone (44223334154)، فلا يُعرف سببُها إلا من الصفحة نفسِها. حدُّ الخطأ في React يكتب الخطأ بـ`console.error`. */
  var errors = [];
  function keepError(text) {
    errors.push(String(text).replace(/\s+/g, " ").slice(0, 220));
    if (errors.length > 4) errors.shift();
  }
  var consoleError = console.error;
  console.error = function () {
    try {
      keepError(Array.prototype.map.call(arguments, function (a) {
        return a && a.stack ? a.message + " @ " + String(a.stack).split("\n").slice(1, 3).join(" ") : String(a);
      }).join(" "));
    } catch (e) { /* لا يُسقط التسجيلُ الصفحة */ }
    return consoleError.apply(console, arguments);
  };
  window.addEventListener("error", function (event) { keepError("onerror: " + event.message + " @ " + (event.filename || "") + ":" + event.lineno); });
  window.addEventListener("unhandledrejection", function (event) { keepError("rejection: " + (event.reason && event.reason.message || event.reason)); });
  function lastErrors() {
    return errors.length ? " — أخطاءُ الصفحة: " + errors.slice(-2).join(" ‖ ") : "";
  }
  /** **مراقبةُ العلامة بعد قبولها** — كلَّ ١٠٠ ms، ويُحفظ أوّلُ غياب. «متّصل» على Pro Max: كان فحصُ ما بعد اللقطة يجد الطلبَ التالي ثلاثَ
   *  مرّاتٍ فلا يُعرف أوصل أثناء اللقطة (صورةٌ خاطئة) أم بعدها (صورةٌ صحيحة) — 44265505208. فيُسأل عن **وقت** الغياب لا عن الغياب */
  var frozen = false, held = [], heldSeq = 0;
  var realSet = window.setTimeout.bind(window), realClear = window.clearTimeout.bind(window);
  window.setTimeout = function (fn, ms) {
    if (frozen && typeof fn === "function" && (ms || 0) >= 4000) {
      var id = -(++heldSeq);
      held.push({ id: id, fn: fn, ms: ms, args: Array.prototype.slice.call(arguments, 2) });
      return id;
    }
    return realSet.apply(null, arguments);
  };
  window.clearTimeout = function (id) {
    if (typeof id === "number" && id < 0) { held = held.filter(function (h) { return h.id !== id; }); return; }
    return realClear(id);
  };
  function thaw() {
    frozen = false;
    var list = held; held = [];
    list.forEach(function (h) { realSet.apply(null, [h.fn, h.ms].concat(h.args)); });
  }
  var watchTimer = null, lostAt = null;
  function present(any) {
    for (var i = 0; i < any.length; i++) {
      var el = find(any[i]);
      if (el && inView(el) && onTop(el)) return true;
    }
    return false;
  }
  function stopWatch() {
    if (watchTimer !== null) clearInterval(watchTimer);
    watchTimer = null;
    lostAt = null;
  }
  function watchMarker(any) {
    stopWatch();
    watchTimer = setInterval(function () {
      if (lostAt === null && !present(any)) lostAt = Date.now();
    }, 100);
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
      // **الظاهرُ فوق غيره أوّلاً** — ثمّ ترتيبُ الصفحة كما كان
      if (!cmd.nth) list.sort(function (a, b) { return (inView(a) && onTop(a) ? 0 : 1) - (inView(b) && onTop(b) ? 0 : 1); });
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
      var target = el.closest(CLICKABLE) || el;
      return (inView(target) && onTop(target) ? 0 : 2) + (el.matches(CLICKABLE) || el.closest(CLICKABLE) ? 0 : 1);
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
          // **زرٌّ معطَّلٌ لم يجهز بعد** — «رفض» `disabled={busy}`، فنُقر وهو مشغولٌ فلم يحدث شيءٌ والجوابُ ✓ وبقيت بطاقةُ الطلب (Pro Max · 44238489964).
          // فيُنتظر كما تنتظر الإصبعُ زرّاً باهتاً
          if (el && (el.disabled || el.getAttribute("aria-disabled") === "true")) el = null;
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
      // **متى غابت العلامة؟** — بالمللي ثانية منذ غيابها، أو -1 إن بقيت. يُسأل بعد اللقطة فيُعرف أغابت أثناءها أم بعدها
      // **إيقافُ مؤقّتات العرض الطويلة** — طلبٌ محاكى كلَّ ٦ ث يسبق لقطةَ Pro Max البطيئة: صورةُ «متّصل» حملت الطلبَ المرفوض، وصورةُ «طلب رحلة»
      // حملت ما قبل الطلب (44265505208)، أي أن الإطارَ يتأخّر عن الصفحة. فيُمسك كلُّ مؤقّتٍ ≥ ٤ ث حتى يُفرج عنه، ولا تتغيّر الحالُ تحت اللقطة
      if (cmd.kind === "freeze") {
        var count = held.length;
        if (cmd.on) frozen = true;
        else thaw();
        return reply(cmd.id, true, cmd.on ? "أُمسكت المؤقّتات" : "أُفرج عن " + count + " مؤقّت");
      }
      // **انتظارُ الرسم** — إطاران ثم مهلة، فيلحق إطارُ المحاكي بالصفحة قبل اللقطة
      if (cmd.kind === "paint") {
        return requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            setTimeout(function () { reply(cmd.id, true, "رُسم"); }, cmd.ms || 1200);
          });
        });
      }
      if (cmd.kind === "tiles") {
        var tilesFrom = Date.now();
        var tilesWait = function () {
          var quiet = net.pending === 0 && Date.now() - net.last > 1500;
          var waited = Date.now() - tilesFrom;
          if (quiet && (net.seen > 0 || waited > 4000)) {
            // ثمّ إطاران ونصفُ ثانية — ليُرسم ما وصل
            return requestAnimationFrame(function () {
              requestAnimationFrame(function () {
                setTimeout(function () {
                  reply(cmd.id, true, "بلاطات: " + net.seen + " طلباً، ساكنةٌ بعد " + waited + " ms");
                }, 500);
              });
            });
          }
          if (waited > (cmd.timeout || 20000)) return reply(cmd.id, false, "البلاطاتُ لم تسكن في " + waited + " ms (معلّق " + net.pending + ")");
          setTimeout(tilesWait, 250);
        };
        return tilesWait();
      }
      if (cmd.kind === "native") {
        var bridge = window.Capacitor;
        if (!bridge || typeof bridge.nativePromise !== "function") return reply(cmd.id, false, "لا جسرَ أصليّ");
        var callNative = function () {
          return bridge.nativePromise(cmd.plugin, cmd.method, cmd.options || {});
        };
        if (cmd.after) {
          setTimeout(function () {
            callNative().catch(function () {});
          }, cmd.after);
          return reply(cmd.id, true, cmd.plugin + "." + cmd.method + " بعد " + cmd.after + " ms");
        }
        return callNative().then(
          function (result) {
            reply(cmd.id, true, cmd.plugin + "." + cmd.method + " " + JSON.stringify(result || {}).slice(0, 160));
          },
          function (error) {
            reply(cmd.id, false, cmd.plugin + "." + cmd.method + " ✗ " + String((error && error.message) || error));
          }
        );
      }
      if (cmd.kind === "lost") return reply(cmd.id, true, String(lostAt === null ? -1 : Date.now() - lostAt));
      if (cmd.kind === "expect") {
        stopWatch();
        var since = Date.now();
        var offView = null;
        var lastHit = null, lastKey = null;
        var goText = function () {
          var el = document.querySelector(".t2-hm-go");
          return el ? (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 60) : null;
        };
        var goAtStart = goText();
        var look = function () {
          for (var i = 0; i < cmd.any.length; i++) {
            var hit = find(cmd.any[i]);
            if (hit && inView(hit) && onTop(hit)) {
              // **وثابتةٌ في موضعها** — قُرئت «الكبتن في الطريق إليك» والورقةُ تنزلق صاعدةً فصُوِّرت الخريطةُ وحدَها (أندرويد الفاتح · 44255793642)؛
              // فلا تُقبل حتى تقرأ في الموضع نفسِه مرّتين بينهما ٣٠٠ ms
              var r = hit.getBoundingClientRect();
              var key = Math.round(r.top) + ":" + Math.round(r.left) + ":" + Math.round(r.height);
              if (lastHit === hit && lastKey === key) {
                watchMarker(cmd.any);
                return reply(cmd.id, true, "علامة: " + (cmd.any[i].text || cmd.any[i].selector));
              }
              lastHit = hit; lastKey = key;
              if (Date.now() - since < (cmd.timeout || 10000) + 600) return setTimeout(look, 300);
              // **وما لم يسكن في المهلة يُقبل ويُقال** — عنصرٌ يتحرّك أبداً (نبضٌ أو عدّاد) لا يُعلِّق الخطوة
              return reply(cmd.id, true, "علامة (لم تسكن): " + (cmd.any[i].text || cmd.any[i].selector));
            }
            if (hit) offView = cmd.any[i].text || cmd.any[i].selector;
          }
          if (Date.now() - since < (cmd.timeout || 10000)) return setTimeout(look, 300);
          // **وما رآه في المهلة يُقال** — «موجودٌ خارج الشاشة» غيرُ «لم يظهر»، و«الزرُّ قال كذا» يسمّي الطورَ الذي وقف فيه
          var goNow = goText();
          reply(cmd.id, false, "لا علامةَ لـ«" + cmd.any.map(function (m) { return m.text || m.selector; }).join("» أو «") + "»" +
            (offView ? " (وُجد «" + offView + "» خارج الشاشة أو محجوباً تحت غيره)" : "") +
            (goAtStart !== null || goNow !== null ? " — الزرّ أوّلاً: «" + goAtStart + "» وآخراً: «" + goNow + "»" : "") + " — يُرى: " + seen() + lastErrors());
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
