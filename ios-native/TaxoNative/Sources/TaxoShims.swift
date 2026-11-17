import Foundation

/// **سدّادتان في الويب، تُحقنان قبل أيِّ سطرٍ من الشاشات** (`atDocumentStart`).
///
/// - `navigator.vibrate` — غائبةٌ في WKWebView، والشاشاتُ تحرسها بـ`"vibrate" in navigator` فلا تهتزّ على iOS أصلاً.
///   تُسدّ بملحق `Haptics` الأصليّ: النبضُ القصيرُ لمسةٌ (`UIImpactFeedbackGenerator`)، والطويلُ اهتزازُ النظام.
/// - `BarcodeDetector` — غائبٌ في WKWebView، **فزرُّ «امسح رمز QR» في شحن بطاقات TAXO لا يُرسم على iOS**.
///   يُسدّ بـ`QrReader` (Vision) **في الجهاز نفسِه**: الصورةُ لا تُرفع إلى أيِّ خادم، كما يعد نصُّ الشاشة.
///
/// **والنداءُ بـ`Capacitor.nativePromise`** — أدنى أبواب الجسر، فلا تُسجَّل الأسماءُ مرّتين مع `registerPlugin`.
enum TaxoShims {
    static let source = #"""
(function () {
  if (window.__taxoShims) return;
  window.__taxoShims = true;
  function native(plugin, method, options) {
    var cap = window.Capacitor;
    if (!cap || typeof cap.nativePromise !== "function") return Promise.reject(new Error("no bridge"));
    return cap.nativePromise(plugin, method, options || {});
  }
  if (!("vibrate" in navigator)) {
    navigator.vibrate = function (pattern) {
      var list = Array.isArray(pattern) ? pattern : [Number(pattern) || 0];
      var on = list.filter(function (_, i) { return i % 2 === 0; });
      var total = on.reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
      if (total <= 0) return true;
      native("Haptics", "vibrate", { pattern: list.map(function (v) { return Number(v) || 0; }) }).catch(function () {});
      return true;
    };
  }
  if (!("BarcodeDetector" in window) && typeof createImageBitmap === "function") {
    var Detector = function (options) {
      this.formats = (options && options.formats) || ["qr_code"];
    };
    Detector.getSupportedFormats = function () { return Promise.resolve(["qr_code"]); };
    Detector.prototype.detect = function (source) {
      try {
        var w = source.width || source.videoWidth || source.naturalWidth || 0;
        var h = source.height || source.videoHeight || source.naturalHeight || 0;
        if (!w || !h) return Promise.resolve([]);
        var scale = Math.min(1, 2048 / Math.max(w, h));
        var canvas = document.createElement("canvas");
        canvas.width = Math.round(w * scale);
        canvas.height = Math.round(h * scale);
        canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
        var data = canvas.toDataURL("image/jpeg", 0.92).split(",")[1];
        return native("QrReader", "detect", { image: data }).then(function (answer) {
          return ((answer && answer.codes) || []).map(function (value) {
            return { rawValue: value, format: "qr_code", boundingBox: null, cornerPoints: [] };
          });
        });
      } catch (error) {
        return Promise.reject(error);
      }
    };
    window.BarcodeDetector = Detector;
  }
})();
"""#
}
