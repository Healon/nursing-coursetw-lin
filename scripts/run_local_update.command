#!/bin/zsh
set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/nursing-course-update.log"

mkdir -p "$LOG_DIR"
if [[ ! -x "$PYTHON" ]]; then
  osascript -e 'display notification "找不到專案 Python；請確認外接 SSD 已連接" with title "護理教育訓練網站"'
  exit 1
fi

"$PYTHON" "$ROOT/scripts/local_update.py" 2>&1 | tee -a "$LOG_FILE"
exit ${pipestatus[1]}
