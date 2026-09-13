(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  function nativePlatform() {
    var C = root.Capacitor;
    return !!(C && typeof C.isNativePlatform === "function" && C.isNativePlatform());
  }

  function translationPlugin() {
    if (!nativePlatform()) return null;
    var C = root.Capacitor;
    var plugins = (C && C.Plugins) || {};
    return plugins.Translation || null;
  }

  ATC.isNativeApp = nativePlatform;

  ATC.nativeMtAvailable = function () {
    var p = translationPlugin();
    return !!(p && typeof p.translate === "function");
  };

  ATC.nativeMtStatus = function () {
    var p = translationPlugin();
    if (!p || typeof p.getDownloadedModels !== "function") {
      return Promise.resolve({ native: false, ready: false, languages: [] });
    }
    return p.getDownloadedModels().then(function (res) {
      var langs = (res && res.languages) || [];
      var ready = langs.indexOf("en") >= 0 && langs.indexOf("vi") >= 0;
      return { native: true, ready: ready, languages: langs };
    }).catch(function () {
      return { native: true, ready: false, languages: [] };
    });
  };

  ATC.prepareNativeMt = function (onProgress) {
    var p = translationPlugin();
    if (!p) return Promise.resolve(false);
    function dl(lang, frac) {
      if (onProgress) onProgress(frac);
      return p.downloadModel({ language: lang });
    }
    return ATC.nativeMtStatus().then(function (st) {
      if (st.ready) return true;
      return dl("en", 0.2)
        .then(function () {
          return dl("vi", 0.7);
        })
        .then(function () {
          if (onProgress) onProgress(1);
          return true;
        });
    });
  };

  ATC.nativeTranslate = function (text, source, target) {
    var p = translationPlugin();
    if (!p || typeof p.translate !== "function") {
      return Promise.reject(new Error("no-native-mt"));
    }
    return p
      .translate({
        text: String(text || ""),
        sourceLanguage: source,
        targetLanguage: target
      })
      .then(function (res) {
        return res && res.text ? String(res.text) : "";
      });
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
