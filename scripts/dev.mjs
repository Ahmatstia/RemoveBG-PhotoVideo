import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const python = resolve(root, ".venv", "Scripts", "python.exe");
const next = resolve(root, "web", "node_modules", "next", "dist", "bin", "next");

if (!existsSync(python)) throw new Error("Jalankan setup.ps1 terlebih dahulu untuk memasang backend Python.");
if (!existsSync(next)) throw new Error("Frontend belum dipasang. Jalankan npm ci --prefix web terlebih dahulu.");

let backend;
let frontend;
let stopping = false;

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  frontend?.kill();
  backend?.kill();
  setTimeout(() => process.exit(code), 500).unref();
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
async function waitForApi() {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (stopping || (backend && backend.exitCode !== null)) return false;
    try {
      const response = await fetch("http://127.0.0.1:7860/api/health", { signal: AbortSignal.timeout(1000) });
      if (response.ok) return true;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

try {
  const existing = await fetch("http://127.0.0.1:7860/api/health", { signal: AbortSignal.timeout(800) });
  if (existing.ok) console.log("Menggunakan API Python yang sudah berjalan.");
  else throw new Error("API belum aktif.");
} catch {
  backend = spawn(python, ["-m", "removebg.api"], {
    cwd: root,
    env: { ...process.env, MYTOOLS_OPEN_BROWSER: "0" },
    stdio: "inherit",
    windowsHide: true,
  });
  backend.on("error", (error) => {
    console.error("Backend Python gagal dijalankan:", error.message);
    stop(1);
  });
  backend.on("exit", (code) => {
    if (!stopping) {
      console.error("Backend Python berhenti.");
      stop(code || 1);
    }
  });
}

if (!(await waitForApi())) {
  console.error("API Python tidak siap. Periksa konfigurasi atau log aplikasi.");
  stop(1);
} else {
  frontend = spawn(process.execPath, [next, "dev", "--hostname", "127.0.0.1"], {
    cwd: resolve(root, "web"),
    stdio: "inherit",
    windowsHide: true,
  });
  frontend.on("error", (error) => {
    console.error("Next.js gagal dijalankan:", error.message);
    stop(1);
  });
  frontend.on("exit", (code) => {
    if (!stopping) stop(code || 0);
  });
}
