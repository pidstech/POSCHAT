# POSCHAT 로드맵과 다음 작업 (v1.16부터)

마지막 갱신: 2026-10-31, v1.19.1 개발 시점.

**플랫폼 정책(2026-10-26, 사용자 결정)**: 앞으로 데스크톱(Windows·macOS)만 개발·빌드한다. Android APK 빌드·에뮬레이터 CI·업로드·릴리스는 중단한다. 기존 Android 소스는 보관하지만 새 기능을 맞추거나 공유 모듈 목록을 동기화하지 않는다. 사용자가 다시 요청하기 전에는 Android 빌드를 재개하지 않는다.

## 지금까지
| 버전 | 내용 | 상태 |
|---|---|---|
| 1.12 | 설치 프로그램 안정화, Knowledge Work Plugins, 접근성 | 릴리스 |
| 1.13 | 브라우저: 채팅 옆 네이티브 웹 뷰, 격리, 페이지 읽기·첨부, 에이전트 browser_read/open | 릴리스(B1은 1.15에서 수정) |
| 1.14 | 논문 읽기(POSCHAT Paper) | 릴리스 |
| 1.15 | B1 수정(ui_events 큐) + POSCHAT Code(편집기·변경 검토·Git·실행) | 릴리스 |
| 1.16 | Code 에이전트(작업 탭), POSCHAT Lab, AI 브라우저 에이전트, 사이드바 정리, 보안 검토 반영(사이트 승인 kind `site`, `.git` 수정 금지) | 릴리스 |
| 1.17 | Adaptive Hybrid AI Engine: 로컬 AI(Ollama)·자동 모델 선택(4정책)·3단계(경량 Cloud·프런티어 상담)·품질 검증·승격·비용 통계·벤치마크 | 릴리스(3단계는 기본 꺼짐, 캐싱은 1.18.8부터 기본 켜짐, 실제 모델 측정은 남음) |
| 1.17.1 | Code 에이전트 2(Claude Code·Codex처럼): 권한 모드 4가지·다시 묻지 않기 규칙·작업 중 지시·슬래시 명령·지시별 되돌리기·AGENTS.md·격리 작업 공간(git worktree)·새 도구, 손익분기 실험 도구 | 릴리스 |
| 1.17.2 | Code 에이전트 3(터미널처럼, 사용자 요청 '완벽히 CLI처럼'): 작업 탭 전체를 Claude Code 같은 터미널로 — `● Read(…) ⎿` 기록·줄 번호 diff·접힌 출력(Ctrl+O), 기록 안의 승인 선택지(1·2·3·Esc, 거부하며 다르게 하라고 알리기), Shift+Tab 모드(작업 중에도), Esc 멈춤·Esc 두 번 되돌리기, ↑↓ 지난 입력, `/`·`@` 자동 완성, `!명령`·`#메모`·`@파일`, 프로젝트 명령(.poschat/.claude commands), /clear /resume /status /diff /revert /todos /permissions /memory /worktree /apply /keep /discard /delete. 코드는 채팅과 나누지 않는 하나의 전체 화면 | 릴리스 |
| 1.18.1 | 에이전트 인터넷 도구(web_search·web_fetch·paper_search 저자별·web_download, `web_research.py`, 에이전트가 만든 주소는 승인·내부망 차단), `/usage`(채팅·작업 탭), 작업 탭 아래 회색 띠 없앰 | 릴리스 |
| 1.19.1 | 1.19 피드백 후속 6가지: 플러그인 스킬 설명 한국어(스킬 목록·/ 메뉴), 기본 전체 화면, 주소 칸·뒤로·앞으로·새로 고침을 웹페이지 위 네이티브 막대로(채팅 위 주소 줄 제거), 막대 윗부분 잘림 수정, 크레딧 사용량 막대, 링크 색 밝게·버튼 모양 링크(플러그인 '홈페이지') 색 | 릴리스(네이티브 막대는 Windows·macOS 실기기 손 확인 남음) |
| 1.19.0 | 공개 전 사용자 피드백 9가지: 시작 창 크기 설정·F11, 브라우저 '기본 브라우저로 열기'·닫기를 웹페이지 위 네이티브 막대로, Lab·라이브러리·자동화·플러그인에서 사이드바 유지, PLMS 창에서 계정 저장, 플러그인·스킬 설명 한국어(341개), 테마 맞춤 링크 색·다녀온 링크, 30일 토큰 그래프, 사용법 가이드 카드·목차, 설치 파일 줄이기(AVIF·setuptools 제외, 설치 중 이중 CRC 확인 제거) | 릴리스(네이티브 막대는 Windows·macOS 실기기 손 확인 남음) |
| 1.18.9 | 공개 배포 전 보안 보강: 명령 승인 우회(`&`) 차단, 채팅 답변의 외부 이미지·위험 링크 차단, 텍스트 첨부 앱 안에서 보기, 채팅 명령 비밀 환경 변수 제거·위험 명령 매번 확인, API 키 OS 보안 저장소, 업데이트 내려받기 대체 경로, 릴리스 태그 점검 | 릴리스 |
| 1.18.8 | PLMS를 베타로 표시(사이드바 맨 아래·베타 배지), 토큰 효율(프롬프트 줄이기·프롬프트 캐싱 기본 켜짐), 대화 검색 색인(`thread_index.py`), 공용 `net.py` 분리 | 실제 앱에서 토큰 절감폭·PLMS 손 확인 남음 |
| 1.18.7 | PLMS 수업 중복 제거·PDF 미리보기·PowerPoint 열기·AI 확인 범위 표시, 작업 화면에서 사이드바 자동 접기, Context7·RTK·ECC 안내 | 실제 학교 계정·Windows·macOS 앱 손 확인 남음 |
| 1.18.6 | PLMS 백그라운드: 저장된 계정으로 숨은 웹 뷰에서 로그인·조회(브라우저 안 열림), 채팅 에이전트가 브라우저 없이 PLMS 조회, 실패 시 10분 재시도 차단 | 실제 학교 계정 SSO·StonePASS 손 확인 남음 |
| 1.18.5 | PLMS 개선: 이번 학기 수업 먼저·지난 학기 접기, 설정에 저장한 계정으로 로그인 창 자동 입력(StonePASS는 직접), 수업 화면(종류 칩·주차별) 재구성 | 실제 학교 계정 자동 입력·학기 구분 손 확인 남음 |
| 1.18.4 | PLMS 로그인·수강 목록·공지·자료 읽기·에이전트 도구, 여러 세션 동시 실행, ponytail, 데스크톱 전용 빌드 | 실제 학교 계정 인증·자료 조회 손 확인 남음 |
| 1.18.3 | 업데이트 서버를 HTTPS 도메인(`https://pidstech.com`)으로. 서버는 IP 피드(1.18.2 앱용)와 도메인 피드를 따로 만든다 | 릴리스 |
| 1.18.2 | 자체 업데이트 서버(저장소 비공개 전환 준비): 새 버전 확인·설치 파일 받기를 PIDS Tech. 서버로, 설치 파일 Ed25519 서명 확인, 서명 도구·서버 동기화([update-server.md](update-server.md)). 서버는 아직 http(IP) | 릴리스 |
| 1.18.0 | 일반 AI 모델(GPT, 본인 OpenAI API 키·Responses API), 코드 화면 아래 패널을 진짜 터미널로(ConPTY·pty, xterm.js, Git·변경 검토는 왼쪽 탭), SSH 원격 작업 폴더(paramiko + 원격 도우미, 파일·Git·터미널·에이전트가 서버에서), 부적절한 응답 신고, Store 제출 준비 | 릴리스 |

