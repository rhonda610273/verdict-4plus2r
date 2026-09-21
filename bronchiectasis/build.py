#!/usr/bin/env python3
"""
把 src/app.html + vendor/ 組成單一、零外連的 HTML 檔。

產出：../bronchiectasis-dashboard.html

做的事：
  1. 把 pdf.js 與其 worker 內嵌為 inline <script>（worker 在主執行緒跑 fake-worker
     模式，因此不需要 blob: worker，CSP 可以維持 worker-src 'none'）
  2. 把中日韓 .bcmap 字元對應表以 base64 內嵌，PDF 解析全程不發任何請求
  3. 對所有 inline <script> / <style> 計算 SHA-256，寫進 CSP，
     因此不需要 'unsafe-inline'，也不需要 'unsafe-eval'
"""

import base64
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src" / "app.html"
VENDOR = ROOT / "vendor"
OUT = ROOT.parent / "bronchiectasis-dashboard.html"


def inline_safe(js: str) -> str:
    """避免內容提早結束 <script> 區塊。"""
    return js.replace("</script", "<\\/script").replace("<!--", "<\\!--")


def build() -> int:
    html = SRC.read_text(encoding="utf-8")

    # ── 1. 內嵌 cmaps ──────────────────────────────────────────────
    cmaps = {}
    for p in sorted((VENDOR / "cmaps").glob("*.bcmap")):
        cmaps[p.stem] = base64.b64encode(p.read_bytes()).decode("ascii")
    cmap_js = "window.__CMAPS__={" + ",".join(
        '"%s":"%s"' % (k, v) for k, v in cmaps.items()
    ) + "};"
    html = html.replace("/*__CMAPS__*/", cmap_js, 1)

    # ── 2. 內嵌 pdf.js ─────────────────────────────────────────────
    for token, fname in (
        ("/*__PDFJS_WORKER__*/", "pdf.worker.min.js"),
        ("/*__PDFJS_LIB__*/", "pdf.min.js"),
    ):
        src = (VENDOR / fname).read_text(encoding="utf-8")
        if token not in html:
            print("build: 找不到佔位符 %s" % token, file=sys.stderr)
            return 1
        html = html.replace(token, inline_safe(src), 1)

    # ── 3. 依實際內容計算 CSP hash ─────────────────────────────────
    def hashes(tag: str) -> list:
        out = []
        for m in re.finditer(
            r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), html, re.DOTALL | re.IGNORECASE
        ):
            body = m.group(1)
            digest = hashlib.sha256(body.encode("utf-8")).digest()
            out.append("'sha256-%s'" % base64.b64encode(digest).decode("ascii"))
        return out

    script_hashes = hashes("script")
    style_hashes = hashes("style")
    if not script_hashes or not style_hashes:
        print("build: 找不到 inline script/style", file=sys.stderr)
        return 1

    csp = "; ".join(
        [
            "default-src 'none'",
            "script-src " + " ".join(script_hashes),
            "style-src " + " ".join(style_hashes),
            "img-src 'self' data:",
            "font-src 'none'",
            "connect-src 'none'",
            "worker-src 'none'",
            "child-src 'none'",
            "frame-src 'none'",
            "object-src 'none'",
            "media-src 'none'",
            "manifest-src 'none'",
            "form-action 'none'",
            "base-uri 'none'",
        ]
    )
    meta = '<meta http-equiv="Content-Security-Policy" content="%s">' % csp
    html = html.replace("<!--__CSP__-->", meta, 1)

    OUT.write_text(html, encoding="utf-8")

    size_mb = OUT.stat().st_size / 1024 / 1024
    print("build: %s" % OUT)
    print("  大小        : %.2f MB" % size_mb)
    print("  cmaps       : %d 個" % len(cmaps))
    print("  script hash : %d 個" % len(script_hashes))
    print("  style hash  : %d 個" % len(style_hashes))

    # ── 4. 零外連自我檢查 ──────────────────────────────────────────
    leaks = []
    for m in re.finditer(r"""(?:src|href|action)\s*=\s*["']([^"']+)["']""", html, re.I):
        url = m.group(1)
        if re.match(r"^(?:https?:)?//|^(?:ftp|ws|wss)://", url, re.I):
            leaks.append(url)
    if leaks:
        print("  ⚠ 發現外部資源參照：%s" % ", ".join(sorted(set(leaks))[:5]), file=sys.stderr)
        return 1
    print("  外部資源    : 0 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(build())
