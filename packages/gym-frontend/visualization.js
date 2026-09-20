// Only this trusted wrapper is placed in the outer frame. The inner frame owns
// all authored code. Its parent's frame-src policy also restricts self-navigation.
export const visualizationPolicy =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; worker-src 'none'; frame-src about:";
const attr = (text) =>
  String(text)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
const jsonScript = (value) =>
  JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029");

export function visualizationDocument(block, parameters) {
  // JSON is escaped before reaching an HTML parser, including author datasets
  // containing </script>. No token, visit, learner response or API bridge enters.
  const payload = jsonScript(
    JSON.stringify({ parameters, data: block.data || {} }),
  );
  const code = String(block.javascript || "").replace(
    /<\/script/gi,
    "<\\/script",
  );
  const css = String(block.css || "").replace(/<\/style/gi, "<\\/style");
  const child = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${visualizationPolicy.replace("frame-src about:", "frame-src 'none'")}"><meta name="referrer" content="no-referrer"><style>body{font:15px system-ui;margin:16px;color:#203958}canvas,svg{max-width:100%;height:auto}${css}</style><script>window.gym = JSON.parse(${payload});</script></head><body>${block.html}<script>${code}</script></body></html>`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${visualizationPolicy}"><meta name="referrer" content="no-referrer"><style>html,body,iframe{margin:0;border:0;width:100%;height:100%;display:block}</style></head><body><iframe title="Visualization content" sandbox="allow-scripts" referrerpolicy="no-referrer" allow="camera 'none'; microphone 'none'; geolocation 'none'; clipboard-read 'none'; clipboard-write 'none'" srcdoc="${attr(child)}"></iframe></body></html>`;
}
