# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""앱 버전. 앱(main.py), 설치 프로그램(installer/installer.py), MCP 클라이언트가 모두 이 값을 쓴다."""
APP_VERSION = "1.19.1"

# 배포 경로(1.18): Microsoft Store 제출용 설치 파일(POSCHAT-Store-Setup.exe)은 앱 폴더(_internal)에 distribution.txt("store")를
# 넣는다. Store판은 앱이 스스로 업데이트 파일을 받지 않고 Store에서 업데이트하게 한다(Store가 심사한 파일만 설치되도록).
DISTRIBUTION_FILE = "distribution.txt"


def distribution():
    """"store" 또는 "github"(GitHub Releases 설치 파일·소스 실행·macOS·안드로이드)."""
    import sys
    from pathlib import Path

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    try:
        return "store" if (base / DISTRIBUTION_FILE).read_text(encoding="utf-8").strip() == "store" else "github"
    except OSError:
        return "github"
