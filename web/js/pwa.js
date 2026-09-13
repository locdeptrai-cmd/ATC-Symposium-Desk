(function () {
  var deferredPrompt = null;

  function isNativeApp() {
    var C = window.Capacitor;
    return !!(C && typeof C.isNativePlatform === "function" && C.isNativePlatform());
  }

  function isIos() {
    var ua = navigator.userAgent || "";
    var iPadOs = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
    return /iPhone|iPad|iPod/i.test(ua) || iPadOs;
  }

  function isStandalone() {
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
      return true;
    }
    return navigator.standalone === true;
  }

  function httpsHint() {
    var host = location.hostname;
    if (host === "localhost" || host === "127.0.0.1") return "";
    if (location.protocol === "https:") return "";
    var httpsPort = location.port === "8765" || !location.port ? "8766" : location.port;
    return "https://" + host + ":" + httpsPort + "/";
  }

  function certHint() {
    var host = location.hostname;
    var port = location.port === "8766" ? "8765" : location.port || "8765";
    return "http://" + host + ":" + port + "/certs/ATC-Desk-CA.cer";
  }

  function setOfflineBadge() {
    var el = document.getElementById("netBadge");
    if (!el) return;
    if (isNativeApp()) {
      el.textContent = "APP MÁY";
      el.className = "badge badge-ok";
      return;
    }
    if (isStandalone() || (navigator.serviceWorker && navigator.serviceWorker.controller)) {
      el.textContent = "ĐÃ LƯU MÁY";
      el.className = "badge badge-ok";
      return;
    }
    if (!window.isSecureContext) {
      el.textContent = "CẦN HTTPS (điện thoại)";
      el.className = "badge badge-off";
      return;
    }
    el.textContent = navigator.onLine ? "Mạng: có (app vẫn chạy local)" : "OFFLINE — đã lưu máy";
    el.className = "badge " + (navigator.onLine ? "badge-ok" : "badge-off");
  }

  function hideBanner() {
    var el = document.getElementById("pwaBanner");
    if (el) el.hidden = true;
    try {
      sessionStorage.setItem("atc-pwa-banner", "1");
    } catch (e) {}
  }

  function bannerHtml() {
    var ios = isIos();
    var secure = window.isSecureContext;
    var httpsUrl = httpsHint();
    var parts = [];
    parts.push("<div class=\"pwa-banner-inner\">");
    parts.push("<strong>Cài ra màn hình chính — dùng offline</strong>");
    if (!secure) {
      parts.push(
        "<p>Điện thoại cần HTTPS để Safari/Chrome lưu app. Mở <a href=\"cai-dat.html\">Cài đặt máy</a>"
      );
      if (httpsUrl) {
        parts.push(" hoặc vào <a href=\"" + httpsUrl + "\">" + httpsUrl + "</a>");
      }
      parts.push(".</p>");
    } else if (ios) {
      parts.push(
        "<p>Safari → nút Chia sẻ → <b>Thêm vào Màn hình chính</b>. Sau đó mở icon ATC Desk, tắt Wi-Fi vẫn dùng được dịch / thuật ngữ / lập trường.</p>"
      );
    } else {
      parts.push(
        "<p>Chrome → menu ⋮ → <b>Cài đặt ứng dụng</b> hoặc <b>Thêm vào màn hình chính</b>. Gói dịch và glossary đã lưu trên máy.</p>"
      );
      parts.push("<button type=\"button\" class=\"primary\" id=\"pwaInstallBtn\">Cài ATC Desk</button>");
    }
    parts.push("<button type=\"button\" class=\"ghost\" id=\"pwaDismiss\">Để sau</button>");
    parts.push("</div>");
    return parts.join("");
  }

  function mountBanner() {
    if (isStandalone()) return;
    try {
      if (sessionStorage.getItem("atc-pwa-banner") === "1") return;
    } catch (e) {}
    if (document.getElementById("pwaBanner")) return;
    var aside = document.createElement("aside");
    aside.id = "pwaBanner";
    aside.className = "pwa-banner";
    aside.innerHTML = bannerHtml();
    var app = document.querySelector(".app");
    if (app && app.firstChild) app.insertBefore(aside, app.firstChild);
    else document.body.insertBefore(aside, document.body.firstChild);

    var dismiss = document.getElementById("pwaDismiss");
    if (dismiss) dismiss.addEventListener("click", hideBanner);
    var btn = document.getElementById("pwaInstallBtn");
    if (btn) {
      btn.hidden = !deferredPrompt;
      btn.addEventListener("click", function () {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
          deferredPrompt = null;
          hideBanner();
        });
      });
    }
  }

  function hideCaiDatNav() {
    if (!isNativeApp()) return;
    var links = document.querySelectorAll('.suite-nav a[href="cai-dat.html"]');
    for (var i = 0; i < links.length; i++) {
      links[i].hidden = true;
    }
  }

  function registerSw() {
    if (isNativeApp()) return;
    if (!("serviceWorker" in navigator)) return;
    if (location.protocol === "file:") return;
    navigator.serviceWorker
      .register("sw.js", { scope: "./" })
      .then(function () {
        return navigator.serviceWorker.ready;
      })
      .then(function () {
        setOfflineBadge();
      })
      .catch(function () {});
  }

  window.addEventListener("beforeinstallprompt", function (ev) {
    ev.preventDefault();
    deferredPrompt = ev;
    var btn = document.getElementById("pwaInstallBtn");
    if (btn) btn.hidden = false;
  });

  window.addEventListener("appinstalled", hideBanner);
  window.addEventListener("online", setOfflineBadge);
  window.addEventListener("offline", setOfflineBadge);

  document.addEventListener("DOMContentLoaded", function () {
    hideCaiDatNav();
    registerSw();
    setOfflineBadge();
    if (!isNativeApp()) mountBanner();
  });
})();
