import { useRef, useState } from "react";
import { Download, FileText, Loader2 } from "lucide-react";

/**
 * Creative e-certificate drawn as a single SVG (so it stays sharp at any size), plus
 * "Download PNG" and "Download PDF" buttons. No extra libraries: the SVG is rasterised on a
 * <canvas>, and the PDF is a tiny hand-built single-page file wrapping that image.
 *
 * Props: certificate = { student_name, course_title, skill_tag, level, score_percent, issued_at, cert_code }
 */
const W = 1600;
const H = 1130;

function formatDate(value) {
  if (!value) return "";
  // SQLite stores "YYYY-MM-DD HH:MM:SS" (UTC). Make it parseable everywhere.
  const d = new Date(String(value).includes("T") ? value : String(value).replace(" ", "T") + "Z");
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

// Shrink long names / titles so they always fit the certificate.
function fit(text, maxChars, base, min) {
  const n = (text || "").length;
  if (n <= maxChars) return base;
  return Math.max(min, Math.round(base * (maxChars / n)));
}

function wrapTitle(title, maxChars = 46) {
  const words = (title || "").split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars && cur) { lines.push(cur); cur = w; }
    else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 2);
}

function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** The certificate artwork as a standalone SVG string. */
export function buildCertificateSvg(cert) {
  const name = esc(cert.student_name || "Student");
  const date = esc(formatDate(cert.issued_at));
  const code = esc(cert.cert_code);
  const skill = esc(cert.skill_tag || "");
  const level = esc(cert.level || "");
  const score = cert.score_percent != null ? `${cert.score_percent}%` : null;
  const titleLines = wrapTitle(cert.course_title).map(esc);
  const nameSize = fit(cert.student_name, 22, 104, 54);
  const titleSize = titleLines.length > 1 ? 42 : 54;
  const titleY = titleLines.length > 1 ? 696 : 712;                                   // baseline of the first course-title line
  const chipsY = titleY + (titleLines.length - 1) * 50 + 56;

  // little confetti / sparkle dots around the edges for a celebratory feel
  const dots = [
    [120, 170, 7, "#f59e0b"], [210, 118, 5, "#2e5bdf"], [1480, 170, 7, "#2e5bdf"], [1390, 118, 5, "#f59e0b"],
    [110, 960, 6, "#0d9488"], [190, 1010, 4, "#f59e0b"], [1490, 960, 6, "#f59e0b"], [1410, 1010, 4, "#0d9488"],
    [300, 90, 4, "#0d9488"], [1300, 90, 4, "#0d9488"], [70, 560, 5, "#2e5bdf"], [1530, 560, 5, "#f59e0b"],
  ].map(([x, y, r, c]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}" opacity="0.85"/>`).join("");

  // star-burst seal: 24-point rosette
  const rosette = Array.from({ length: 24 }, (_, i) => {
    const a = (i / 24) * Math.PI * 2;
    const r = i % 2 === 0 ? 112 : 96;
    return `${(Math.cos(a) * r).toFixed(1)},${(Math.sin(a) * r).toFixed(1)}`;
  }).join(" ");

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" font-family="Georgia, 'Times New Roman', serif">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="0.55" stop-color="#f7f9ff"/><stop offset="1" stop-color="#fff9ec"/></linearGradient>
  <linearGradient id="brand" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#14203e"/><stop offset="0.5" stop-color="#2e5bdf"/><stop offset="1" stop-color="#6366f1"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7d774"/><stop offset="0.5" stop-color="#d99a1f"/><stop offset="1" stop-color="#f3c850"/></linearGradient>
  <linearGradient id="ribbon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2e5bdf"/><stop offset="1" stop-color="#14203e"/></linearGradient>
  <radialGradient id="seal" cx="0.35" cy="0.3" r="0.9"><stop offset="0" stop-color="#fde9a3"/><stop offset="0.6" stop-color="#e0a21f"/><stop offset="1" stop-color="#b9770e"/></radialGradient>
  <pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" fill="#2e5bdf" opacity="0.07"/></pattern>
  <clipPath id="inner"><rect x="70" y="70" width="${W - 140}" height="${H - 140}" rx="18"/></clipPath>
</defs>

<rect width="${W}" height="${H}" fill="#14203e"/>
<rect x="24" y="24" width="${W - 48}" height="${H - 48}" rx="30" fill="url(#gold)"/>
<rect x="40" y="40" width="${W - 80}" height="${H - 80}" rx="22" fill="#14203e"/>
<rect x="56" y="56" width="${W - 112}" height="${H - 112}" rx="16" fill="none" stroke="url(#gold)" stroke-width="2.5"/>
<rect x="70" y="70" width="${W - 140}" height="${H - 140}" rx="18" fill="url(#bg)"/>
<rect x="70" y="70" width="${W - 140}" height="${H - 140}" rx="18" fill="url(#dots)"/>

<!-- corner flourishes -->
<g clip-path="url(#inner)">
  <path d="M70 70 H330 Q250 120 200 200 Q150 280 70 330 Z" fill="url(#brand)"/>
  <path d="M70 70 H250 Q190 110 150 170 Q110 230 70 250 Z" fill="url(#gold)" opacity="0.9"/>
  <path d="M${W - 70} ${H - 70} H${W - 330} Q${W - 250} ${H - 120} ${W - 200} ${H - 200} Q${W - 150} ${H - 280} ${W - 70} ${H - 330} Z" fill="url(#brand)"/>
  <path d="M${W - 70} ${H - 70} H${W - 250} Q${W - 190} ${H - 110} ${W - 150} ${H - 170} Q${W - 110} ${H - 230} ${W - 70} ${H - 250} Z" fill="url(#gold)" opacity="0.9"/>
  <path d="M${W - 70} 70 H${W - 270} Q${W - 210} 105 ${W - 170} 160 Q${W - 130} 215 ${W - 70} 235 Z" fill="#2e5bdf" opacity="0.10"/>
  <path d="M70 ${H - 70} H270 Q210 ${H - 105} 170 ${H - 160} Q130 ${H - 215} 70 ${H - 235} Z" fill="#2e5bdf" opacity="0.10"/>
</g>
${dots}

<!-- brand header -->
<g transform="translate(${W / 2}, 150)">
  <circle r="34" fill="url(#brand)"/>
  <path d="M-14 6 L-4 -14 L4 0 L10 -8 L16 6 Z" fill="#fff" opacity="0.95"/>
  <circle cx="0" cy="-2" r="4" fill="#f7d774"/>
</g>
<text x="${W / 2}" y="222" text-anchor="middle" font-size="26" letter-spacing="9" fill="#2346cb" font-family="Arial, Helvetica, sans-serif" font-weight="700">CAREERAI</text>

<text x="${W / 2}" y="318" text-anchor="middle" font-size="86" font-weight="700" fill="url(#brand)" letter-spacing="6">CERTIFICATE</text>
<text x="${W / 2}" y="372" text-anchor="middle" font-size="27" letter-spacing="12" fill="#b9770e" font-family="Arial, Helvetica, sans-serif" font-weight="700">OF ACHIEVEMENT</text>
<g transform="translate(${W / 2}, 402)"><path d="M-230 0 H-30" stroke="url(#gold)" stroke-width="3"/><path d="M30 0 H230" stroke="url(#gold)" stroke-width="3"/><path d="M0 -11 L11 0 L0 11 L-11 0 Z" fill="url(#gold)"/></g>

<text x="${W / 2}" y="462" text-anchor="middle" font-size="27" fill="#64748b" font-style="italic">This is proudly presented to</text>

<!-- recipient -->
<text x="${W / 2}" y="${nameSize > 90 ? 565 : 555}" text-anchor="middle" font-size="${nameSize}" fill="#14203e" font-style="italic" font-family="'Brush Script MT', 'Segoe Script', 'Snell Roundhand', 'Lucida Handwriting', cursive, Georgia, serif">${name}</text>
<path d="M${W / 2 - 420} 585 H${W / 2 + 420}" stroke="url(#gold)" stroke-width="2.5"/>

<text x="${W / 2}" y="${titleLines.length > 1 ? 640 : 650}" text-anchor="middle" font-size="25" fill="#64748b" font-style="italic">for successfully completing the course and passing the assessment in</text>
${titleLines.map((l, i) => `<text x="${W / 2}" y="${titleY + i * 50}" text-anchor="middle" font-size="${titleSize}" font-weight="700" fill="#2346cb">${l}</text>`).join("\n")}

<!-- skill / level chips -->
<g transform="translate(${W / 2}, ${chipsY})" font-family="Arial, Helvetica, sans-serif" font-size="21" font-weight="700" text-anchor="middle">
  ${(() => {
    const chips = [];
    if (skill) chips.push({ t: `SKILL: ${skill.toUpperCase()}`, c: "#0f766e", bg: "#ccfbf1" });
    if (level) chips.push({ t: level.toUpperCase(), c: "#2346cb", bg: "#dde7fc" });
    if (score) chips.push({ t: `SCORE: ${score}`, c: "#b45309", bg: "#fef3c7" });
    const widths = chips.map((c) => c.t.length * 15 + 46);
    const total = widths.reduce((a, b) => a + b, 0) + (chips.length - 1) * 18;
    let x = -total / 2;
    return chips.map((c, i) => {
      const w = widths[i];
      const out = `<rect x="${x.toFixed(0)}" y="-26" width="${w}" height="44" rx="22" fill="${c.bg}"/><text x="${(x + w / 2).toFixed(0)}" y="5" fill="${c.c}">${c.t}</text>`;
      x += w + 18;
      return out;
    }).join("");
  })()}
</g>

<!-- footer: date / seal / id -->
<g font-family="Arial, Helvetica, sans-serif">
  <text x="400" y="902" text-anchor="middle" font-size="30" fill="#14203e" font-weight="700">${date}</text>
  <path d="M250 918 H550" stroke="#94a3b8" stroke-width="2"/>
  <text x="400" y="950" text-anchor="middle" font-size="19" letter-spacing="4" fill="#64748b">DATE OF ISSUE</text>
  <text x="400" y="1000" text-anchor="middle" font-size="17" letter-spacing="2" fill="#94a3b8">ID: ${code}</text>

  <text x="${W - 400}" y="902" text-anchor="middle" font-size="40" fill="#14203e" font-style="italic" font-family="'Brush Script MT', 'Segoe Script', 'Snell Roundhand', cursive, Georgia, serif">CareerAI</text>
  <path d="M${W - 550} 918 H${W - 250}" stroke="#94a3b8" stroke-width="2"/>
  <text x="${W - 400}" y="950" text-anchor="middle" font-size="19" letter-spacing="4" fill="#64748b">ISSUED BY CAREERAI</text>
</g>

<!-- gold seal with ribbons -->
<g transform="translate(${W / 2}, 925) scale(0.72)">
  <path d="M-62 60 L-92 170 L-52 150 L-26 185 L-6 80 Z" fill="url(#ribbon)"/>
  <path d="M62 60 L92 170 L52 150 L26 185 L6 80 Z" fill="url(#ribbon)"/>
  <polygon points="${rosette}" fill="url(#seal)" stroke="#a8690a" stroke-width="2"/>
  <circle r="80" fill="none" stroke="#fff3c4" stroke-width="3" opacity="0.9"/>
  <circle r="68" fill="none" stroke="#a8690a" stroke-width="1.5" stroke-dasharray="3 5"/>
  <path d="M0 -38 L11 -12 L40 -9 L18 10 L25 38 L0 23 L-25 38 L-18 10 L-40 -9 L-11 -12 Z" fill="#fff8dc" stroke="#a8690a" stroke-width="2" stroke-linejoin="round"/>
  <text y="62" text-anchor="middle" font-size="14" letter-spacing="3" fill="#7a4a06" font-family="Arial, Helvetica, sans-serif" font-weight="700">VERIFIED</text>
</g>

</svg>`;
}

// ---------------------------------------------------------------- downloads ---

function svgToCanvas(svg, scale = 1) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = W * scale;
      canvas.height = H * scale;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas);
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not render the certificate")); };
    img.src = url;
  });
}

function download(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1500);
}

function safeName(cert) {
  return `CareerAI-Certificate-${(cert.skill_tag || cert.course_title || "course").replace(/[^a-z0-9]+/gi, "-")}-${cert.cert_code}`;
}

/** Minimal one-page A4-landscape PDF that holds the certificate as a full-bleed JPEG. */
function jpegToPdfBlob(jpegBytes, imgW, imgH) {
  const pageW = 841.89, pageH = 595.28;          // A4 landscape in points
  const enc = new TextEncoder();
  const chunks = [];
  const offsets = [];
  let length = 0;
  const push = (data) => {
    const bytes = typeof data === "string" ? enc.encode(data) : data;
    chunks.push(bytes);
    length += bytes.length;
  };
  const obj = (n, body) => { offsets[n] = length; push(`${n} 0 obj\n${body}\nendobj\n`); };

  push("%PDF-1.4\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
  obj(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageW} ${pageH}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);
  offsets[4] = length;
  push(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${imgW} /Height ${imgH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBytes.length} >>\nstream\n`);
  push(jpegBytes);
  push("\nendstream\nendobj\n");
  const content = `q ${pageW} 0 0 ${pageH} 0 0 cm /Im0 Do Q`;
  obj(5, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
  const xref = length;
  push(`xref\n0 6\n0000000000 65535 f \n${[1, 2, 3, 4, 5].map((n) => String(offsets[n]).padStart(10, "0") + " 00000 n \n").join("")}`);
  push(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`);
  return new Blob(chunks, { type: "application/pdf" });
}

export default function Certificate({ certificate, showActions = true }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const svg = useRef("");
  svg.current = buildCertificateSvg(certificate);
  const preview = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.current)}`;

  const savePng = async () => {
    setBusy("png"); setErr("");
    try {
      const canvas = await svgToCanvas(svg.current, 2);
      const blob = await new Promise((res) => canvas.toBlob(res, "image/png"));
      download(blob, `${safeName(certificate)}.png`);
    } catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  const savePdf = async () => {
    setBusy("pdf"); setErr("");
    try {
      const canvas = await svgToCanvas(svg.current, 1.5);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
      const bin = atob(dataUrl.split(",")[1]);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      download(jpegToPdfBlob(bytes, canvas.width, canvas.height), `${safeName(certificate)}.pdf`);
    } catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  return (
    <div>
      <div className="rounded-2xl overflow-hidden shadow-xl ring-1 ring-slate-200 bg-white">
        <img src={preview} alt={`Certificate for ${certificate.student_name} - ${certificate.course_title}`} className="w-full h-auto block" draggable={false} />
      </div>
      {showActions && (
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <button onClick={savePdf} disabled={!!busy}
            className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2.5 rounded-lg">
            {busy === "pdf" ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />} Download PDF
          </button>
          <button onClick={savePng} disabled={!!busy}
            className="flex items-center gap-2 bg-white border border-slate-200 hover:bg-slate-50 disabled:opacity-60 text-slate-700 text-sm font-semibold px-5 py-2.5 rounded-lg">
            {busy === "png" ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Download image (PNG)
          </button>
          {err && <span className="text-xs text-red-600">{err}</span>}
        </div>
      )}
    </div>
  );
}