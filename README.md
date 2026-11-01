
## 왜 만들었나요?
학교에서 제공하는 POSTECH GenAI API는 웹에서만 쓸 수 있어서 활용하기가 꽤 불편했습니다. 파일을 다루거나 코드를 돌리거나 내 작업 환경과 연결하기 어려워서, 좋은 API를 받아놓고도 "채팅창 하나"로만 쓰게 되더라고요.

그래서 우리 학교 학생들이 실제로 자주 쓰는 기능(수업 듣기, 논문 읽기, 코딩, 연구)을 한 앱에 담아서 PC에서 바로 쓸 수 있게 만들었습니다.

## 어떤 기능이 있나요?
- ChatGPT의 UI와 비슷한 직관적인 채팅 화면: 파일 첨부도 가능합니다. (파일당 20MB, 메시지당 10개)
- PO노트: 강의 녹음을 받아 필기 노트로 정리해주는 기능
- 에이전트 모드: 작업 폴더를 지정하면 AI가 그 폴더의 파일을 읽고, 수정하고, 명령까지 실행합니다. (Claude Code, Codex 같은 방식)
- 코드 작업: 전체 화면 코드 에디터, 코드 에이전트, SSH 환경 작업 지원
- 연구 도구: 리서치 라이브러리, 웹 리서치, 내장 브라우저, 논문 뷰어
- 대화 간 메모리: 이전 대화 내용을 기억해서 이어서 쓸 수 있습니다.
- 외부 서비스 연동: GitHub, Google, Notion, Office 등
- 기본은 POSTECH GenAI API, 원하면 본인의 Claude / OpenAI(GPT) API 키로도 사용 가능합니다.

## 다운로드 및 설치
다운로드: https://pidstech.com/poschat

[Windows]
1) POSCHAT-Setup.exe 다운로드 후 실행
2) 아직 코드 서명이 없어서 Windows 경고가 뜰 수 있습니다. "추가 정보 → 실행"을 누르면 됩니다.
3) "설치" 클릭 (관리자 권한 필요 없음)
4) 처음 실행할 때 POSTECH GenAI API 키 입력 (또는 설정에서 본인의 Claude/OpenAI 키 등록)

[macOS] (Apple Silicon M1 이상만 지원, Intel Mac은 미지원)
1) POSCHAT-mac.dmg를 열고 POSCHAT을 응용 프로그램 폴더로 드래그
2) 서명이 없는 앱이라 Control 키를 누른 채 클릭 → "열기"
   (macOS 15 이상은 설정 → 개인정보 보호 및 보안 → "그래도 열기")
3) 처음 실행할 때 API 키 입력

## 참고해주세요
- 포스텍 공식 서비스가 아닌 PIDS Tech.에서 만든 비공식 프로젝트입니다.
- 사용하려면 유효한 API 키가 필요합니다.
- 비밀번호나 API 키는 USER.md 같은 메모리 파일에 적지 마세요. 내용이 매 질문마다 함께 전송됩니다.

## 설치

