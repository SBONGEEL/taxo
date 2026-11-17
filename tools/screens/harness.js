/* **مُشغِّلُ اللقطات داخل الصفحة** (أمرُ المالك ٢٠٢٦-١١-١٧) — يُحقن أوّلَ `<head>` في **حزمة اللقطات وحدَها** (`prepare-dist.mjs`)، ولا يُشحن.
 *
 * يقرأ أمراً من خادم اللقطات (`server.mjs › /__shot`) كلَّ ٤٠٠ ms وينفّذه مرّةً، ثمّ يردّ بـ`/__shot/ack`:
 *   reset {storage}   — يمحو التخزين ويضع ما يُعطى ثمّ يُعيد التحميل (الدخولُ في العرض، والسمةُ، واللغة)
 *   nav {path}        — ينتقل كما ينتقل الرابطُ في التطبيق (`pushState` + `popstate`)
 *   click {text}      — يضغط أصغرَ عنصرٍ ظاهرٍ يبدأ نصُّه بالنصّ (أو `selector`)
 *   type {text}       — يكتب في الحقل المركَّز، أو أوّلِ حقلٍ ظاهر، كما يكتب المستخدم (حدثُ `input`)
 *   back              — `history.back()`
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
  function find(cmd) {
    if (cmd.selector) {
      var list = Array.prototype.filter.call(document.querySelectorAll(cmd.selector), visible);
      return list[cmd.nth || 0] || null;
    }
    var want = cmd.text;
    var all = Array.prototype.filter.call(document.querySelectorAll("body *"), function (el) {
      var own = (el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || "").trim();
      return own && own.indexOf(want) === 0 && visible(el);
    });
    all.sort(function (a, b) {
      return (a.innerText || "").length - (b.innerText || "").length;
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
        history.back();
        return reply(cmd.id, true, "back");
      }
      if (cmd.kind === "click") {
        var el = find(cmd);
        if (!el) return reply(cmd.id, false, "لا عنصرَ: " + (cmd.text || cmd.selector));
        el.click();
        return reply(cmd.id, true, (el.innerText || el.tagName).trim().slice(0, 40));
      }
      if (cmd.kind === "type") return reply(cmd.id, typeInto(cmd.text), cmd.text);
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
