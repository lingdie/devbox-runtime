const http = require("node:http");
const { execSync } = require("node:child_process");

const PORT = process.env.PORT || 8080;

const run = (command) => {
  try {
    return execSync(command, { encoding: "utf8" }).trim();
  } catch (error) {
    return `unavailable (${error.message.split("\n")[0]})`;
  }
};

const getVersions = () => ({
  node: process.version,
  bun: run("bun --version"),
  python: run("python3.14 --version").replace(/^Python\s+/, ""),
});

const server = http.createServer((req, res) => {
  const body = JSON.stringify(
    {
      framework: "sandbox",
      runtime: getVersions(),
      method: req.method,
      path: req.url,
    },
    null,
    2
  );

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(body);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Sandbox server running on http://0.0.0.0:${PORT}`);
  console.log("Runtime versions:", getVersions());
});
