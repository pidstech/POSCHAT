# Microsoft Store 제출 (MSIX 방식, 개인 계정)

POSCHAT Windows 앱을 Microsoft Store에 **MSIX 방식**으로 올리는 절차와 파트너 센터에 넣을 값입니다(2026-11 기준).

**왜 MSIX인가(2.0.1, 사용자 결정 2026-11-01)**: Chrome·SmartScreen은 서명 없는 낯선 exe를 받을 때 경고하거나 막습니다.
Store에서 설치하면 브라우저로 exe를 받지 않으므로 이 경고가 아예 없습니다. EXE 방식은 설치 파일을 **직접 산 코드 서명 인증서로**
서명해야 Store가 받지만, MSIX는 **Microsoft가 심사 뒤 자기 인증서로 다시 서명**하므로 인증서가 필요 없습니다.
([코드 서명 선택지](https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options))
아래 EXE 방식 표는 인증서를 구하면 쓸 수 있도록 남겨 둡니다.

## MSIX 패키지 (2.0.1)
| 항목 | POSCHAT |
|---|---|
| 파일 | CI의 Windows 작업 산출물 **`POSCHAT-msix`** 안의 `POSCHAT.msix` (서명하지 않은 파일 — 릴리스에는 올리지 않음) |
| 형식 | 전체 신뢰 데스크톱 앱(`runFullTrust`), x64, Windows 10 1809 이상, 마이크 권한(PO노트) |
| 버전 | `version.py`의 X.Y.Z → `X.Y.Z.0` (Store는 마지막 자리가 0이어야 함) |
| Store판 표시 | 패키지 안 `_internal/distribution.txt` = store → 앱이 스스로 업데이트하지 않음. **업데이트는 Store가 자동으로** 함 |
| CI 확인 | 사본에 시험용 인증서로 서명해 실제로 설치 → `poschat.exe --selftest`가 패키지 안에서 Store판으로 도는지 확인 → 제거 |
| 데이터 | MSIX 앱이 `%APPDATA%\PostechChat`에 새로 만드는 파일은 Windows가 패키지 전용 폴더로 돌립니다. 그래서 GitHub판과 대화·설정이 따로일 수 있고, Store판을 제거하면 그 데이터도 지워집니다 |

### 직접 할 일 (MSIX)
1. **개발자 계정(개인)** — https://storedeveloper.microsoft.com (등록비 없음). Microsoft 계정 로그인, 신분증·셀카로 본인 확인.
   개인 계정은 나중에 회사 계정으로 바꿀 수 없습니다.
2. **이름 예약** — 파트너 센터 → 앱 및 게임 → 새 제품 → **MSIX 또는 PWA 앱** → `POSCHAT` 예약.
3. **제품 ID 값 세 개를 저장소 변수로** — 파트너 센터 → POSCHAT → *제품 관리 → 제품 ID*에 나오는 값을
   GitHub 저장소 → Settings → Secrets and variables → Actions → **Variables**에 넣습니다(비밀 값이 아님).
   | 변수 | 파트너 센터 항목 | 예 |
   |---|---|---|
   | `MSIX_IDENTITY_NAME` | Package/Identity/Name | `12345PIDSTech.POSCHAT` |
   | `MSIX_PUBLISHER` | Package/Identity/Publisher | `CN=1A2B3C4D-...` |
   | `MSIX_PUBLISHER_DISPLAY_NAME` | Package/Properties/PublisherDisplayName | `PIDS Tech.` |
   같은 화면의 **Store ID(9N…)** 는 `updates.py`의 `STORE_PRODUCT_ID`에 넣습니다.
   변수가 없으면 빌드는 시험용 게시자(`CN=POSCHAT Test`)로 만들고, 그 파일은 Store가 받지 않습니다(빌드 로그에 "시험용 게시자"라고 나옴).
4. **빌드** — 변수를 넣은 뒤 Actions → *Build installer* → *Run workflow*(또는 다음 릴리스 태그). Windows 작업이 끝나면
   실행 화면 아래 Artifacts에서 `POSCHAT-msix`를 받아 압축을 풉니다.
