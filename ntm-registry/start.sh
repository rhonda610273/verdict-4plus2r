#!/bin/sh
# macOS / Linux 啟動腳本
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    exec python3 server.py "$@"
fi

echo "============================================================"
echo " 這台電腦找不到 python3，系統無法啟動。"
echo "============================================================"
echo
echo "  macOS：內建通常已有 python3。若沒有，安裝 Xcode 命令列工具："
echo "      xcode-select --install"
echo "  或用 Homebrew：brew install python"
echo
echo "  Linux：sudo apt install python3   （Debian/Ubuntu）"
echo
exit 1
