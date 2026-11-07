# POSCHAT 개인정보 처리방침

시행일: 2026년 10월 26일 · 적용 대상: POSCHAT 데스크톱 앱(Windows·macOS)과 안드로이드 앱(Microsoft Store판 포함)

POSCHAT은 PIDS Tech. 팀이 만들고 관리하는 비공식 프로젝트입니다(포항공과대학교(POSTECH)의 공식 제품이 아닙니다).
이 문서는 앱이 어떤 정보를 어디에 저장하고, 어디로 보내는지 설명합니다.

## 1. 요약
- **우리(개발자)는 사용자의 대화·파일·계정 정보를 받거나 모으지 않습니다.** 개발자가 운영하는 서버는 새 버전을 알려 주고 설치 파일을 나눠 주는 업데이트 서버 하나뿐이며, 앱은 그 서버에 대화·파일·계정 정보를 보내지 않습니다.
- 사용자가 보낸 질문과 첨부는 **사용자가 고른 AI 모델 서비스**로 바로 전송됩니다.
- 대화·설정·기록은 **사용자의 기기**에 저장되고, API 키·토큰은 운영체제의 보안 저장소에 둡니다.
- 연결(커넥터)·동기화·외부 전송 기능은 **사용자가 켰을 때만** 동작합니다.

## 2. 기기에 저장하는 정보
| 무엇 | 어디 |
|---|---|
| 대화 내용, 첨부한 파일의 사본, 메모리, PO노트(녹음·받아쓰기), 연구 라이브러리, Lab 실험 기록, Code 에이전트 작업 기록 | 앱 데이터 폴더(Windows `%APPDATA%\PostechChat`, macOS `~/Library/Application Support/PostechChat`) |
| API 키, 커넥터 토큰(GitHub·Google·Notion 등) | 운영체제 보안 저장소(Windows 자격 증명 관리자, macOS 키체인). 쓸 수 없을 때만 데이터 폴더의 권한 제한 파일 |
| 관측 기록(모델 이름, 걸린 시간, 토큰 수, 성공 여부) | 데이터 폴더의 `telemetry/events.jsonl`, 90일 보관. 질문·답변 내용은 남기지 않습니다 |

앱을 지워도 데이터 폴더는 남습니다. 지우려면 데이터 폴더를 직접 지우세요.

## 3. 외부로 보내는 정보

### 사용자가 요청할 때(기본 기능)
| 받는 곳 | 보내는 것 | 언제 |
|---|---|---|
| 사용자가 고른 AI 모델 서비스: POSTECH GenAI API(기본), Anthropic Claude API, 사용자가 넣은 호환 API 주소 | 질문, 대화 맥락, 첨부한 파일·코드의 내용, 에이전트가 읽은 파일의 일부 | 질문을 보내거나 에이전트에게 일을 맡길 때 |
| 로컬 AI(Ollama, 이 기기 안) | 위와 같음 | 'AI 실행 정책'에서 로컬 모델을 쓸 때. 기기 밖으로 나가지 않습니다 |
| 업데이트 서버(PIDS Tech.가 운영) | 일반적인 HTTP 정보(IP 주소·시각·`POSCHAT` 이름표). 앱 버전·사용자 정보는 보내지 않습니다 | 새 버전 확인(설정에서 끌 수 있음)과 설치 파일 받기. Microsoft Store판은 확인만 하고 내려받지 않습니다 |
| GitHub(`raw.githubusercontent.com`), 받지 못하면 업데이트 서버 | 일반적인 HTTP 정보(IP 주소·시각·`POSCHAT` 이름표) | 하루에 한 번 모델 목록(공개 저장소의 `models.json`) 받기(설정 → 업데이트에서 끌 수 있음). 받기만 하고 아무것도 보내지 않습니다 |
| Hugging Face(`huggingface.co`) | 일반적인 HTTP 정보 | PO노트의 음성 인식 모델을 처음 받을 때. 음성은 이 기기 안에서만 처리합니다 |
| arXiv·Semantic Scholar·Crossref·OpenAlex | 사용자가 찾는 논문 검색어·식별자 | 논문 열기·찾기를 쓸 때 |
| 사용자가 연 웹사이트 | 일반적인 웹 브라우징 정보 | 앱 안의 브라우저로 사이트를 열 때 |

