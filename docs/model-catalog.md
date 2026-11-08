# 모델 목록 자동 동기화(2.3)

제공 모델이 바뀌어도(새 모델 추가, 이름 변경, 서비스 종료) 앱을 새로 내지 않고 설치된 앱의 모델 목록을 맞추는 방법입니다.

## 구조
```
api.py 기본 목록(MODELS·ANTHROPIC_MODELS·OPENAI_MODELS·MODEL_ALIASES)
   └─ tools/model_catalog.py write ─ models.json(저장소 루트, main 브랜치)
        └─ 앱: 시작할 때 하루 한 번 받음(raw.githubusercontent.com → 실패하면 pidstech.com/api/models.json)
             └─ 설정에 저장(model_catalog) → 모델 선택 목록·기본 모델·옛 ID 옮기기에 씀
매주 월요일 GitHub Actions(Model list check) ─ 제공자 API에 실제 목록을 물어 비교 ─ 사라진 모델이 있으면 'model-catalog' 이슈
```

### 방식별로 목록을 정하는 순서
| API 방식 | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| POSTECH GenAI(OpenAI 호환) | 사용자가 '모델 목록 불러오기'로 받은 서버 목록 | 모델 카탈로그 `chat_completions` | 앱에 들어 있는 `MODELS` |
| 개인 Claude API | 받은 목록(`anthropic_server_models`) | 카탈로그 `anthropic` | `ANTHROPIC_MODELS` |
| 개인 GPT API | 받은 목록(`openai_server_models`) | 카탈로그 `openai` | `OPENAI_MODELS` |
| Responses API | — | — | `RESPONSES_MODELS`(카탈로그 대상 아님) |

- POSTECH 게이트웨이는 `GET .../models`가 404라 앱이 직접 목록을 알 수 없습니다. 그래서 게이트웨이 모델은 카탈로그로만 바꿀 수 있습니다.
- '모델 목록 불러오기'로 한 번 받아 둔 방식은 하루에 한 번 같은 키로 다시 받아 바뀐 내용(새 모델·없어진 모델)을 반영합니다.
- 대화나 설정의 모델이 목록에서 사라지면 열 때 그 방식의 기본 모델(목록의 첫 모델)로 바뀝니다. 이름만 바뀐 모델은 `aliases`로 새 ID로 옮깁니다.
- 설정 → 업데이트의 '모델 목록 자동 업데이트'로 끌 수 있고, '모델 목록 확인'으로 바로 받을 수 있습니다. 네트워크가 안 되면 지금 목록을 그대로 씁니다.

## 모델이 바뀌었을 때 할 일
1. `api.py`의 목록을 고칩니다. 첫 줄이 그 방식의 기본(권장) 모델입니다. 이름이 바뀐 모델은 `MODEL_ALIASES`에 `"옛 ID": "새 ID"`를 넣습니다.
2. `python tools/model_catalog.py write`로 `models.json`을 다시 만듭니다(내용이 바뀌면 `updated` 날짜도 바뀝니다).
3. main에 병합합니다. 설치된 앱은 다음 시작 때(하루 간격) 새 목록을 받습니다. 앱 릴리스는 필요 없습니다.

`models.json`이 `api.py`와 다르면 단위 시험(`tests/test_model_catalog.py`)과 주간 점검이 실패합니다.

## 주간 점검(.github/workflows/models.yml)
- 저장소 Secrets에 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `POSTECH_GENAI_API_KEY`를 넣으면 그 제공자를 점검합니다(없는 것은 건너뜀). 키는 목록 조회(`GET /models`)에만 쓰며 크레딧을 쓰지 않습니다.
- 카탈로그 모델이 제공자 목록에서 사라졌으면 `model-catalog` 이슈를 열거나 열린 이슈에 보고서를 덧붙입니다. 새 모델만 보이면 실행 요약에만 남깁니다.
- 직접 실행: Actions → Model list check → Run workflow. 로컬: `ANTHROPIC_API_KEY=... python tools/model_catalog.py probe`.
- 자동으로 목록을 고치지는 않습니다. 권장 모델·이름·가격 판단은 사람이 합니다.

## 안전
- 카탈로그는 모델 ID·이름·별칭만 담습니다. API 주소·키·다른 설정은 바꾸지 못합니다.
- ID는 `[A-Za-z0-9._:/@-]` 100자 이하, 이름은 80자 이하, 방식별 100개·별칭 200개·파일 64KB 이하입니다. 하나라도 어기거나 `schema`가 1이 아니면 통째로 버립니다.
- 받는 곳은 공개 저장소(main)와 업데이트 서버뿐이고 리디렉션은 따라가지 않습니다. main에 쓸 수 있는 사람만 목록을 바꿀 수 있습니다.
