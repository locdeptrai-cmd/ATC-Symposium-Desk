(function () {
  var expected = "created by Lộc đẹp trai";
  function lock() {
    document.open();
    document.write(
      "<!doctype html><html lang='vi'><meta charset='utf-8'>" +
        "<meta name='viewport' content='width=device-width, initial-scale=1'>" +
        "<title>Ứng dụng đã khóa</title><body style='margin:0;min-height:100vh;" +
        "display:grid;place-items:center;background:#061018;color:#e7eef6;" +
        "font-family:Segoe UI,sans-serif'><main style='text-align:center;max-width:28rem;padding:24px'>" +
        "<p style='letter-spacing:.2em;color:#e2b15a;text-transform:uppercase;font-size:12px'>Locked</p>" +
        "<h1 style='font-size:1.4rem'>Ứng dụng đã bị khóa</h1>" +
        "<p style='color:#8aa0b5'>Chữ ký số bị thay đổi hoặc thiếu file SIGNATURE.txt.</p>" +
        "</main></body></html>"
    );
    document.close();
  }
  fetch("./SIGNATURE.txt", { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("missing");
      return res.text();
    })
    .then(function (text) {
      if (String(text || "").trim() !== expected) lock();
    })
    .catch(lock);
})();