각 서비스는 받은 정보를 그 서비스의 정책에 따라 처리합니다(예: Anthropic, POSTECH GenAI). 모델 서비스에 보내기 싫은 내용은 보내지 마세요.
'AI 실행 정책'의 Local Only를 켜면 모델 호출이 이 기기의 로컬 AI로만 갑니다.

### 사용자가 켰을 때만(선택 기능)
| 기능 | 받는 곳 | 보내는 것 |
|---|---|---|
| GitHub 커넥터 | GitHub | 저장소·이슈·PR 조회와 사용자가 승인한 쓰기 |
| Google Drive·Docs·Sheets·Slides·Gmail·Calendar 커넥터 | Google | 사용자가 요청한 파일·메일·일정 조회와 승인한 쓰기·전송 |
| Google Drive 동기화 | Google Drive의 앱 전용 숨김 폴더 | 기기 사이에 맞출 데이터(암호화) |
| Notion·Firecrawl·Zotero 커넥터 | 각 서비스 | 사용자가 요청한 조회·쓰기 |
| Langfuse 내보내기(기본 꺼짐) | 사용자가 넣은 Langfuse 주소 | 관측 메타데이터. '내용 포함'을 따로 켜면 질문·답변 앞부분(비밀·이메일은 가림) |
| 외부 MCP 서버 | 사용자가 추가한 서버 | 그 서버의 도구에 넘긴 인자 |
| 부적절한 응답 신고 | GitHub 이슈(공개) | 사용자가 고르고 확인한 내용만. 앱이 따로 보내지 않고 브라우저에서 사용자가 직접 올립니다 |

전송·삭제·외부 쓰기처럼 되돌리기 어려운 동작은 실행 전에 승인을 받습니다.

## 4. 마이크·파일·명령
- **마이크**는 PO노트에서 녹음을 시작할 때만 씁니다. 음성 인식은 기기 안에서 하고, 녹음은 데이터 폴더에 저장합니다.
- **파일**은 사용자가 고른 작업 폴더와 첨부한 파일만 읽습니다.
- **명령 실행**(Code·Lab·에이전트)은 사용자가 승인하거나 권한 모드에서 허용한 것만 실행하며, API 키 같은 비밀 환경 변수는 넘기지 않습니다.

## 5. 아동
POSCHAT은 만 14세 미만 아동을 대상으로 하지 않으며, 아동의 정보를 일부러 모으지 않습니다.

## 6. 바뀔 때
이 문서를 바꾸면 이 페이지에 새 시행일과 함께 올리고, 바뀐 내용은 [변경 기록](https://github.com/pidstech/POSCHAT/commits/main/docs/privacy-policy.md)에서 볼 수 있습니다.

## 7. 문의
- 개발: PIDS Tech. 팀 · 서비스 대표자: 김범준
- 메일: [beomjoon@pidstech.com](mailto:beomjoon@pidstech.com)
- 소스 코드(AGPL-3.0-only): https://github.com/pidstech/POSCHAT

---

## Privacy Policy (English summary)
POSCHAT is an unofficial project by the PIDS Tech. team; it is not an official product of POSTECH. **The only server the developer runs is the update server (new-version check and installer download); the app sends it no chats, files, or account data, and the developer does not collect any.**
Your prompts and attachments are sent directly to the AI model service you choose (POSTECH GenAI API by default, Anthropic Claude API, a compatible endpoint you enter, or a local Ollama model that stays on your device).
Chats, settings, and logs stay on your device; API keys and tokens are kept in the operating system's secure storage.
The app contacts the update server to check for new versions (can be turned off; the Microsoft Store edition only checks; the server sees only your IP address and a generic HTTP request), GitHub (or the update server) once a day to download the public model list `models.json` (can be turned off; nothing is sent), Hugging Face to download the on-device speech model once, and paper services (arXiv, Semantic Scholar, Crossref, OpenAlex) when you search papers.
Connectors (GitHub, Google, Notion, Firecrawl, Zotero), Google Drive sync (encrypted), Langfuse export (off by default), external MCP servers, and content reports (public GitHub issues you submit yourself in the browser) work only when you enable or use them.
The microphone is used only while recording in PO Note, and speech recognition runs on the device. Contact: beomjoon@pidstech.com.