5. **제출** — 파트너 센터 → 제출 → 패키지에 `POSCHAT.msix`를 올리고, 아래 *파트너 센터에 넣을 값*(속성·연령 등급·Store 목록·인증 참고 사항)을 채워
   **인증을 위해 제출**. `runFullTrust`는 제한된 기능이라 사유를 묻습니다: *"Desktop app (Python/WebView2) that runs local tools,
   a terminal and git for the user's own project folders."* 보통 1~3일.
6. **공개 링크 바꾸기** — 심사가 끝나면 Windows 다운로드 링크를 `https://apps.microsoft.com/detail/<Store ID>`로 바꿉니다.

### 업데이트할 때 (MSIX)
평소처럼 릴리스 → 그 실행의 `POSCHAT-msix` 산출물을 파트너 센터 *업데이트* 제출에 올립니다. 버전은 이전보다 커야 합니다.
Store판 사용자는 Store가 자동으로 업데이트합니다.

## EXE 방식 (코드 서명 인증서가 있을 때)
정책 원문: [Store 정책](https://learn.microsoft.com/windows/apps/publish/store-policies) ·
[EXE/MSI 요구 사항](https://learn.microsoft.com/windows/apps/publish/publish-your-app/msi/app-package-requirements)

### 앱이 이미 맞춘 것 (EXE 방식, 1.18)
| 요구(정책) | POSCHAT |
|---|---|
| 무인 설치(설치 화면 없이) | `POSCHAT-Store-Setup.exe --silent --no-desktop` (성공 0, 실패 1) |
| 독립 설치 파일(설치 중 내려받지 않음) | 앱 전체가 설치 파일 안에 있음 |
| 버전이 들어간 HTTPS 주소, 제출 뒤 파일이 바뀌지 않음(10.2.9) | `https://github.com/pidstech/POSCHAT/releases/download/vX.Y.Z/POSCHAT-Store-Setup.exe` — 릴리스마다 새 태그. **저장소가 비공개이면 이 주소로 받을 수 없으므로** 공개 HTTPS 주소가 필요합니다(업데이트 서버 `https://pidstech.com`에 Store용 파일도 올리도록 동기화를 넓히면 됩니다. 지금은 올리지 않습니다) |
| 설치 파일과 모든 PE 파일 서명(10.2.9) | 인증서를 넣으면 빌드가 exe·dll·pyd 중 서명 없는 것에 모두 서명(`build_installer.sign_tree`) — **인증서는 직접 구해야 함** |
| 심사한 파일만 설치 | Store판(`distribution.txt` = store)은 새 버전을 알리기만 하고 Microsoft Store를 엽니다. 스스로 내려받지 않습니다 |
| 깨끗한 제거(10.2.7) | 설정 → 앱에 'POSCHAT'으로 등록, 조용한 제거(`--uninstall --quiet`) |
| 다른 프로그램을 끼워 설치하지 않음(10.2.3) | 없음(WebView2는 Windows에 들어 있는 것을 씀) |
| 개인정보 처리방침(10.5.1, 데스크톱 앱은 언제나) | [docs/privacy-policy.md](privacy-policy.md) |
| 생성형 AI: 고지·신고 수단(11.16) | 답변마다 '부적절한 응답 신고'(Code 에이전트는 `/report`) → GitHub 이슈 양식 `ai-report` |

관리자 권한 없이 현재 사용자에게 설치합니다(`%LOCALAPPDATA%\Programs\PostechChat`). GitHub판과 같은 폴더·데이터를 쓰므로, 한 PC에 둘 중 하나만 설치됩니다(나중에 설치한 쪽으로 바뀜).

### 직접 할 일 (EXE 방식)
1. **개발자 계정(개인)** — https://storedeveloper.microsoft.com 에서 시작(이 경로는 등록비 없음). Microsoft 계정으로 로그인, 신분증과 셀카로 본인 확인.
   개인 계정은 나중에 회사 계정으로 바꿀 수 없습니다. Store에 보이는 게시자 이름(예: 김범준 또는 PIDS Tech. 팀)을 정합니다.
2. **이름 예약** — 파트너 센터 → 앱 및 게임 → 새 제품 → **EXE 또는 MSI 앱** → `POSCHAT` 가용성 확인 → 예약.
   예약 뒤 보이는 **Store ID(9N…)** 를 `updates.py`의 `STORE_PRODUCT_ID`에 넣습니다(Store판의 업데이트 안내가 POSCHAT 페이지를 엽니다).
3. **코드 서명 인증서** — Microsoft Trusted Root Program에 든 CA의 코드 서명 인증서(개인 개발자용 OV 등)를 삽니다.
   `.pfx`를 base64로 바꿔 저장소 Secrets에 `WINDOWS_SIGN_PFX_BASE64`, 암호를 `WINDOWS_SIGN_PASSWORD`로 넣습니다.
   - 하드웨어 토큰(USB)·클라우드 HSM으로만 주는 인증서는 `.pfx`가 없으므로 CI 서명 단계를 그 방식에 맞게 바꿔야 합니다(알려 주시면 고칩니다).
   - 인증서를 넣은 뒤의 릴리스 빌드 로그에 `PE 파일 N개 중 서명이 없는 M개에 서명합니다`가 나오고 `서명하지 못한 파일`이 없어야 합니다.
4. **GitHub 설정** — 저장소에 `ai-report` 라벨을 만들고(신고 이슈에 붙음), 저장소 설정에서 **Immutable releases**를 켜 두면 제출한 설치 파일이 바뀌지 않습니다.
5. **서명된 릴리스** — 인증서를 넣은 뒤 평소 절차로 릴리스합니다. 릴리스에 `POSCHAT-Store-Setup.exe`가 함께 올라갑니다.
6. **제출 정보 작성**(아래 값) → **인증을 위해 제출**. 보통 1~2일. 떨어지면 사유를 고쳐 다시 냅니다.

## 파트너 센터에 넣을 값

### 패키지 (EXE 방식만 — MSIX는 파일을 올림)
| 항목 | 값 |
|---|---|
| 패키지 URL | `https://github.com/pidstech/POSCHAT/releases/download/vX.Y.Z/POSCHAT-Store-Setup.exe` (X.Y.Z는 서명된 릴리스) |
| 아키텍처 | x64 |
| 설치 관리자 매개 변수(무인 설치) | `--silent --no-desktop` |
| 언어 | 한국어 |
| 반환 코드 | 0 = 성공, 1 = 설치 실패(자세한 내용은 `%TEMP%\PostechChat-install.log`) |

### 가격·출시
무료 · 시장: 대한민국(필요하면 전 세계) · 앱 내 구매 없음

### 속성
- 범주: 생산성(부범주 없음) — 또는 개발자 도구
- 개인정보 처리방침 URL: `https://github.com/pidstech/POSCHAT/blob/main/docs/privacy-policy.md`
- 웹사이트: `https://github.com/pidstech/POSCHAT` · 지원 연락처: `beomjoon@pidstech.com`
- 시스템 요구: Windows 10 이상 x64, 인터넷(클라우드 모델) · 마이크(PO노트, 선택)
- **생성형 AI**: 실시간 생성형 AI 콘텐츠를 쓴다고 표시(정책 11.16)

### 연령 등급(IARC 설문)
설문에 그대로 답합니다: 사용자끼리 소통하는 기능 없음, 생성형 AI가 사용자 입력에 따라 글을 만듦(사용자가 보지 않은 내용이 나올 수 있음), 위치 공유 없음, 디지털 구매 없음.

### Store 목록(한국어)
- **이름**: POSCHAT
- **짧은 설명**: 학생과 연구자를 위한 AI 작업 공간 — 채팅, 코드 에이전트, 논문 읽기, 강의 노트, 실험 기록을 한 앱에서.
- **설명**:

  > POSCHAT은 POSTECH GenAI API(학교 구성원) 또는 본인의 Claude API 키로 쓰는 AI 데스크톱 앱입니다.
  > PIDS Tech. 팀이 만들고 관리하는 비공식 프로젝트이며, 포항공과대학교(POSTECH)의 공식 제품이 아닙니다.
  >
  > - 채팅: 파일 첨부(PDF·Word·PowerPoint·Excel·한글), 작업 폴더를 읽고 고치는 에이전트(승인 후 실행)
  > - 코드: 편집기, Git, 명령 실행, 터미널 같은 Code 에이전트(계획·수정·테스트, 되돌리기)
  > - 논문: PDF 옆에서 선택한 문장·쪽·그림 묻기, 요약, 비교표
  > - PO노트: 강의 녹음을 기기 안에서 받아 적고 필기 노트 만들기
  > - Lab: 실험 조건·코드 버전·결과 기록과 비교
  > - 로컬 AI(Ollama)와 자동 모델 선택
  >
  > 이 앱은 생성형 AI를 사용합니다. AI의 답은 틀리거나 부적절할 수 있으니 중요한 내용은 확인하세요. 부적절한 답변은 답변 아래 신고 단추로 알려 주세요.
  > 대화와 파일은 개발자에게 보내지 않으며, 질문은 사용자가 고른 AI 서비스로만 전송됩니다.
  > 자유 소프트웨어(AGPL-3.0-only): https://github.com/pidstech/POSCHAT

- **검색어**: AI 채팅, 코딩 에이전트, 논문, 강의 노트, 연구 (다른 회사의 제품 이름은 넣지 않습니다 — 정책 10.1.3)
- **스크린숏**: 1장 이상(권장 4장 이상, 최대 10장). 채팅·코드(작업 탭)·논문·PO노트 화면. `POSTECH_UI_SHOTS=<폴더> python -m unittest tests.test_ui_smoke`로 만들 수 있습니다.
- **로고**: 1:1 상자 그림(필수), `assets/icon.png`에서 만듭니다.
- 로고·스크린숏·설명에 POSTECH 로고나 공식처럼 보이는 표현을 쓰지 않습니다(정책 10.1.1).

### 인증 참고 사항(심사자에게)
심사자는 POSTECH 계정이 없으므로 시험 방법을 적어 줍니다. 심사용 Claude API 키를 따로 만들어 넣고, 심사가 끝나면 지웁니다.

```
POSCHAT is an AI desktop app. To test without a POSTECH account:
1. Launch POSCHAT. The Settings window opens on first run (or click "설정" at the bottom left).
   Set "API 방식" to "일반 AI 모델 (Claude)", paste this test key into "Claude API 키 (Anthropic)": <심사용 키>, then save.
2. Type a question in the chat box and press Enter.
3. Code: click "코드" in the left sidebar, choose a folder as the workspace, type a task in the bottom ">" line.
Generative AI: answers are generated live. Users can report inappropriate answers with the flag button under each answer;
reports open a GitHub issue form (https://github.com/pidstech/POSCHAT/issues).
The MSIX package is a full-trust desktop app (Python + WebView2); runFullTrust is needed to run the user's own tools (git, terminal) on folders they choose.
```

## 업데이트할 때 (EXE 방식)
1. 평소처럼 릴리스(서명된 빌드)한다.
2. 파트너 센터 → POSCHAT → **업데이트**에서 패키지 URL을 새 버전 주소로 바꾸고 제출한다. 이미 제출한 주소의 파일은 절대 바꾸지 않는다.
3. Store판 사용자는 앱이 새 버전을 알리면 Microsoft Store에서 업데이트한다(심사가 끝나야 Store에 보임).

## 확인하지 못한 것
- Microsoft 문서는 Store가 이미 설치된 EXE 앱을 새 버전으로 자동 업데이트하는지 밝히지 않습니다. 그래서 Store판은 알림만 하고 Store를 엽니다.
  Store 화면에 '업데이트'가 보이지 않으면, Store의 POSCHAT 페이지에서 다시 설치하면 새 버전으로 바뀝니다(대화·설정은 그대로).
- 정책 11.16(생성형 AI)의 세부 문구는 요약본으로 확인했습니다. 제출 전에 원문을 한 번 더 확인하세요.