설치 파일(`POSCHAT-Setup.exe`)은 저장소의 [Releases](https://github.com/pidstech/POSCHAT/releases)에서 받습니다. (Microsoft Store 제출 준비: [docs/microsoft-store.md](docs/microsoft-store.md), 개인정보 처리방침: [docs/privacy-policy.md](docs/privacy-policy.md)) 저장소 자체에는 exe를 넣지 않습니다. 설치 파일 하나에 Python, 화면 라이브러리(marked·DOMPurify·KaTeX), 문서 라이브러리, 내장 MCP 서버가 모두 들어 있으므로 npm·curl·Python을 따로 설치할 필요가 없습니다. 직접 빌드하려면 아래 [개발](#개발)을 보세요.

1. Releases에서 받은 `POSCHAT-Setup.exe`(또는 직접 빌드한 `release\POSCHAT-Setup.exe`)를 실행합니다.
2. 설치 프로그램에는 아직 코드 서명이 없어서 Windows가 "Windows의 PC 보호" 경고를 띄울 수 있습니다. 파일을 Releases에서 받았는지 확인한 뒤 **추가 정보 → 실행**을 누르세요. 경고를 없애려면 코드 서명 인증서가 필요합니다([배포](#배포) 참고). 보호 기능을 끄거나 예외를 추가하는 것을 설치 절차로 요구하지 않습니다.
3. **설치**를 누릅니다. 관리자 권한은 필요 없습니다.
   - 설치 위치: `%LOCALAPPDATA%\Programs\PostechChat` (이전 버전에서 그대로 업데이트되도록 폴더·실행 파일·데이터 폴더 이름은 1.10과 같습니다)
   - 시작 메뉴와 바탕화면에 바로가기가 생깁니다.
4. 처음 실행하면 설정 창이 열립니다. POSTECH GenAI API 키를 입력하세요. 본인 Claude API 키로 쓰려면 API 방식에서 **일반 AI 모델 (Claude)**를, 본인 OpenAI API 키로 GPT를 쓰려면 **일반 AI 모델 (GPT)**를 고르고 키를 넣습니다.

제거는 **설정 → 앱 → 설치된 앱 → POSCHAT → 제거**에서 합니다. 대화 기록과 설정(`%APPDATA%\PostechChat`)은 지우지 않고 남겨 둡니다.

### macOS

Releases의 `POSCHAT-mac.dmg`를 받아 엽니다. Apple Silicon(M1 이후) 맥용이며 Intel 맥은 지원하지 않습니다.

1. 열린 창에서 **POSCHAT**(앱 파일 이름은 PostechChat.app)을 **Applications(응용 프로그램)** 폴더로 끌어다 놓습니다.
2. 앱에는 Apple 개발자 서명·공증이 없어서, 처음 실행하면 "확인되지 않은 개발자" 또는 "열 수 없음" 경고가 뜹니다. 응용 프로그램 폴더에서 앱을 **Control 키를 누른 채 클릭 → 열기**를 누르세요. macOS 15 이후에서는 **시스템 설정 → 개인정보 보호 및 보안**의 아래쪽에서 **그래도 열기**를 누릅니다. 한 번 허용하면 이후에는 그대로 실행됩니다.
3. 처음 실행하면 설정 창이 열립니다. POSTECH GenAI API 키를 입력하세요.

대화 기록과 설정은 `~/Library/Application Support/PostechChat`에 저장됩니다. 에이전트의 `run` 단계는 macOS 셸(`/bin/sh`)로 실행됩니다. 제거는 응용 프로그램 폴더의 앱을 휴지통으로 옮기면 됩니다(대화 기록 폴더는 남습니다).

### 설치 문제 해결

설치 중 오류나 지연이 발생하면 보안 제품의 알림과 설치 로그를 확인하세요. 조직에서 관리하는 PC는 관리자 정책을 따르세요.

- 시작 메뉴에 `POSCHAT (2)`라는 이름으로 바로가기가 생길 수 있습니다. 같은 이름의 이전 바로가기를 탐색기가 아직 붙잡고 있을 때 생기며, 재부팅하면 풀립니다.
- 바로가기를 만들지 못해도 설치는 끝납니다. 이때는 `%LOCALAPPDATA%\Programs\PostechChat\PostechChat.exe`로 실행하세요.
- 조용한 설치 로그: `%TEMP%\PostechChat-install.log`

### 안드로이드(기존 배포본)

2026-10-26부터 Android 빌드·배포는 중단했습니다. 아래는 기존 배포본의 사용 안내이며, 앞으로는 Windows·macOS만 빌드합니다.

과거 Releases의 `POSCHAT.apk`를 휴대폰에서 받아 설치합니다(Android 7.0 이상, 64비트 ARM). 스토어 앱이 아니므로 처음 설치할 때 "출처를 알 수 없는 앱 설치"를 허용해야 합니다. 새 버전도 APK를 그대로 설치하면 대화·설정을 유지한 채 업데이트됩니다. 1.9.1부터는 앱이 새 버전을 알려 주고 APK를 받아 설치 화면을 엽니다.

데스크톱과 같은 화면과 Python 코드(에이전트, 문서 읽기, 내장 MCP 서버, 스트리밍, 수식)를 앱 안에서 그대로 실행합니다. 다른 점은 다음과 같습니다.

- 사이드바는 왼쪽 위 버튼으로 여는 서랍이고, 뒤로 가기로 창·사이드바를 닫습니다. 입력창의 Enter는 줄바꿈이며 보내기 버튼으로 보냅니다.
- 작업 폴더를 고르면 "모든 파일 접근" 권한을 요청합니다. 에이전트가 휴대폰 저장소의 일반 폴더(예: `Documents/보고서`)를 읽고 고치려면 필요합니다. 작업 폴더 없이 대화만 할 때는 필요 없습니다.
- `run` 단계는 안드로이드 셸(`/system/bin/sh`)로 실행됩니다. Python·Node 같은 개발 도구는 없습니다.
- 내장 MCP 서버(Word·PowerPoint·Excel·paper·notion·firecrawl)는 앱 안에서 바로 동작합니다. 추천 서버(Playwright)는 보이지 않습니다. `npx`·`uvx`가 필요한 외부 MCP 서버는 휴대폰에서 실행할 수 없습니다.
- 대화 기록과 설정은 앱 전용 저장소에 따로 있으며 PC와 동기화되지 않습니다.

## 사용법

| 기능 | 방법 |
|---|---|
| 사용법 가이드 | 왼쪽 아래 **설정** → **사용법 가이드**, 또는 `/help` → **사용법 가이드** |
| 새 대화 | 왼쪽 위 **새 채팅** (Ctrl+Shift+O) |
| 대화 이름 변경·삭제 | 대화 목록에 마우스를 올리면 나오는 연필·휴지통 아이콘 |
| 작업 폴더 지정 | 왼쪽 아래 **작업 폴더**, 또는 입력창의 폴더 칩 |
| 에이전트 켜기·끄기 | 오른쪽 위 **에이전트** 스위치 |
| 명령어·스킬 | 입력창에 `/`를 입력하면 목록이 뜹니다 |
| 파일 첨부 | 입력창의 + 버튼, 파일 끌어다 놓기, 이미지 붙여 넣기(Ctrl+V) |
| 내 정보(USER.md) | 왼쪽 아래 **내 정보**, `/user` |
| 메모리(memory.md) | 왼쪽 아래 **메모리**, `/remember 내용`, `/memory` |
| MCP 서버 켜기·끄기, 외부 서버 추가 | 왼쪽 아래 **연결·도구** → MCP 서버 |
| AI 실행 정책·로컬 AI | **설정 → AI 실행 정책**. 자동 모델 선택(Economy·Balanced·Quality·Local Only), Ollama 연결·모델 받기, 3단계(경량 Cloud 모델과 프런티어 상담)·단가·손익분기·프롬프트 캐싱, 대화 위 모델 목록의 **자동**·**로컬**, **설정 → 개발자 모드** ([설정](docs/adaptive-ai-setup.md), 1.17) |
| 에이전트의 인터넷 조사 | 에이전트에게 조사를 맡기면 웹 검색(`web_search`)·웹페이지·PDF 읽기(`web_fetch`)·저자별 논문 목록(`paper_search`)·파일 받기(`web_download`)로 직접 찾습니다. 끄기는 **연결·도구 → 기능** ([릴리스 노트](docs/release-notes/v1.18.1.md), 1.18.1) |
| Code 에이전트(작업 맡기기) | **코드** → 맨 앞 **작업** 탭(터미널). 할 일을 쓰고 Enter. 계획·diff·실행 출력, 이어서 지시, 바뀐 파일 되돌리기 ([사용법](docs/code-editor-guide.md#code-에이전트-작업-맡기기-116), 1.16). 권한 모드(계획·전체 자동), 다시 묻지 않기, 작업 중 추가 지시, `/init` `/review` `/test` `/plan` `/undo` `/compact`, AGENTS.md, 격리 작업 공간(git worktree) (1.17.1). 터미널 화면·기록 안 승인·Shift+Tab·Esc·`!` `#` `@`·`/resume` `/status` `/diff` 등·프로젝트 명령 ([사용법](docs/code-editor-guide.md#code-에이전트-3-터미널처럼-쓰기-1172), 1.17.2) |
| Lab(실험 기록·비교·AI 분석) | 왼쪽 위 **Lab**. 실험·Run, 승인 실행, 재현성 기록, 결과 가져오기, 지표·그래프·비교, AI 분석 ([사용법](docs/lab-guide.md), 1.16) |
| PLMS (베타) | 사이드바 맨 아래 **PLMS(베타 표시) → SSO 로그인 → 내 수업 불러오기**. 수업별 공지·자료를 보고 PDF 미리보기, PowerPoint 앱 열기, 에이전트 정리를 사용합니다(자료 20MB까지). [사용법·한계](docs/plms-guide.md) |
| 브라우저 에이전트 | 브라우저를 연 채 에이전트에게 웹 작업을 맡기면 페이지를 직접 조작합니다. 브라우저 막대에서 일시정지·멈춤 ([보안](docs/browser-agent-security.md), 1.16) |
| 코드(전체 화면 편집기) | 왼쪽 위 **코드**(1.17.2부터 하나의 전체 화면). 파일 트리·편집·저장(Ctrl+S), 선택한 코드 AI에게 묻기, 에이전트 변경 덩어리별 검토, Git 상태·차이·스테이지·커밋(왼쪽 Git 탭) ([사용법](docs/code-editor-guide.md), 1.15). 아래 패널은 진짜 터미널(PowerShell·로그인 셸, **Ctrl+`**) ([사용법](docs/code-editor-guide.md#터미널-118), 1.18) |
| 논문(채팅 옆 PDF) | 왼쪽 위 **논문**. PDF 열기·arXiv 번호, 선택한 부분·이 쪽·영역 잘라 묻기, 논문 요약, 라이브러리 논문 비교표 (1.14) |
| 브라우저(채팅 옆 웹페이지) | 왼쪽 위 **브라우저**. 주소창, 이 페이지에 대해 묻기·선택한 부분 묻기·연구 라이브러리에 저장 (1.13) |
| 플러그인(직무별 스킬 묶음) | 왼쪽 위 **플러그인**에서 설치·켜기·끄기. 입력창에 `/플러그인:스킬` (1.12) |
| 연구 라이브러리·에이전트 자동화 | 왼쪽 위 **연구 라이브러리**·**에이전트 자동화** (1.11부터 PO노트처럼 본문 화면) |
| 본인 Claude API 키로 쓰기 | **설정 → API 방식 → 일반 AI 모델 (Claude)** ([아래](#모델과-스트리밍)) |
| 본인 OpenAI API 키로 GPT 쓰기 | **설정 → API 방식 → 일반 AI 모델 (GPT)** (1.18) |
| SSH 서버의 폴더에서 코드 작업 | **코드 → SSH**. 파일·Git·터미널·Code 에이전트가 서버에서 돎(키·OTP·ProxyJump, 서버에 python3만) ([사용법](docs/code-editor-guide.md#ssh-서버의-폴더에서-일하기-118), 1.18) |
| PO노트(강의 녹음·전사·필기 노트) | 왼쪽 위 **PO노트** ([아래](#po노트)) |
| 대화별 모델 선택 | OpenAI 호환·Responses API·일반 AI 모델(Claude·GPT)에서 위쪽 **대화 모델** 메뉴로 고릅니다. 각 대화의 선택은 따로 저장됩니다. |
| 크레딧 확인 | 왼쪽 아래 **설정** → POSTECH GenAI 크레딧(PO노트 화면에도 표시). 이 키의 이번 주 사용량·한도·남은 양. 확인 자체는 크레딧을 쓰지 않습니다. |
| 모델 API 사용량 보기 | 입력창·코드 작업 탭에서 `/usage`(1.18.1), 또는 왼쪽 아래 **설정** → 모델 API 사용량. 이 앱에서 보낸 요청의 오늘·이번 달·최근 30일 호출 수와(서버가 알려 주면) 토큰 수. |

### 대화 간 정보 공유 (메모리 · 다른 대화 참고)

대화(스레드)마다 기록은 따로 저장되지만, 다음 두 가지 방법으로 서로 정보를 주고받습니다.

- **메모리**: 모든 대화에 공통으로 전달되는 기억입니다. 대화 중에 "~를 기억해 줘", "잊지 마"라고 하면 앱이 기억할 내용을 한 문장으로 정리해 저장합니다. 이때 대화에 `🧠 기억: …` 줄이 표시됩니다. `/remember 내용`으로 직접 추가할 수도 있습니다. "기억해?"처럼 묻는 말은 저장하지 않습니다.
- **다른 대화 참고**: 새 질문과 관련된 내용이 다른 대화에 있으면 자동으로 찾아 함께 참고합니다. 참고한 대화는 `📎 다른 대화 참고: …`로 표시됩니다. 에이전트 모드에서는 "지난번에 얘기한 …"처럼 말하면 `recall` 단계로 다른 대화를 직접 검색합니다. 메모리 창에서 끌 수 있습니다.

메모리는 `%APPDATA%\PostechChat\memory.md`에 Markdown으로 저장됩니다. `- `로 시작하는 줄 하나가 기억 하나이고, 메모리 창에서 항목을 보거나 지울 수 있으며 **memory.md 편집**으로 파일 전체를 직접 고칠 수 있습니다. 제목이나 설명을 더 써도 모두 대화에 전달되고, `<!-- -->` 안의 안내문만 빠집니다. 1.4 이전의 `memory.json`은 처음 실행할 때 memory.md로 옮겨집니다(원래 파일은 그대로 둡니다).

### 내 정보 (USER.md)

`%APPDATA%\PostechChat\USER.md`는 나에 대한 정보(하는 일, 관심 분야, 선호하는 답변 방식 등)이며, 작업 폴더의 INIT.md처럼 모든 대화에 함께 전달되어 답변을 나에게 맞추는 데 쓰입니다.

- **직접 쓰기**: 왼쪽 아래 **내 정보**에서 고치고 저장합니다.
- **AI로 작성·업데이트**: `/user`를 입력하면(또는 내 정보 창의 **AI로 작성·업데이트**) AI가 모든 대화의 최근 사용자 메시지와 메모리를 살펴보고 USER.md를 새로 쓰거나 고칩니다. 기존 내용은 어긋나지 않는 한 유지하고, 근거 없는 내용은 쓰지 않습니다. `/user 소속은 빼 줘`처럼 요청을 덧붙이거나 이력서 같은 파일을 첨부해 함께 보낼 수 있습니다. 바뀐 내용은 대화에 `📝 USER.md` 줄로 비교해 보여 줍니다.
- 비밀번호나 API 키 같은 비밀 정보는 적지 마세요. 내용은 질문할 때마다 POSTECH GenAI API로 전달됩니다.

### 파일 첨부

입력창 왼쪽 아래의 + 버튼으로 파일을 고르거나, 파일을 창에 끌어다 놓거나, 이미지를 붙여 넣으면 첨부됩니다. 파일은 하나에 20MB, 한 번에 10개까지입니다.

- **문서·텍스트**: PDF·Word·PowerPoint·Excel·한글 문서와 텍스트 파일(코드, CSV, Markdown 등)은 글자를 뽑아 질문과 함께 보냅니다(파일 하나에 2만 자, 한 번에 4만 자까지). 기억하는 이전 메시지 범위 안이면 다음 질문에서도 그 파일 내용을 다시 참고합니다.
- **이미지**(PNG·JPEG·GIF·WebP): 설정의 API 방식이 **OpenAI Responses API** 또는 **OpenAI 호환 API**일 때 모델이 이미지를 직접 봅니다. 기본 방식(a1)은 글자만 보낼 수 없습니다.
- 첨부한 파일은 `%APPDATA%\PostechChat\attachments`에 복사해 두고, 대화를 지우면 함께 지웁니다. 보낸 메시지의 파일을 누르면 알맞은 앱으로 엽니다.

### PO노트

강의를 녹음해 실시간으로 받아 적고, 강의 자료와 함께 복습용 필기 노트를 만듭니다. 왼쪽 위 **PO노트**에서 강의마다 노트를 만듭니다.

1. **새 강의 노트**를 만들고 **강의 자료**(PPT·PDF·Word·Excel·한글·텍스트, 노트 하나에 10개까지)를 올립니다.
2. **녹음 시작**을 누르면 마이크 소리를 말 구간마다 끊어 받아 적고 **전사** 탭에 `[분:초] 글`로 쌓습니다. 강의 중 떠오른 질문이나 칠판 필기는 **메모** 탭에 적습니다. 멈췄다가 **이어서 녹음**할 수 있습니다.
3. **노트 만들기**를 누르면 고른 모델이 강의 자료의 순서(슬라이드·페이지)를 뼈대로 전사와 메모를 합쳐 Markdown 필기 노트를 씁니다. 말로만 나온 설명은 `💬`, 시험·과제 같은 강조는 `⭐`로 표시하고, 끝에 핵심 정리·용어 정리·확인할 것을 둡니다. 전사가 길면 부분별로 정리한 뒤 합칩니다.
4. 노트·전사·자료 내용은 앱 안에서 보고, 노트는 **고치기**로 직접 고칩니다. **폴더 열기**로 `note.md`·`transcript.md`를 다른 앱에서 열 수 있습니다.

**음성 인식 설정**(PO노트 화면)에서 받아 적는 방식을 고릅니다.

| 방식 | 처리 | 비용 | 특징 |
|---|---|---|---|
| 자동 (기본, 권장) | 하이브리드: 로컬 AI가 바로 받아 적고, 약 2분치 구간 가운데 로컬 AI가 확신하지 못한 구간이 있을 때만 POSTECH 서버가 음성과 초안을 대조해 고칩니다 | 1시간에 0~약 420크레딧 | 글이 바로 뜨고, 서버가 실패해도 로컬 글이 남습니다. 줄마다 시각을 유지합니다. API 키가 없으면 로컬 AI만 씁니다. |
| POSTECH 서버로 모두 | OpenAI 호환 API의 Gemini 3.8 Flash가 음성(`input_audio`)을 받아 적습니다 | 1시간에 약 1,000~1,300크레딧(주간 한도 15,000의 약 7~9%) | 말 구간을 약 25초씩 모아 보냅니다. 실패하면 로컬 AI(있으면)로 받아 적습니다. |
| 로컬 AI만 | 이 PC에서 [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)로 처리 | 없음(인터넷도 필요 없음) | CPU 스레드 2개만 쓰는 가벼운 모델. |

- **크레딧은 거의 호출 수로 정해집니다**(호출당 약 8크레딧 + 음성 1초당 약 0.05크레딧, 5초 9 · 23초 9 · 60초 10 · 120초 14크레딧으로 측정). 그래서 하이브리드는 서버 보정을 약 2분씩 모아 한 번에 보냅니다.
- **로컬 신뢰도**: 한국어 모델은 토큰 확률의 평균을 신뢰도로 냅니다. 0.8 아래인 줄은 전사 화면에서 흐리게 보이고, 그런 줄이 든 묶음은 서버가 보정합니다. 다국어 모델은 신뢰도를 내지 않아 모든 묶음을 보정합니다.
- **로컬 AI 정확도**(1.10.0, 독립 공개 데이터의 글자 오류율, 숫자 표기 차이는 뺌):
  - 측정 데이터: Zeroth-Korean(낭독 뉴스, 60문장)과 FLEURS 한국어(위키 문장 낭독, 60문장).

  | 로컬 모델 | Zeroth | FLEURS | 처리 속도(이 PC 기준, 실시간 대비) |
  |---|---|---|---|
  | 한국어 | 약 27% | 약 11% | 약 50배 빠름 |
  | 다국어 | 약 4% | 약 5% | 약 20배 빠름 |

  - 한국어 모델은 대화체(KsponSpeech)로 학습해 낭독 음성에 약하고, 신뢰도 0.8 이상인 줄도 10~17%가 틀렸습니다. 서버 보정이 이를 메웁니다.
  - 다국어 모델의 수치는 이 공개 데이터를 학습에 썼을 수 있어 낙관적일 수 있습니다.
  - 1.10.0부터 작은 소리(강의실 뒤쪽 등)를 키워서 인식합니다. 전에는 한국어 모델이 작은 소리에 빈 글을 냈습니다(FLEURS 오류율 46%→11%).
  - 영어가 섞이거나 정확도가 더 중요하면 다국어 모델을 고르세요.
- **크레딧 예산 보호**(기본: 30% 남기기): 이번 주 남은 크레딧이 한도의 이 비율 아래면 서버를 쓰지 않고 로컬 AI로만 받아 적어, 채팅과 노트 만들기에 쓸 크레딧을 남깁니다. 0~50% 또는 끄기로 바꿉니다.
- 자동 방식에서 로컬 모델이 아직 없으면 첫 녹음은 서버로 받아 적으면서 한국어 모델을 내려받고, 다음 녹음부터 하이브리드로 동작합니다.
- POSTECH GenAI에는 음성 인식 전용 API(`/audio/transcriptions`)가 없어서 Chat Completions의 음성 입력으로 받아 적습니다.

로컬 AI 모델은 둘 중에서 고릅니다.

| 모델 | 내려받기 | 언어 | 비고 |
|---|---|---|---|
| 한국어 (권장) | 약 76MB | 한국어 | k2-fsa Zipformer(KsponSpeech 학습). 가장 가볍고 한국어 띄어쓰기까지 정확합니다. |
| 다국어 | 약 240MB | 한국어·영어·일본어·중국어 | SenseVoice Small. 영어 강의나 한영 혼용 강의용입니다. |

- 말 구간은 음성 구간 검출(Silero VAD, 약 2MB, 첫 녹음 때 자동으로 내려받음)로 끊습니다. 녹음 소리 자체는 저장하지 않고 전사 글만 저장합니다.
- 마이크는 설정에서 고릅니다(기본: 시스템 기본 마이크). macOS는 처음 녹음할 때 마이크 권한을 묻습니다.
- **안드로이드**(1.10.0부터): 처음 녹음할 때 마이크 권한(과 Android 13부터 알림 권한)을 묻습니다. 녹음하는 동안 "PO노트 녹음 중" 알림이 떠 있고, 화면을 끄거나 다른 앱으로 가도 계속 받아 적습니다. 알림의 **녹음 중지**로도 멈춥니다. 인식은 휴대폰 안에서 하며(데스크톱과 같은 sherpa-onnx를 C 라이브러리로 넣었습니다), 이 때문에 APK가 이전보다 커졌습니다. 녹음 중에는 휴대폰 CPU를 써서 배터리가 평소보다 빨리 닳습니다.
- 데이터는 `%APPDATA%\PostechChat\po_notes\<id>\`(`meta.json`, `transcript.json`, `note.md`, `memo.md`, `materials\`)에, 로컬 AI 모델은 `stt_models\`에 저장합니다.

### 에이전트 모드

작업 폴더를 지정하고 에이전트를 켜면, AI가 목표를 이룰 때까지 단계를 반복합니다.

- `list` 폴더 보기 · `read` 파일 읽기 · `search` 내용 검색
- `write` 파일 작성 · `edit` 부분 수정 · `run` 명령 실행(Windows cmd)
- `skill` 스킬 불러오기 · `recall` 다른 대화 검색 · `done` 최종 답변
- `mcp` MCP 도구 실행(아래 [MCP](#mcp))

각 단계는 대화에 한 줄씩 표시되고, 누르면 자세한 내용(파일 내용, 변경 diff, 명령 출력)이 펼쳐집니다. **파일 수정과 명령 실행은 실행 전에 diff나 명령을 보여 주고 승인을 받습니다.** 설정에서 "파일 수정은 자동 허용" 등으로 바꿀 수 있습니다. 파일 도구는 경로를 검사해 작업 폴더 밖의 접근을 차단합니다. 다만 `run`은 작업 폴더를 시작 위치로 하는 일반 셸 명령이며, 운영체제 수준의 샌드박스가 아닙니다. 승인한 명령은 현재 사용자 권한으로 다른 위치나 네트워크에 접근할 수 있습니다.

작업 폴더가 없거나 에이전트를 끄면 일반 챗봇으로 동작합니다.

### 모델과 스트리밍

**설정 → API 방식**에서 고릅니다. 1.9부터 기본은 OpenAI 호환 API이며, 주소를 비워 두면 POSTECH GenAI 콘솔(에이전트 API → OpenAI Compatible API)의 `https://genai.postech.ac.kr/agent/openai_compatible/a1/v1/chat/completions`를 씁니다. Responses 방식은 콘솔에서 확인한 HTTPS 주소를 넣어야 저장할 수 있습니다. 새 대화의 기본 모델은 설정에서 고르고, 현재 대화 모델은 화면 위쪽 **대화 모델** 메뉴에서 바꿉니다. 각 대화는 생성 당시의 기본 모델 또는 직접 선택한 모델을 따로 저장하므로, 기본 설정을 바꿔도 기존 대화의 모델은 유지됩니다.

| 방식 | 주소 | 모델 | 특징 |
|---|---|---|---|
| OpenAI 호환 (기본, 권장) | 비워 두면 POSTECH 주소. 기본 주소(`.../v1`)만 넣어도 됨 | GPT·Claude·Gemini | Chat Completions, 표준 SSE 스트리밍. 인증은 `x-api-key`(다른 OpenAI 호환 서버를 위해 Bearer도 함께 보냄) |
| Responses | 콘솔에서 확인한 `.../a<번호>/openai/responses` | GPT-5 계열 | OpenAI Responses API, 표준 SSE 스트리밍 |
| a1/gpt (예전 기본값) | `agent/api/a1/gpt` | 서버가 정함 | 2026년 10월 현재 서버가 답변 대신 오류 코드 10000만 돌려줍니다. 1.9는 a1을 쓰던 설정을 한 번 OpenAI 호환으로 옮깁니다. |
| 일반 AI 모델 (Claude) (1.11) | `api.anthropic.com` (Claude Messages API) | Claude Opus 5.5(권장)·Sonnet 5.5·Haiku 5.5·Fable 5.1, 또는 키로 쓸 수 있는 모델 전체 | 본인 Claude API 키. 공식 Anthropic SDK(데스크톱)·같은 HTTP 요청(안드로이드), SSE 스트리밍, 이미지 첨부 |
| 일반 AI 모델 (GPT) (1.18) | `api.openai.com/v1/responses` (OpenAI Responses API) | GPT-5.1(권장)·GPT-5.2·GPT-5 mini·GPT-4.1 mini, 또는 키로 쓸 수 있는 대화 모델 전체 | 본인 OpenAI API 키(Bearer). HTTP 요청(데스크톱·안드로이드 같음), SSE 스트리밍, 이미지 첨부, GPT-5 계열은 추론 낮음 |

모델 선택 방식에서 고를 수 있는 GPT 모델은 POSTECH 게이트웨이가 허용하는 목록입니다. 가격은 OpenAI 공개 가격(입력/출력 100만 토큰당, USD)이며, 학교 계정의 실제 과금·한도는 POSTECH GenAI 콘솔에서 확인하세요.

| 모델 | 용도 | 가격(입력/출력) |
|---|---|---|
| **GPT-5.1 (기본, 권장)** | 성능과 비용의 균형 | $1.25 / $10 |
| GPT-5.2 | 가장 좋은 성능 | $1.75 / $14 |
| GPT-5 | GPT-5.1의 이전 버전 | $1.25 / $10 |
| GPT-5 mini | 빠르고 저렴, 에이전트 단계가 많을 때 | $0.25 / $2 |
| GPT-4.1 mini | 추론 없는 저렴한 모델 | — |
| GPT-6.1 Sol | POSTECH GenAI 2026년 10월 안내 모델 | 콘솔에서 확인 |
| GPT-6 Astra | POSTECH GenAI 2026년 10월 안내 모델 | 콘솔에서 확인 |
| Claude Opus 5.5 | POSTECH GenAI 2026년 10월 안내 모델 | 콘솔에서 확인 |
| Claude Sonnet 5.5 | POSTECH GenAI 2026년 10월 안내 모델 | 콘솔에서 확인 |
| Gemini 3.8 Flash | POSTECH GenAI 2026년 10월 안내 모델 | 콘솔에서 확인 |

표의 10개 모델은 모두 OpenAI 호환 API에서 응답하는 것을 확인했습니다(2026년 10월). Claude 모델 ID는 점이 아니라 `-`를 씁니다(`claude-opus-5-5`, `claude-sonnet-5-5`). POSTECH 서버는 모델 목록(`GET .../models`)을 알려 주지 않으므로 기본 목록을 씁니다. 다른 OpenAI 호환 서버는 **모델 목록 불러오기**로 그 서버의 모델을 받아 저장할 때 반영합니다. GPT-5 계열은 Responses API에서도 계속 사용할 수 있습니다.

**일반 AI 모델 (Claude)** (1.11): [Anthropic 콘솔](https://console.anthropic.com)에서 발급한 본인 Claude API 키(`sk-ant-...`, 또는 환경 변수 `ANTHROPIC_API_KEY`)로 대화·에이전트·PO노트 노트 만들기·대화 요약·모델 평가를 모두 Claude API로 보냅니다. 요금은 그 키의 Anthropic 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. 키와 기본 모델은 POSTECH 쪽과 따로 저장되므로 방식만 바꿔 오갈 수 있고, 동기화되지 않습니다. Claude API는 음성을 받지 않으므로 PO노트의 서버 음성 보정과 크레딧 확인은 POSTECH 키가 있을 때만 씁니다(없으면 로컬 AI로만 받아 적습니다). Opus 5.5·Sonnet 5.5·Fable 5.1은 안전 정책으로 답하지 않으면 Anthropic이 권하는 다른 모델로 다시 답하게 합니다(server-side fallback).

**일반 AI 모델 (GPT)** (1.18): [OpenAI 플랫폼](https://platform.openai.com/api-keys)에서 발급한 본인 OpenAI API 키(`sk-...`, 또는 환경 변수 `OPENAI_API_KEY`)로 모든 모델 호출을 OpenAI Responses API로 보냅니다(`store: false`). 요금은 그 키의 OpenAI 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. 키와 기본 모델은 따로 저장되고 동기화되지 않습니다. **모델 목록 불러오기**는 그 키로 쓸 수 있는 대화 모델만(음성·이미지·임베딩 전용 제외) 최근 것부터 보입니다. PO노트의 서버 음성 보정과 크레딧 확인은 POSTECH 키가 있을 때만 씁니다.

**크레딧**: POSTECH GenAI는 모든 응답 헤더(`x-role-ratelimit-credit-usage`, `-limit`, `-interval`)에 이 키의 이번 주 크레딧 사용량과 한도를 담아 줍니다. 앱은 이 값을 설정 창과 PO노트에 보여 주고, **확인**을 누르면 크레딧을 쓰지 않는 요청(404가 나는 `GET .../models`)으로 새로 받습니다. 직접 잰 값(Claude Sonnet 5.5): 1크레딧 ≈ 입력 약 250토큰 또는 출력 약 75토큰이고, 짧은 질문도 호출마다 약 24크레딧이 듭니다. Claude Opus 5.5는 모두 두 배입니다. 에이전트 모드는 단계마다 모델을 한 번씩 부르므로 단계 수만큼 이 기본 비용이 붙습니다.

**스트리밍**(설정 → 답변을 받는 대로 표시)을 켜면 일반 대화의 답변이 글자가 오는 대로 표시됩니다. 기본으로 켜져 있습니다. 에이전트 모드는 단계 선택이 JSON이라 단계 진행만 표시하고 최종 답변은 한 번에 표시합니다. 모델 선택 방식은 OpenAI 표준 SSE를 씁니다. a1 방식은 스트리밍 형식이 문서에 없어서 SSE·JSON Lines·일반 텍스트를 모두 받아 주며, 알 수 없는 형식이면 자동으로 한 번에 받는 방식으로 다시 요청합니다. 표시가 이상하면 스트리밍을 끄세요.

### 문서 읽기

`read`와 `search`는 텍스트 파일뿐 아니라 다음 문서도 읽습니다. 문서에서 글자만 뽑아 AI에게 전달하며, 이미지·도형 안의 그림은 읽지 못합니다.

| 형식 | 읽는 내용 |
|---|---|
| PDF (`.pdf`) | 페이지별 텍스트. 스캔한 이미지 PDF와 암호 걸린 PDF는 읽지 못합니다. |
| Word (`.docx`) | 문단, 제목 단계, 글머리 기호, 표 |
| PowerPoint (`.pptx`) | 슬라이드별 텍스트, 표, 발표자 노트 |
| Excel (`.xlsx`, `.xlsm`) | 시트별 셀 값과 셀 주소(예: `B3=90`). 계산 값이 없는 수식은 수식으로 표시 |
| 한글 (`.hwp`, `.hwpx`) | 본문·표·글상자 텍스트. 암호·배포용 문서와 HWP 3.x 이하는 읽지 못합니다. |

예전 Office 형식(`.doc`, `.ppt`, `.xls`)은 읽지 못하므로 Office에서 새 형식으로 저장한 뒤 사용하세요. 문서는 50MB까지 읽고, `search`는 20MB 이하 문서만 검색합니다.

### MCP

1.10부터 MCP 목록은 **연결·도구 → MCP 서버** 탭에 있고, 커넥터(GitHub·Google 등)의 서버는 **커넥터** 탭에서 켭니다([API 레퍼런스](docs/api/reference.md)).

MCP(Model Context Protocol)는 AI 도구를 연결하는 표준입니다. 에이전트 모드에서 켜진 MCP 서버의 도구가 `mcp` 단계로 제공됩니다. 서버는 처음 필요할 때 작업 폴더를 현재 폴더로 해서 실행되고, 작업 폴더나 설정이 바뀌면 다시 실행됩니다. 앱을 닫으면 함께 종료됩니다.

**내장 서버**는 앱에 들어 있어 따로 설치할 것이 없고, 작업 폴더 안의 파일만 다룹니다. 모두 무료로 쓸 수 있습니다.

| 서버 | 도구 |
|---|---|
| `word` | `create_document`(마크다운으로 새 .docx), `append_content`(끝에 덧붙이기), `replace_text`(글자 바꾸기, 서식 유지) |
| `powerpoint` | `create_presentation`(슬라이드 목록으로 새 .pptx, 16:9), `add_slides`, `replace_text` |
| `excel` | `create_workbook`(시트·행으로 새 .xlsx, `=`로 시작하면 수식), `write_cells`(셀 주소부터 값 쓰기) |
| `paper` | `search`(arXiv·Semantic Scholar에서 논문 찾기), `info`(저자·게재처·인용 수·한 줄 요약·초록), `read`(목차를 찾아 섹션·쪽 단위로 본문 읽기), `related`(참고한 논문·인용한 논문), `download`(PDF를 작업 폴더에 저장) |
| `notion` | `search`, `read_page`(페이지를 마크다운으로), `query_database`(데이터베이스 행 보기·필터), `create_page`(마크다운으로 새 페이지·데이터베이스 행), `append_content`, `update_page`(제목·속성 바꾸기) |
| `firecrawl` | `scrape`(웹페이지를 마크다운으로), `search`(웹 검색, 본문까지 가져오기 선택), `map`(사이트의 페이지 주소 목록), `crawl`(여러 페이지 따라가며 읽기), `crawl_status` |

**추천 서버**는 앱이 실행 방법을 아는 외부 서버입니다. 기본으로 꺼져 있고 **MCP** 창에서 켭니다. PC에 [Node.js](https://nodejs.org)가 있어야 하며 휴대폰에서는 쓸 수 없습니다.

| 서버 | 내용 |
|---|---|
| `playwright` | [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)(`@playwright/mcp@0.0.83`). 브라우저를 열어 페이지 이동·클릭·입력·스크린샷·폼 채우기. Windows에서는 설치된 Edge를 씁니다. 스냅숏·스크린샷은 작업 폴더의 `.playwright-mcp/`에 저장됩니다. 모든 조작은 명령 실행처럼 승인을 받습니다. |
| `context7` | [Context7 MCP](https://github.com/upstash/context7)(`@upstash/context7-mcp@4.4.4`). 라이브러리 이름을 찾고 관련 문서를 조회합니다. Node.js 20.18.1 이상과 인터넷이 필요합니다. 키 없이도 제한적으로 쓸 수 있으며, 조회할 질문이 Context7에 전달됩니다. Code 작업에서도 사용할 수 있습니다. |

Context7은 **연결·도구 → MCP 서버**에서 켠 뒤, 에이전트 모드나 Code 작업에서 “Context7으로 라이브러리 문서를 찾아줘”라고 요청합니다. Code의 계획 모드에서는 MCP 서버를 실행하지 않습니다. 처음 연결할 때 npm에서 고정된 버전의 서버를 내려받습니다. API 키를 쓸 경우 `mcp.json`에서 같은 이름의 서버 설정으로 덮어쓸 수 있습니다. 이 파일의 키는 평문으로 저장됩니다. Local Only에서 외부 도구를 차단하면 Context7도 사용하지 않습니다.

#### 논문 읽기 (`paper`)

"이 논문 쉽게 설명해 줘: 1706.03762"처럼 arXiv 번호, DOI, 논문 URL, 작업 폴더의 PDF 경로, 또는 제목으로 요청합니다. 에이전트가 `paper-reading` 스킬에 따라 정보 → 목차 → 필요한 섹션 순서로 나눠 읽고 핵심 아이디어·방법·결과·용어 정리를 풀어 줍니다. 논문 검색과 PDF는 arXiv API(키 없음), 인용 수·한 줄 요약(TLDR)·arXiv 밖의 논문은 Semantic Scholar API를 씁니다. Semantic Scholar는 키 없이 쓸 수 있지만 요청이 몰리면 잠시 거절하므로, 자주 쓰면 무료 API 키를 받아 `SEMANTIC_SCHOLAR_API_KEY` 환경 변수로 넣으세요. 구독이 필요한 논문은 학교 도서관 등에서 PDF를 받아 작업 폴더에 넣으면 같은 방법으로 읽습니다. 스캔한 이미지 PDF는 글자를 읽지 못합니다.

#### Notion (`notion`)

1. https://www.notion.so/profile/integrations 에서 **새 통합**(내부)을 만들고 토큰(`ntn_...`)을 복사합니다.
2. 앱의 **설정 → Notion 통합 토큰**에 넣고 저장합니다(또는 `NOTION_TOKEN` 환경 변수).
3. Notion에서 다룰 페이지(또는 상위 페이지)의 오른쪽 위 **··· → 연결**에서 만든 통합을 추가합니다. 통합은 연결된 페이지와 그 하위 페이지만 볼 수 있습니다.

Notion에 쓰는 도구는 바깥 서비스를 바꾸므로 명령 실행처럼 승인을 받습니다.

#### 웹페이지 읽기 (`firecrawl`)

[Firecrawl](https://www.firecrawl.dev) API로 자바스크립트로 그리는 페이지까지 깔끔한 마크다운으로 읽습니다. firecrawl.dev에서 무료로 가입해 API 키(`fc-...`)를 받고 **설정 → Firecrawl API 키**에 넣으세요(또는 `FIRECRAWL_API_KEY` 환경 변수). 무료 요금제는 크레딧과 분당 요청 수(약 10회)에 한도가 있고, `crawl`은 쪽마다 크레딧을 씁니다. 직접 띄운 Firecrawl 서버는 `FIRECRAWL_API_URL`에 주소를 넣으면 씁니다.

**외부 서버**는 **MCP → 설정 파일 열기**로 `%APPDATA%\PostechChat\mcp.json`을 열어 Claude Desktop과 같은 형식으로 추가합니다. `npx`·`uvx` 같은 실행 도구가 필요한 서버는 그 도구가 PC에 설치되어 있어야 합니다. 내장 서버 이름(`word`, `powerpoint`, `excel`, `paper`, `notion`, `firecrawl`)은 쓸 수 없습니다. 추천 서버와 같은 이름(`playwright`)으로 적으면 적은 설정이 대신 쓰입니다.

```json
{
  "mcpServers": {
    "filesystem": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."] }
  }
}
```

작업 폴더의 파일만 고치는 내장 도구는 파일 수정처럼, 외부 서버의 도구와 바깥에 영향을 주는 내장 도구(Notion에 쓰기)는 명령 실행처럼 실행 전에 승인을 받습니다(논문 검색·읽기, Notion 읽기처럼 서버가 읽기 전용이라고 밝힌 도구는 제외). 텍스트 파일용 `write`·`edit`로는 Office·PDF·한글 문서를 쓸 수 없습니다.

#### 다른 AI 에이전트와 기억 이어 쓰기 (ai-memory)

[ai-memory](https://github.com/akitaonrails/ai-memory)를 PC에 설치하고(`ai-memory setup`) 외부 서버로 등록하면, Claude Code·Codex·Cursor·Gemini CLI 같은 코딩 에이전트와 같은 기억을 씁니다. 그 에이전트들도 같은 ai-memory 서버에 연결되어 있어야 합니다.

```json
{
  "mcpServers": {
    "ai-memory": { "command": "ai-memory", "args": ["mcp-bridge", "--no-session-id"] }
  }
}
```

에이전트 모드에서 작업 폴더가 있으면 앱이 다음을 자동으로 합니다.

- 대화에서 처음 에이전트를 실행할 때 그 작업 폴더에 남은 인계(다른 에이전트가 하던 일·남은 질문·다음 할 일)를 받고 최근 기억 페이지를 불러와, 그 대화 내내 참고 자료로 넣습니다. 인계는 한 번 받으면 사라지는 방식이라 다른 에이전트가 같은 인계를 다시 받지는 않습니다.
- 파일을 고치거나 명령·도구를 실행한 뒤에는 요청과 결과, 고친 파일 목록으로 인계를 남겨, 다음에 Claude Code 등을 같은 폴더에서 열면 이어받게 합니다. 같은 대화에서 다시 남기면 앞의 인계는 취소되어 대화마다 하나만 열려 있습니다.
- 모델이 부르는 ai-memory 도구에는 `workspace`·`project`를 앱이 채웁니다. 이름은 ai-memory 규칙대로 정합니다: 가장 가까운 `.ai-memory.toml`의 값 → git 원격(`upstream`, 없으면 `origin`)의 호스트를 뺀 경로(예: `bj0322-poschat`) → 원격이 없으면 폴더 이름.

ChatGPT·claude.ai 같은 웹 채팅 서비스의 기억은 ai-memory가 기록하지 않으므로 이어받을 수 없습니다. `.ai-memory.toml`의 홈 폴더 경로 규칙(`[routes]`)은 아직 지원하지 않으니, 필요하면 작업 폴더의 `.ai-memory.toml`에 `workspace`와 `project`를 적으세요.

### INIT.md

작업 폴더 최상위의 `INIT.md`는 모든 대화에 프로젝트 지침으로 들어갑니다(Claude Code의 CLAUDE.md와 같은 역할). `/init`을 입력하면 AI가 폴더를 살펴보고 INIT.md를 써 줍니다.

### 스킬

스킬은 `<스킬이름>/SKILL.md` 형식의 지침 파일입니다. 에이전트가 요청에 맞는 스킬을 스스로 불러오고, `/스킬이름 요청`으로 직접 실행할 수도 있습니다.

```markdown
---
name: meeting-notes
description: 회의 녹취를 회의록 형식으로 정리할 때 사용
---

# 회의록 스킬
## 절차
1. ...
```

스킬을 읽는 위치는 다음과 같습니다. 이름이 같으면 아래쪽이 우선합니다.

1. 앱 내장: `summarize`(문서 요약), `code-review`(코드 검토), `paper-reading`(논문을 나눠 읽고 쉽게 설명), `paper-compare`(논문 비교), `ponytail`(가장 작은 변경으로 문제 해결), `strategic-compact`(긴 작업의 맥락 요약), `rtk`(명령 출력 줄이기)
2. 사용자 공용: `%APPDATA%\PostechChat\skills\`. 앱의 **스킬 → 새 스킬 만들기**로 템플릿을 만들 수 있습니다.
3. 작업 폴더 전용: `<작업 폴더>\skills\`

`/ponytail 요청`으로 간결한 개발 지침을 불러옵니다. 기본은 `full`이며, `/ponytail lite`, `/ponytail ultra`로 수준을 바꾸고 `/ponytail off`로 현재 대화에서 끌 수 있습니다. 이 모드는 AI가 따르는 지침입니다.

`rtk` 스킬은 별도로 설치한 [RTK OSS](https://github.com/rtk-ai/rtk)를 명시적으로 호출해 지원되는 명령의 출력을 줄입니다. macOS는 `brew install rtk-ai/tap/rtk-oss`, Windows는 [릴리스](https://github.com/rtk-ai/rtk/releases)에서 `rtk-oss-x86_64-pc-windows-msvc.zip`을 받아 풀고 `rtk.exe`를 PATH에 추가하세요. 설치 뒤 `rtk --version`, `rtk gain`을 확인하고 앱을 다시 시작하세요. Code 작업에서는 “RTK로 Git 상태를 확인해 줘”처럼 요청할 수 있습니다. 원격 작업은 원격 컴퓨터에도 설치해야 합니다. 명령은 기존 승인 절차를 따르며, RTK의 출력은 일부 생략될 수 있으므로 필요하면 원래 명령으로 다시 확인합니다. RTK 실행 파일은 앱에 포함되지 않고 자동으로 설치되지 않습니다.

### 여러 세션 동시에 실행하기

- 채팅은 **새 대화**를 열어 다른 요청을 보낼 수 있습니다. 실행 중인 대화는 목록에 표시되며, 중지는 현재 대화에만 적용됩니다.
- Code의 **새 세션**(또는 `/new`)으로 다른 작업을 시작합니다. 위쪽 작업 선택 목록이나 `/resume`으로 실행 중인 작업과 지난 작업을 오갑니다. 추가 지시·중지·권한 모드 변경은 선택한 작업에만 적용됩니다.
- 같은 파일을 여러 작업에서 고치려면 `/worktree 할 일`로 격리 작업 공간을 쓰는 편이 좋습니다. 일반 작업은 같은 디스크 파일을 공유합니다.
- 실행 유지는 앱이 켜져 있는 동안입니다. 앱을 종료하면 작업을 멈추며, 저장된 대화와 작업 기록은 다음 실행에서 이어 볼 수 있습니다. 브라우저 화면은 하나이므로 브라우저 조작은 한 채팅 세션이 맡습니다.


## 동작 방식과 한계

POSTECH GenAI 서버의 모델은 자체 시스템 프롬프트 때문에 "사용자 PC에 접근하라"는 형식의 도구 호출을 거부합니다. 그래서 이 앱은 "진행 기록을 보고 다음 단계를 JSON으로 고르는 작업"으로 요청합니다. 모델이 그래도 형식을 거부하고 사용자에게 할 일을 안내하면, 앱이 그 안내문을 다음 단계로 바꾸거나 언급된 파일을 직접 읽어 진행을 이어 갑니다.

- 에이전트는 단계마다 API를 한 번씩 호출하므로, 여러 단계짜리 작업은 1~2분 걸릴 수 있습니다. 스트리밍은 일반 대화의 답변에만 적용됩니다.
- 모델이 가끔 같은 파일을 여러 번 읽는 등 불필요한 단계를 거칠 수 있습니다. 최대 단계 수는 설정에서 바꿉니다.
- 오류가 나면 `%APPDATA%\PostechChat\error.log`를 확인하세요.

## 개발

| 파일 | 역할 |
|---|---|
| `main.py` | pywebview 창과 JS↔Python 브리지 |
| `agent.py` | INIT.md·스킬 로딩, 에이전트 단계 루프와 도구 |
| `documents.py` | PDF·Word·PowerPoint·Excel·한글 문서의 텍스트 추출 |
| `mcp_client.py` | MCP 클라이언트: 서버 실행·연결·도구 호출, `mcp.json` 읽기 |
| `ai_memory.py` | ai-memory 연동: 작업 폴더의 workspace·project 결정, 인계 받기·남기기 |
| `office_mcp.py` | 내장 MCP 서버(word·powerpoint·excel)와 모든 내장 서버의 공통 실행 루프. 앱 exe를 `--mcp-server <이름>`으로 실행하면 이 서버가 됩니다. |
| `paper_mcp.py` · `notion_mcp.py` · `firecrawl_mcp.py` | 내장 MCP 서버 paper(arXiv·Semantic Scholar), notion(Notion API), firecrawl(Firecrawl API) |
| `api.py` | POSTECH GenAI API 호출(OpenAI 호환 Chat Completions / OpenAI Responses / a1), 스트리밍 해석, 이미지·음성 입력, 사용량·크레딧 기록 |
| `po_note.py` | PO노트 저장(전사·노트·메모·강의 자료)과 필기 노트 프롬프트·생성(긴 전사는 나눠 정리 후 합치기) |
| `updates.py` | 자동 업데이트: 업데이트 서버 확인, 이 기기용 설치 파일 내려받기(크기·SHA-256·Ed25519 서명 확인) |
| `stt.py` | PO노트 음성 인식: 마이크(sounddevice) → 음성 구간 검출(Silero VAD) → 로컬 AI(sherpa-onnx) 또는 POSTECH 서버, 모델 내려받기 |
| `attachments.py` | 채팅창 첨부 파일: 조각 업로드, 종류 확인, 문서·텍스트 내용 뽑기, 이미지 |
| `storage.py` | 대화·설정 저장(`%APPDATA%\PostechChat`), memory.md·USER.md, 첨부 파일 폴더, 모델 API 사용량, 다른 대화 검색 |
| `web/` | 화면(HTML/CSS/JS, marked·DOMPurify·KaTeX 포함). PO노트 화면은 `web/po.js` |
| `tests/` | 단위 테스트(`python -m unittest discover -s tests`) |
| `.github/workflows/build.yml` | 단위 테스트, Windows·macOS·Android 빌드와 플랫폼별 자가 진단, 태그 push 때 Release에 첨부 |
| `android/` | 안드로이드 앱(Kotlin WebView + Chaquopy). 빌드할 때 저장소 최상위의 Python 모듈·`web/`·`skills/`를 복사해 넣고, `android_main.py`가 pywebview 대신 화면과 Python을 연결합니다. |
| `certs.py` | 중간 인증서를 보내지 않는 서버를 위해 AIA로 중간 인증서를 받아 검증(Windows는 운영체제가 처리) |
| `installer/installer.py` | 설치 프로그램(`--silent --dir=<경로> --no-desktop` 지원) |
| `assets/` | 앱 아이콘 |
| `build_installer.py` | 앱과 설치 프로그램 빌드 |

- 소스로 실행: `run.bat`
- 진단: `PostechChat.exe --selftest`를 실행하면 API 연결, 문서 라이브러리, 내장 MCP 서버 연결 결과가 `%APPDATA%\PostechChat\selftest.txt`에 기록됩니다. 제거 명령은 `PostechChat.exe --uninstall`입니다.
- 설치 파일 빌드: `build.bat`, 또는 `python build_installer.py`. 결과는 `release\POSCHAT-Setup.exe`입니다.
  - **python.org 공식 Python(3.11 이상, tcl/tk 포함)으로 빌드하세요.** Anaconda Python으로 빌드한 exe는 HTTPS 요청 때 `OPENSSL_Uplink: no OPENSSL_Applink` 오류로 꺼집니다. 빌드 스크립트가 이 경우를 미리 막습니다.
- 앱의 HTTPS 요청은 `truststore`를 통해 운영체제 인증서 저장소를 사용합니다. 인증서 오류가 발생하면 Windows 인증서와 네트워크 설정을 확인하세요. TLS 검증을 비활성화하지 마세요.


## 소스 설치와 개발 환경

Windows와 Python 3.11 이상(ai_memory.py가 표준 라이브러리 tomllib을 씀)을 기준으로 합니다. 데스크톱 화면에는 Microsoft Edge WebView2 런타임이 필요합니다. 프로젝트 폴더에서 다음 명령을 실행하세요.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

첫 실행의 설정 창에서 본인의 POSTECH GenAI API 키를 입력합니다. 또는 실행할 프로세스에 `POSTECH_GENAI_API_KEY` 환경 변수를 설정할 수 있습니다. 설정에 저장한 키가 환경 변수보다 우선합니다. `.env` 파일을 자동으로 읽는 기능은 없습니다. 프런트엔드는 정적 HTML/CSS/JavaScript이므로 npm 설치나 별도 웹 서버가 필요하지 않습니다.

개발 중 브리지 디버깅은 `POSTECH_CHAT_DEBUG=1` 환경 변수를 설정해 켤 수 있습니다. `run.bat`은 사용 가능한 Python을 찾아 의존성을 설치하고 실행하는 편의 스크립트이며, 위의 가상환경 직접 실행 방법은 사용할 Python을 명확하게 고정합니다.

설치 프로그램은 python.org Python(tcl/tk 포함)에서 다음과 같이 빌드합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build_installer.py
```

빌드는 `%TEMP%\PostechChat-build`를 사용하며 결과는 `release\POSCHAT-Setup.exe`입니다. 빌드 결과는 Git에 포함하지 않습니다.

## 배포

안드로이드 APK는 `android/`에서 `./gradlew assembleRelease`(JDK 17, Android SDK, Python 3.11 필요)로 빌드합니다. 결과는 `android/app/build/outputs/apk/release/app-release.apk`입니다. 모든 빌드는 저장소의 공용 키(`android/app/poschat-shared.keystore`)로 서명해 덮어 설치가 되게 합니다. 공개 스토어에 올릴 때는 따로 보관한 키로 바꾸세요.

설치 파일은 GitHub Releases에 올립니다. `.github/workflows/build.yml`이 Windows·macOS·Android 빌드와 플랫폼별 검증을 자동으로 수행합니다.

- PR을 올리거나 Actions에서 **Build installer**를 수동 실행하면, 빌드한 `POSCHAT-Setup.exe`를 실행 결과의 Artifacts에서 받을 수 있습니다.
- 버전 태그를 push하면 같은 빌드가 그 태그의 Release에 첨부됩니다. 단위 테스트가 실패하면 Release를 만들지 않습니다.

  ```powershell
  git tag v1.2.0
  git push origin v1.2.0
  ```

  태그를 직접 push하지 않고 Actions에서 **Build installer → Run workflow**의 `release` 칸에 `v1.2.0`을 넣어 실행해도 됩니다. 이 경우 실행한 커밋에 태그와 Release가 만들어집니다.
- 사용자에게는 항상 최신 버전을 가리키는 업데이트 서버 링크 `https://pidstech.com/releases/download/latest/POSCHAT-Setup.exe`(맥은 `POSCHAT-mac.dmg`, 안드로이드는 `POSCHAT.apk`)를 안내하면 됩니다. 저장소가 비공개여도 받을 수 있습니다. 서버가 GitHub 릴리스를 10분마다 가져옵니다([운영 안내](docs/update-server.md)).
- **자동 업데이트**(1.9.1부터): 앱이 시작할 때(6시간에 한 번) 업데이트 서버(`updates.UPDATE_BASE_URL`)의 `/api/releases/latest`로 최신 정식 릴리스를 확인합니다. 1.18.1 이하 앱은 GitHub를 확인하므로, 저장소를 비공개로 바꾸기 전에 1.18.2를 공개 저장소에서 릴리스해 한 번 받게 합니다. 새 버전이 있으면 릴리스 노트와 함께 알리고, **업데이트**를 누르면 이 기기용 파일(`POSCHAT-Setup.exe`·`POSCHAT-mac.dmg`·`POSCHAT.apk`, 1.11부터의 이름. 릴리스에는 1.9.1~1.10.0 앱을 위해 예전 이름 `PostechChat-*`도 함께 올립니다)을 받아 서버가 알려 준 크기·SHA-256(digest)과, 릴리스 CI가 만든 Ed25519 서명(`<파일>.sig`)을 앱에 들어 있는 공개키로 확인합니다. 서버 주소가 http이므로 서명이 없거나 맞지 않으면 설치하지 않습니다([보안](docs/security.md#업데이트-신뢰-모델)).
  - Windows: 설치 프로그램을 지금 설치 폴더로 열고 앱이 스스로 닫힙니다. 설치 프로그램에서 **설치**를 누르면 앱이 완전히 닫히기를 기다렸다가(1.11부터, 한 번만 누르면 됨) 대화·설정을 유지한 채 바뀝니다. 30초가 지나도 닫히지 않으면 강제로 종료할지 묻습니다.
  - macOS: 디스크 이미지를 엽니다. 앱을 끝낸 뒤 응용 프로그램 폴더로 끌어다 놓아 바꿉니다.
  - Android: 설치 화면을 엽니다(처음 한 번 "이 출처 허용"이 필요합니다).
  - 업데이트 서버가 응답하지 않으면 확인하지 못했다고만 알리고(시작할 때는 알리지 않음) 사용에는 지장이 없습니다.
  - **설정 → 업데이트**에서 시작할 때 확인을 끄거나 지금 확인할 수 있고, 알림 창에서 **이 버전 건너뛰기**를 고를 수 있습니다.

- 설치 파일에는 코드 서명이 없어서 처음 실행할 때 Windows SmartScreen 경고가 뜰 수 있습니다. 경고는 코드 서명 인증서로 서명해야만 없앨 수 있습니다. 인증서(.pfx)를 base64로 바꿔 저장소 Secrets의 `WINDOWS_SIGN_PFX_BASE64`에, 비밀번호를 `WINDOWS_SIGN_PASSWORD`에 넣으면 빌드가 앱 exe와 설치 파일에 서명합니다(로컬 빌드는 `WINDOWS_SIGN_PFX`·`WINDOWS_SIGN_PASSWORD` 환경 변수). 서명한 파일도 다운로드가 쌓여 평판이 생길 때까지는 경고가 남을 수 있습니다.

## v1.1.0 아키텍처

1. `web/app.js`가 `window.pywebview.api`를 통해 `main.py`의 `Bridge`를 호출합니다. `/remember`, `/memory`, `/help`는 화면에서 처리합니다.
2. `Bridge`는 대화와 설정을 관리하고 백그라운드 스레드에서 `Agent`를 실행합니다. 진행 상황·도구 결과·승인 요청은 `window.onBackendEvent`로 화면에 전달합니다.
3. `agent.py`는 공통 메모리, 관련 대화, 최근 메시지와 INIT.md·스킬을 조합합니다. 일반 대화는 한 번의 답변 요청으로, 에이전트는 JSON 단계 선택과 로컬 도구 실행의 반복으로 처리합니다.
4. `api.py`는 POSTECH GenAI 엔드포인트를 지원합니다. a1은 `X-Api-Key`, Responses는 `x-api-key`, OpenAI 호환 Chat Completions는 Bearer 토큰으로 인증합니다. 일반 대화는 스트리밍으로 받아 `delta` 이벤트로 화면에 보냅니다. TLS 검증에는 `truststore`를 통해 운영체제 인증서 저장소를 사용합니다.
5. `storage.py`는 JSON 파일을 임시 파일에 쓴 뒤 교체합니다. 다른 대화 검색은 한국어·영문·숫자의 문자 bigram 겹침을 사용하며 벡터 DB나 임베딩 서버를 사용하지 않습니다.

자동 대화 참고는 기본 활성화되며 메모리 창에서 끌 수 있습니다. 현재 구현에서 이 설정은 자동 참고를 제어하며, 에이전트의 명시적 `recall` 검색은 별도로 실행될 수 있습니다. 기본 에이전트 단계 한도는 25, 대화 이력은 20개 메시지이고 설정에서 바꿀 수 있습니다.

## 데이터와 저장소 관리

- API 키를 설정 창에 입력하면 `%APPDATA%\PostechChat\config.json`에 평문으로 저장됩니다. 공용 PC에서는 환경 변수를 사용하는 등 보관 방식을 신중히 선택하세요.
- 대화·공통 메모리·사용자 정보(USER.md)·첨부 파일 내용·관련 대화 발췌·읽은 파일 및 명령 출력은 답변 생성에 필요할 때 POSTECH GenAI API로 전달됩니다.
- 사용자 대화, 메모리, 설정, 로그, 개인 API 키는 소스 저장소에 포함하지 않습니다. `.gitignore`는 이 파일들과 가상환경·캐시·빌드 결과·실행 파일을 제외합니다.
- 앱 소스, 설치 프로그램 소스, 실행·빌드 스크립트, 기본 스킬 3종, 아이콘, 정적 UI와 번들 JavaScript 라이브러리를 포함합니다. `web/vendor/` 파일은 UI 실행에 필요한 배포 의존성이므로 포함하며, 원본 저작권·라이선스 주석을 유지합니다.
- 이 저장소는 v1.1.0 소스 스냅샷을 시작점으로 합니다. 이전 버전의 코드·변경 이력은 가져오지 않습니다.

## 버전 기록

- 1.18.9 — **공개 배포 전 보안 보강**: '다시 묻지 않기' 규칙의 `&` 우회 차단, 채팅 답변의 외부 이미지·위험 링크 차단, 텍스트 첨부는 앱 안에서 보기, 채팅 명령의 비밀 환경 변수 제거·위험 명령 매번 확인, API 키를 OS 보안 저장소로, 업데이트 내려받기 대체 경로, 릴리스 태그 점검. [릴리스 노트](docs/release-notes/v1.18.9.md)
- 1.18.8 — **PLMS 베타 표시·토큰 효율**: PLMS를 베타로 표시하고 사이드바 맨 아래로 옮김. 에이전트 프롬프트 줄이기, 프롬프트 캐싱 기본 켜짐, 대화 검색 색인. [릴리스 노트](docs/release-notes/v1.18.8.md)

## 라이선스 (License)

Copyright © 2026 Beomjoon Kim (bj0322)

POSCHAT의 새 공식 배포본은 **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**를 따릅니다. 전문은 [LICENSE](LICENSE), 전환 이력은 [LICENSE_HISTORY.md](LICENSE_HISTORY.md)에 있습니다. "or later"(이후 버전 선택)는 적용하지 않습니다.

1. **적용 범위**: v1.10.0부터의 공식 배포본과, 전환 커밋 `3edf859` 이후의 이 저장소 코드에 AGPL-3.0-only가 적용됩니다.
2. **할 수 있는 것**: AGPL 조건에 따라 누구나 사용·연구·수정·재배포할 수 있습니다.
3. **소스 제공 의무**: 수정한 버전을 배포하거나, 수정한 버전을 네트워크로 다른 사람이 이용하게 하는 경우 등 AGPL이 요구하는 경우에는 그 버전의 해당 소스코드(Corresponding Source)를 AGPL로 제공해야 합니다.
4. **상업적 이용**: AGPL은 판매·유료 제공 같은 상업적 이용 자체를 금지하지 않습니다. 이 프로젝트는 AGPL 원문 외의 추가 금지 조항을 두지 않습니다.
5. **과거 MIT 배포본**: v1.2.0~v1.9.2(태그)와 전환 커밋 이전의 코드는 MIT License로 배포되었고, 그 버전을 받은 사람의 MIT 권리는 그대로 유지됩니다(철회하지 않습니다).
6. **POSTECH GenAI API는 별개**: 이 소프트웨어 라이선스는 POSTECH GenAI API 이용 권한이나 POSTECH 명칭·상표 사용권을 주지 않습니다. API는 본인에게 발급된 키와 서비스 제공자의 이용 조건을 따릅니다.
7. **제3자 구성 요소**: 번들 라이브러리와 설치 파일에 들어가는 패키지, 실행 중에 내려받는 모델·도구는 각자의 라이선스를 따릅니다.

앱의 **설정** 맨 아래에서 라이선스 전문(**라이선스 보기**), 설치한 버전과 같은 태그의 소스코드(**소스 코드 보기**), 제3자 라이선스를 볼 수 있습니다. 각 Release 본문에도 그 바이너리에 대응하는 소스(같은 태그)를 적습니다. 의존성별 호환성 검토는 [docs/license-audit.md](docs/license-audit.md)에 있습니다.

번들 라이브러리의 버전, 출처, 라이선스는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 정리했습니다. 원문은 `licenses/`에 보관하며, 제3자 파일은 각 원본 라이선스를 따릅니다.
