var fs = require("fs");
var path = require("path");

var roots = [
  path.join("android", "app", "src", "main", "assets", "public", "certs"),
  path.join("ios", "App", "App", "public", "certs")
];

function rm(dir) {
  if (!fs.existsSync(dir)) return;
  fs.rmSync(dir, { recursive: true, force: true });
  process.stdout.write("stripped " + dir + "\n");
}

roots.forEach(rm);
