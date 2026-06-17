// Dev launcher for the Electron app.
//
// Replaces the old `concurrently "vite" "wait-on tcp:5173 && electron ."`
// chain, which hardcoded port 5173 three times and died if that port was busy.
//
// Instead we start Vite (in-process, via its JS API) on the first FREE port
// from a candidate list, then launch Electron pointed at whatever port Vite
// actually bound. No race with wait-on, single source of truth for the port.

import { spawn } from "node:child_process";
import electronPath from "electron";
import { createServer } from "vite";

// Try these in order; the first free one wins. Falls back to an OS-assigned
// ephemeral port if every candidate is taken.
const CANDIDATE_PORTS = [5173, 5174, 5175, 5176, 5177, 5180, 5190, 5200];

async function startViteOnFreePort() {
  for (const port of CANDIDATE_PORTS) {
    try {
      const server = await createServer({ server: { port, strictPort: true } });
      await server.listen();
      return server;
    } catch (err) {
      const busy =
        err?.code === "EADDRINUSE" || /address already in use|is already in use/i.test(String(err?.message));
      if (busy) {
        console.log(`[dev] port ${port} is busy, trying the next one…`);
        continue;
      }
      throw err;
    }
  }
  // Last resort: let the OS pick any open port.
  console.log("[dev] all candidate ports busy — using an OS-assigned port…");
  const server = await createServer({ server: { port: 0, strictPort: false } });
  await server.listen();
  return server;
}

const server = await startViteOnFreePort();
const url = (server.resolvedUrls?.local?.[0] || `http://localhost:${server.config.server.port}/`).replace(/\/$/, "");
server.printUrls();
console.log(`[dev] launching Electron against ${url}`);

const electron = spawn(electronPath, ["."], {
  stdio: "inherit",
  env: { ...process.env, SUBLY_DEV_URL: url },
});

let shuttingDown = false;
async function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  try {
    await server.close();
  } catch {}
  process.exit(code ?? 0);
}

// When the app window is closed, tear down Vite too.
electron.on("exit", (code) => shutdown(code ?? 0));
// Ctrl+C / kill: stop Electron, then Vite.
for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => {
    if (!electron.killed) electron.kill();
    shutdown(0);
  });
}
