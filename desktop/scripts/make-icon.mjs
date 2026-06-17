// Generates build/icon.icns from a rendered 字 logo (matches the web favicon).
// Uses Playwright (already a dev dep) to rasterize, then macOS sips + iconutil
// to assemble the .icns. Run: node scripts/make-icon.mjs
import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";

const OUT_DIR = "build";
const ICONSET = `${OUT_DIR}/icon.iconset`;
fs.mkdirSync(ICONSET, { recursive: true });

// A coral squircle with a white 字, padded like a native macOS icon.
const html = `<!doctype html><html><body style="margin:0">
  <div style="width:1024px;height:1024px;display:flex;align-items:center;justify-content:center">
    <div style="width:824px;height:824px;background:#ff5a45;border-radius:185px;
                display:flex;align-items:center;justify-content:center;
                box-shadow:0 24px 60px rgba(0,0,0,.25)">
      <span style="font-size:520px;color:#fff;font-weight:700;
                   font-family:'Hiragino Sans','Apple SD Gothic Neo',sans-serif">字</span>
    </div>
  </div>
</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
await page.setContent(html);
await page.screenshot({ path: `${OUT_DIR}/icon-master.png`, omitBackground: true, clip: { x: 0, y: 0, width: 1024, height: 1024 } });
await browser.close();

// Standard macOS iconset sizes (base + @2x).
const sizes = [16, 32, 128, 256, 512];
for (const s of sizes) {
  execFileSync("sips", ["-z", String(s), String(s), `${OUT_DIR}/icon-master.png`, "--out", `${ICONSET}/icon_${s}x${s}.png`]);
  execFileSync("sips", ["-z", String(s * 2), String(s * 2), `${OUT_DIR}/icon-master.png`, "--out", `${ICONSET}/icon_${s}x${s}@2x.png`]);
}
execFileSync("iconutil", ["-c", "icns", ICONSET, "-o", `${OUT_DIR}/icon.icns`]);
fs.rmSync(ICONSET, { recursive: true, force: true });
console.log("wrote build/icon.icns");