## 지금 할 일

### Future Work: 다운로드 경고(Chrome·Windows SmartScreen) 줄이기 — 2026-10-31 메모, 다음에 진행
공개 다운로드 때 Chrome·SmartScreen이 설치 파일에 경고를 띄우는 문제. 1.19.0에는 넣지 않았다(사용자 결정: 메모만 남기고 다음 날 진행).
- **코드 서명(가장 중요)**: 공인 CA 코드 서명 인증서로 설치 파일과 안의 exe·dll·pyd까지 서명. 일반(OV) 인증서는 다운로드 평판이 쌓일 때까지 경고가 남을 수 있고, EV는 처음부터 SmartScreen 평판을 받는다. 빌드 쪽은 이미 준비돼 있다: `build_installer.sign`·`sign_tree`가 `WINDOWS_SIGN_PFX`·`WINDOWS_SIGN_PASSWORD`가 있으면 모든 PE 파일에 서명한다(CI의 *Prepare code signing certificate* 단계). 인증서가 하드웨어 토큰·클라우드 HSM 방식이면(최근 CA 정책상 대부분) CI 서명 단계를 그 방식(예: Azure Trusted Signing·signtool + KSP)으로 바꾼다. macOS는 Apple Developer ID 서명·공증(notarization)이 따로 필요하다.
- **HTTPS·헤더 확인**: 다운로드 페이지(pidstech.com)와 실제 파일 주소(GitHub Releases·업데이트 서버)가 모두 https인지, 혼합 콘텐츠가 없는지, 응답이 `Content-Type: application/octet-stream`·`Content-Disposition: attachment`인지 확인.
- **오탐 신고**: Google Search Console에 도메인 등록 → 보안 문제 확인·검토 요청, Safe Browsing 오탐 신고(https://safebrowsing.google.com/safebrowsing/report_error/).
- **VirusTotal 사전 검사**: 새 빌드마다 올려 오탐 엔진(AhnLab·Avast·Defender 등)이 있으면 그 회사에 먼저 신고. PyInstaller 설치 파일은 오탐이 잦다.
- **배포 형식**: 지금처럼 단일 설치 파일(.exe·.dmg)로 배포하고 ZIP·이중 압축·스크립트 동봉은 하지 않는다.


### 0. Microsoft Store 제출 (EXE 방식, 개인 계정 — 사용자 결정 2026-10-25)
- 앱 쪽 준비는 했다(1.18.0에 들어감): Store 설치 파일 `POSCHAT-Store-Setup.exe`(Store판은 스스로 업데이트하지 않고 Store를 엶),
  모든 PE 파일 서명(`build_installer.sign_tree`), 부적절한 응답 신고(GitHub 이슈 `ai-report`), 개인정보 처리방침, 제출 안내 [microsoft-store.md](microsoft-store.md).
- 사용자가 할 일: 개발자 계정(개인)·이름 예약 → Store ID를 `updates.STORE_PRODUCT_ID`에, 코드 서명 인증서를 Secrets에,
  `ai-report` 라벨·Immutable releases → 서명된 릴리스 → 파트너 센터 제출. 인증서가 하드웨어 토큰·클라우드 HSM 방식이면 CI 서명 단계를 바꾼다.

### 1. 손익분기 실험으로 결정 함수 맞추기 (진행 중)
- 도구: `tools/breakeven_experiment.py`(방법은 [adaptive-ai-evaluation.md](adaptive-ai-evaluation.md#손익분기-실험-toolsbreakeven_experimentpy-117-뒤)).
- 사용자가 이 클라우드 환경에 API 키(`ANTHROPIC_API_KEY`, 선택 `POSTECH_GENAI_API_KEY`)를 넣으면 새 세션에서 1차(시범, 호출 약 900번)를 돌린다.
  모델 짝은 Claude Haiku 5.5 → Opus 5.5 먼저(캐싱까지 잼), 다음 Haiku → Sonnet, POSTECH GPT-5 mini → GPT-5.1.
- 분석 결과로 `adaptive_cost`의 기본 프로필·승격 확률·상담 비율(지금은 '언제나 상담'으로 봄)을 고치고, 표 정책이 이기면 엔진에 옮긴다.

### 2. v1.17 뒤: 실제 모델 측정
v1.17(Adaptive Hybrid AI Engine)은 릴리스했다(사용자 승인, 2026-10-24). 3단계는 기본 꺼짐, 프롬프트 캐싱은 1.18.8부터 기본 켜짐(다단계 작업·상담에서만), 단가를 넣으면 손익분기(`adaptive_cost`)로 경로를 고른다. 구조 [architecture/adaptive-ai.md](architecture/adaptive-ai.md), 결과 [adaptive-ai-benchmark-results.md](adaptive-ai-benchmark-results.md).
- 사용자 PC에서 `tools/local_ai_check.py`와 `tools/adaptive_benchmark.py --run`(A·B·E·F·G, Cloud 호출 상한)으로 실제 품질·비용을 재고 결과 문서에 적는다.
  성공률 하락이 2%p를 넘는 작업 유형은 `LOCAL_ELIGIBLE`·`LIGHT_DIRECT`에서 뺀다.
- 실제 Windows·macOS 앱에서 Ollama 연결·모델 받기·정책 창·라우팅 표시·상담을 손으로 확인한다.
- 개발자 모드(설정)의 실측 토큰·캐시 적중률로 상담·캐싱의 실제 이득을 확인하고, 손익분기 프로필의 기본값(O·C·A·승격 확률)을 실측으로 고친다.
- 1.16 실제 앱 손 확인(아래 '알려진 한계')은 계속 남아 있다.

### 3. 다음 후보(v1.18 이후)
- PLMS 과제 제출(승인 창 필수: 과목·과제·파일·마감 표시, 임시저장 후 최종 제출은 한 번 더 확인). 실제 계정으로 시험할 수 있을 때 한다.
- Code 에이전트: 하위 작업(서브에이전트), 긴 출력 요약, 이미지(스크린숏) 입력, MCP 도구, 훅(편집 뒤 포맷·린트 자동 실행), 실제 앱에서 worktree·백그라운드 명령 손 확인.
  (1.17.1에서 worktree 격리·테스트 명령 찾기·권한 모드·슬래시 명령은 했다)
- SystemVerilog 문법 트리, 원격(SSH) 작업 폴더에서 격리 작업(git worktree). (대화형 터미널과 SSH 원격 작업 폴더는 1.18.0에 들어갔다)
- Lab: papermill식 노트북 파라미터, 원격(SSH) 실행 기록, 실험 보고서 내보내기(Markdown·PDF), 지표 단위 변환 규칙.
- 브라우저 에이전트: iframe·shadow DOM 요소, 드래그·호버, 탭 여러 개, 사이트별 허용 목록 설정.

### 구현 기록
- 1.16 구조: [architecture/poschat-lab.md](architecture/poschat-lab.md), [architecture/browser-agent.md](architecture/browser-agent.md), [architecture/poschat-code.md](architecture/poschat-code.md)(Code 에이전트 절).
- 1.15 B1: 네이티브 이벤트 처리기(UI 스레드) → `Bridge._push()` → `evaluate_js()` 교착 → `ui_events.EventPump`로 해결. 시험 `tests/test_ui_events.py`, `tests/browser_spike.py`(`--legacy-push`로 재현).

## 알려진 한계·확인할 것
- 1.14 논문 화면은 Chromium 화면 시험과 CI 빌드만 통과했다. 실제 Windows(WebView2)·macOS(WKWebView)·안드로이드 앱에서 PDF 열기·드래그 선택·영역 자르기·파일 고르기를 손으로 확인하지 않았다.
  특히 macOS WKWebView의 ES 모듈 워커(`pdf.worker.min.js`)와 안드로이드 `appassets` 주소에서의 모듈 불러오기.
- 1.13 브라우저의 네이티브 붙이기는 CI 창에서 확인했다. B1은 1.15에서 고쳤고 CI 창 시험(열기·이동·이벤트 폭주·닫기 중 앱 응답)은 통과했지만, 실제 앱에서 손으로 확인하는 일은 남았다.
- 1.15 Code 화면은 Chromium 화면 시험과 CI 빌드만 통과했다. WebView2·WKWebView·안드로이드 WebView에서의 편집기 입력·IME·키보드는 손으로 확인해야 한다.
- macOS WKWebView 백엔드는 제목·주소가 바뀌어도(SPA의 pushState 등) 페이지가 다 열릴 때만 알린다(KVO 없음).
- 1.16 브라우저 에이전트·Lab·Code 에이전트 화면은 Chromium 화면 시험과 CI로 확인했다. 실제 앱에서 손으로 확인하는 일이 남았다.
- 1.17.2 터미널 작업 탭은 Chromium 화면 시험으로만 확인했다. 실제 WebView2·WKWebView에서 Shift+Tab·Esc·Ctrl+O·Ctrl+L이 앱(창) 단축키와 겹치지 않는지, 한글 IME 조합 중 Enter·↑↓, macOS의 Ctrl/Cmd 차이를 손으로 확인해야 한다.
- 1.18.1 인터넷 도구는 가짜 응답 시험만 했다(개발 환경에서 DuckDuckGo·OpenAlex·Semantic Scholar가 요청 한도로 거절). 실제 앱에서 조사 작업(예: 회사 창업자 논문 전수조사)을 손으로 돌려 검색 품질·한도를 확인할 것.
  키 없는 검색이 자주 막히면 검색 API 키(예: Brave Search) 설정을 더하는 것을 검토한다.
- 1.17 로컬 AI는 가짜 Ollama(시험)로만 확인했다. 개발 환경에서 실제 Ollama 실행 파일을 돌릴 수 없었고 Cloud 키도 없었다. 라우터의 test 세트 오류(paper-15 등)는 일부러 고치지 않았다.
