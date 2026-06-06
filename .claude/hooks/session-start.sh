#!/bin/bash
set -euo pipefail

# Claude Code on the web 환경에서만 실행
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

# Linux 환경에서 설치 가능한 패키지만 설치 (pywin32, PyQt5는 Windows 전용)
pip install \
  pandas==2.0.3 \
  numpy==1.24.3 \
  requests==2.31.0 \
  python-dotenv==1.0.0 \
  schedule==1.2.1 \
  SQLAlchemy==2.0.20 \
  flake8 \
  --quiet

# PYTHONPATH 설정
echo 'export PYTHONPATH="${CLAUDE_PROJECT_DIR:-$(pwd)}"' >> "$CLAUDE_ENV_FILE"
