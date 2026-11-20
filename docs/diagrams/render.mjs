// Renderiza docs/diagrams/data_model.elements.json (formato de elementos do Excalidraw) em PNG,
// usando a API oficial de exportação do @excalidraw/excalidraw num Chromium headless.
//
// Uso (na raiz do repositório; o node_modules criado fica fora do git):
//   npm install --prefix docs/diagrams --no-save playwright-core@1.49.1
//   node docs/diagrams/render.mjs docs/diagrams/data_model.elements.json docs/diagrams/data_model.png <caminho do chrome.exe>
// Qualquer Chromium serve (por exemplo, o instalado pelo Playwright em %LOCALAPPDATA%\ms-playwright).
import { chromium } from "playwright-core";
import fs from "node:fs";

const [, , inPath, outPath, chromePath] = process.argv;
const elements = JSON.parse(fs.readFileSync(inPath, "utf8")).filter(e => e.type !== "cameraUpdate");

const html = `<!doctype html><html><head><meta charset="utf-8"></head><body>
<script type="module">
  import { convertToExcalidrawElements, exportToBlob } from "https://esm.sh/@excalidraw/excalidraw@0.18.0?deps=react@18.3.1,react-dom@18.3.1";
  window.__render = async (skeleton) => {
    const els = convertToExcalidrawElements(skeleton, { regenerateIds: false });
    const blob = await exportToBlob({
      elements: els,
      appState: { exportBackground: true, viewBackgroundColor: "#ffffff", exportWithDarkMode: false },
      files: null,
      exportPadding: 40,
      getDimensions: (w, h) => ({ width: w * 2, height: h * 2, scale: 2 }),
    });
    const buf = await blob.arrayBuffer();
    let s = ""; const b = new Uint8Array(buf);
    for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s);
  };
  window.__ready = true;
</script></body></html>`;

const browser = await chromium.launch({ executablePath: chromePath });
const page = await browser.newPage();
page.on("console", m => console.log("[page]", m.text()));
page.on("pageerror", e => console.log("[pageerror]", e.message));
await page.setContent(html);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
const b64 = await page.evaluate(async (sk) => await window.__render(sk), elements);
fs.writeFileSync(outPath, Buffer.from(b64, "base64"));
console.log("wrote", outPath, fs.statSync(outPath).size, "bytes");
await browser.close();
