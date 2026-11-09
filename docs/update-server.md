# 업데이트 서버 운영

1.18.8부터 앱은 공개 저장소 `pidstech/POSCHAT`의 GitHub 릴리스를 먼저 보고, GitHub에서 받지 못할 때만 이 서버(`updates.UPDATE_BASE_URL` = `https://pidstech.com`)를 씁니다. 1.18.7 이하 앱은 이 서버만 보므로 서버는 계속 필요합니다. 앱 쪽은 `updates.py`, 서명은 [security.md](security.md#업데이트-신뢰-모델).

**저장소가 공개이므로 서버의 동기화 대상은 `pidstech/POSCHAT`이어야 합니다**(저장소를 옮기거나 다시 만들었다면 `poschat-sync.py`의 저장소 이름을 확인). 공개 저장소는 토큰 없이 가져올 수 있습니다.

## 구조
```
GitHub 릴리스(CI가 서명 파일 .sig까지 올림)
   └─ 서버의 poschat-update-sync.timer(10분마다) ─ /opt/poschat-update/poschat-sync.py
        └─ publish.py → /var/www/updates/{api/releases/latest, releases/download/<태그>/…}
             └─ nginx(80·443)가 그대로 줌 ─ 앱: GET /api/releases/latest, /releases/download/<태그>/<파일>(.sig)
```
- 피드가 둘입니다. 앱은 피드의 다운로드 주소가 자기 서버 주소로 시작할 때만 받아들이므로, `https://pidstech.com`은 `api/latest-domain.json`(주소가 도메인), 옛 `http://3.38.118.65`는 `api/latest.json`(주소가 IP, 1.18.2 앱용)을 줍니다. 동기화 스크립트가 같은 내용으로 둘을 만듭니다.
- 피드는 GitHub `releases/latest`와 같은 모양의 JSON(`tag_name`·`name`·`body`·`assets[name,size,digest,browser_download_url]`)입니다.
- 서버에는 서명 개인키가 없습니다. 동기화 스크립트는 파일마다 GitHub가 알려 주는 크기·SHA-256을 확인하고, 앱이 서명을 다시 확인합니다.
- 최신 버전은 `/releases/download/latest/<파일>` 링크로도 받을 수 있습니다. 서버에는 최근 2개 버전만 둡니다.
- 다운로드 페이지(`/poschat/`, 저장소 밖)는 이 링크를 씁니다. Windows(`POSCHAT-Setup.exe`)·macOS(`POSCHAT-mac.dmg`)에 더해 2.2부터 Linux(`POSCHAT-linux-x86_64.AppImage`) 버튼도 있어야 합니다.
- 서버의 스크립트(저장소 밖): `/opt/poschat-update/poschat-sync.py`, `publish.py`, systemd 유닛 `poschat-update-sync.{service,timer}`.

## 모델 카탈로그(2.3)
앱은 하루에 한 번 `https://raw.githubusercontent.com/pidstech/POSCHAT/main/models.json`을 받고, 받지 못하면 이 서버의 `/api/models.json`을 봅니다([model-catalog.md](model-catalog.md)). GitHub가 막힌 망을 위해 동기화 스크립트가 같은 파일을 `/var/www/updates/api/models.json`으로 복사하도록 넣어 두세요(저장소 밖 작업, 크기 64KB 이하, `Content-Type: application/json`). 없으면(404) 앱은 GitHub에서 받은 것이나 앱에 들어 있는 목록을 그대로 씁니다.

## 저장소를 다시 비공개로 바꿀 때(지금은 공개)
GitHub가 비공개이면 서버가 릴리스를 가져오려면 읽기 전용 토큰이 필요합니다.
1. GitHub → Settings → Developer settings → Fine-grained tokens: 저장소 `pidstech/POSCHAT`만, 권한은 **Contents: Read-only**(Metadata는 자동).
2. 서버에서 `/etc/poschat-update.env`(소유 root:pidsdeploy, 권한 0640)에 `GITHUB_TOKEN=<토큰>` 한 줄을 넣습니다.
3. `sudo systemctl start poschat-update-sync.service`, `journalctl -u poschat-update-sync.service`로 확인합니다.
토큰은 GitHub로 가는 요청에만 쓰고, 저장소 밖 서명 URL로 리디렉션될 때는 보내지 않습니다.

## HTTPS
- Let's Encrypt 인증서(`/etc/letsencrypt/live/pidstech.com`, `certbot-renew.timer`로 자동 갱신, 만료 알림 메일 없음). nginx 설정은 `/etc/nginx/conf.d/pids-tls.conf`(도메인)와 `pids.conf`(IP·기본 서버).
- 인증서 점검: `sudo certbot certificates`

## 점검
- 피드: `curl https://pidstech.com/api/releases/latest`(도메인), `curl http://3.38.118.65/api/releases/latest`(IP, 1.18.2 앱용)
- 마지막 동기화: `journalctl -u poschat-update-sync.service -n 20`, 다음 실행: `systemctl list-timers poschat-update-sync.timer`
- 지금 바로 동기화: `sudo systemctl start poschat-update-sync.service`
- 다운로드 페이지와 피드가 GitHub 최신 릴리스와 같은지: 태그·파일 이름·크기·digest 비교, `/poschat/`의 받기 링크(Windows·macOS·Linux)와 `/api/models.json`(200, JSON)
- 디스크: `df -h /var/www` (릴리스 하나가 약 300MB, 동기화 중에는 두 배)
