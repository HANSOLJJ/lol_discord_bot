<!-- Cloudflare 터널, DNS, 캐시 및 디스코드 개발자 포털 인프라 설정 가이드 -->
# 인프라 구성 및 디스코드 개발자 포털 설정 가이드

본 문서는 리그 오브 레전드 투기장 서비스의 Cloudflare 터널, 도메인 라우팅, 캐시 정책, 그리고 디스코드 개발자 포털 설정 현황을 정리합니다. 설정의 도입 배경과 변경 시 주의점, 향후 운영 봇을 액티비티 모드로 전환하기 위한 점검 항목을 기술합니다.

---

## 1. 외부 주소 및 라우팅 요약

서비스에 사용되는 도메인과 내부 프록시 대상은 다음과 같습니다.

| 도메인 / 경로 | 프록시 대상 로컬 주소 | 처리 주체 및 역할 |
|---|---|---|
| `lol.hansoljj.com/pick-api` | `http://127.0.0.1:8790` | 운영 디스코드 봇(pm2 `lol-bot`) 액티비티 API 및 WebSocket 서버. 운영 봇에 `DISCORD_CLIENT_ID`와 `DISCORD_CLIENT_SECRET`이 주입되어야 기동됩니다. |
| `lol.hansoljj.com` (기타 경로) | `http://127.0.0.1:8791` | aiohttp 정적 웹 서버(pm2 `lol-web`). `/` 접근 시 디스코드 액티비티(`?frame_id=`)면 픽 화면, 일반 브라우저면 전적 대시보드를 서빙합니다. `/terms`, `/privacy`, `/history_data.json`, `/legacy.html`, `/favicon.svg` 등을 처리합니다. |
| `arena.hansoljj.com` | `http://127.0.0.1:8791` | 과거 서비스 주소입니다. 정적 웹 서버가 `https://lol.hansoljj.com`과 동일한 경로 및 쿼리로 301 영구 리다이렉트합니다. |
| `lol-dev.hansoljj.com` | `http://127.0.0.1:5173` | 개발용 액티비티 프론트엔드(pm2 `lol-web-dev`, Vite 개발 서버). `/pick-api` 요청은 Vite 내부 프록시를 통해 개발 봇(`http://127.0.0.1:8792`)으로 전달됩니다. |
| `fin.hansoljj.com` | `finance` 터널 | 롤 봇 프로젝트와 무관한 독립 서비스입니다. 롤 관련 작업에서 절대 변경하지 않습니다. |

- `pick.hansoljj.com`은 초기 설계 시 검토되었으나 현재 사용하지 않습니다.

---

## 2. Cloudflare 터널 구성

### 2-1. 롤 전용 터널 `lol`
롤 서비스 전용 트래픽을 처리하기 위해 맥미니 로컬에서 관리하는 전용 Cloudflare 터널을 운영합니다.

- **터널 이름**: `lol`
- **터널 ID**: `bdf8b12f-2d40-4c1e-8f6a-89e5d4350797`
- **관리 방식**: 로컬 관리형(Local-managed). 맥미니 터미널에서 `cloudflared tunnel create lol` 명령으로 생성되었으며 인증서는 `~/.cloudflared/cert.pem`을 사용합니다.
- **설정 파일**: `~/.cloudflared/lol.yml` (맥미니 로컬 전용, git 저장소에 포함하지 않음)
- **인증 파일**: `~/.cloudflared/bdf8b12f-2d40-4c1e-8f6a-89e5d4350797.json` (맥미니 로컬 전용, git 저장소에 포함하지 않음)
- **프로세스 관리**: pm2 앱 `lol-tunnel`이 아래 명령으로 실행합니다.
  ```bash
  cloudflared tunnel --config ~/.cloudflared/lol.yml run
  ```

### 2-2. ingress 라우팅 순서
Cloudflare 터널은 ingress 규칙을 위에서부터 차례대로 평가하여 가장 먼저 일치하는 대상을 선택합니다. 따라서 세부 경로가 일반 도메인 규칙보다 반드시 앞서야 합니다.

`~/.cloudflared/lol.yml`의 라우팅 구성은 다음과 같습니다.

```yaml
tunnel: bdf8b12f-2d40-4c1e-8f6a-89e5d4350797
credentials-file: /Users/hansol/.cloudflared/bdf8b12f-2d40-4c1e-8f6a-89e5d4350797.json

ingress:
  # 1. 개발 환경 액티비티 프론트 (Vite 개발 서버)
  - hostname: lol-dev.hansoljj.com
    service: http://127.0.0.1:5173

  # 2. 운영 액티비티 백엔드 API (경로 접두사 매칭)
  - hostname: lol.hansoljj.com
    path: ^/pick-api
    service: http://127.0.0.1:8790

  # 3. 운영 정적 웹 서버 (대시보드 및 번들 자산)
  - hostname: lol.hansoljj.com
    service: http://127.0.0.1:8791

  # 4. 과거 주소 (웹 서버에서 301 처리)
  - hostname: arena.hansoljj.com
    service: http://127.0.0.1:8791

  # 5. 미일치 트래픽 차단
  - service: http_status:404
```

### 2-3. 설정 변경 및 검증 절차
`~/.cloudflared/lol.yml`을 수정한 뒤에는 터널 프로세스를 재시작하기 전에 반드시 ingress 검증을 거쳐야 합니다.

```bash
# 1. ingress 문법 및 유효성 검사
cloudflared tunnel --config ~/.cloudflared/lol.yml ingress validate

# 2. 검증 통과 후 pm2 프로세스 재시작
pm2 restart lol-tunnel
```

이 작업은 롤 전용 터널만 재시작하므로 finance 터널을 포함한 맥미니 내 다른 서비스에 아무런 영향을 주지 않습니다.

### 2-4. DNS 설정 (CNAME 라우팅)
Cloudflare DNS에 등록된 세 도메인은 모두 `lol` 터널로 라우팅됩니다.

- `lol.hansoljj.com` CNAME → `bdf8b12f-2d40-4c1e-8f6a-89e5d4350797.cfargotunnel.com`
- `lol-dev.hansoljj.com` CNAME → `bdf8b12f-2d40-4c1e-8f6a-89e5d4350797.cfargotunnel.com`
- `arena.hansoljj.com` CNAME → `bdf8b12f-2d40-4c1e-8f6a-89e5d4350797.cfargotunnel.com`

초기 DNS 등록은 맥미니에서 아래 명령으로 수행되었습니다.
```bash
cloudflared tunnel route dns [--overwrite-dns] bdf8b12f-2d40-4c1e-8f6a-89e5d4350797 <호스트이름>
```

---

## 3. finance 터널 및 이전 환경과의 분리

맥미니에는 롤 프로젝트 외에도 `finance` 서비스가 구동 중입니다. 상호 간섭으로 인한 장애를 방지하기 위해 엄격히 격리되어 있습니다.

- **독립 구동**: finance 터널(ID: `2558b984-…`)은 `~/.cloudflared/config.yml` 설정 파일을 쓰며, 2026-09-29부터 pm2 앱 `finance-tunnel`(`cloudflared tunnel --config ~/.cloudflared/config.yml run`)이 실행합니다. 롤 저장소의 `ecosystem.config.cjs`에는 넣지 않고 pm2 명령으로 따로 등록했습니다. 예전 LaunchAgent(`com.cloudflare.cloudflared`)는 내리고 plist를 `~/Library/LaunchAgents/com.cloudflare.cloudflared.plist.bak-20260929-pm2`로 백업했습니다. `brew services`에는 cloudflared가 등록되어 있지 않습니다.
- **서비스 중단 주의**: `finance`나 `finance-tunnel`을 재시작하면 finance 서비스가 잠깐 끊어집니다. 롤 작업 시 건드리지 않습니다. 되돌릴 때는 `pm2 delete finance-tunnel` 뒤 plist 이름을 원래대로 바꾸고 `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist`를 실행합니다.
- **Zero Trust 대시보드 조작 금지**: Cloudflare Zero Trust 대시보드에 노출되는 **"Migrate finance"** 버튼은 되돌릴 수 없는 영구적인 마이그레이션을 트리거하므로 절대로 클릭하지 않습니다.
- **레거시 정리**: 과거 Windows 환경에서 테스트 목적으로 운영하던 대시보드 관리형 터널의 `lol-dev` 공개 호스트 이름은 모두 삭제되었습니다. Windows 머신은 인프라 구성에서 완전히 제외되었습니다.

---

## 4. Cloudflare Pages 도메인 분리

2026-09-29에 Cloudflare Pages 설정에서 `arena.hansoljj.com` 사용자 지정 도메인을 공식 분리하였습니다.

- GitHub의 `lol_arena` 저장소와 연동된 Pages 프로젝트는 `*.pages.dev` 주소로 빌드 및 배포가 지속되지만, 실제 서비스 목적의 대시보드로는 사용하지 않습니다. Cloudflare의 Pages 프로젝트와 GitHub 앱 "Cloudflare Workers and Pages"는 삭제 대상입니다. finance도 Pages를 쓰지 않습니다(빌드 기록 없음).
- `lol_arena` 저장소는 2026-09-29에 지원 중단(Deprecated)으로 표시했습니다(설명과 README). 봇의 전적 백업(`history_data.json`) 대상이라 저장소는 남겨 두며, **Archive하면 읽기 전용이 되어 백업이 실패하므로 하지 않습니다.**
- 사용자가 `arena.hansoljj.com`으로 접근하면 `lol` 터널을 거쳐 맥미니 정적 웹 서버(8791)로 도달하고, 웹 서버의 `legacy_host_redirect` 미들웨어가 `https://lol.hansoljj.com`의 동일 경로 및 쿼리로 301 영구 리다이렉트합니다. 이를 통해 기존에 공유된 링크의 접근성을 완벽히 보존합니다.

---

## 5. Cloudflare 캐시 규칙 (Cache Rules)

개발 환경 액티비티의 원활한 디버깅을 위해 전용 캐시 규칙이 설정되어 있습니다.

- **규칙 이름**: `lol-dev캐시 끄기`
- **매칭 조건**: `URI Full wildcard https://lol-dev.hansoljj.com/*`
- **동작**: `Bypass cache` (캐시 적용 안 함)

### 설정 배경 및 이유
Cloudflare의 기본 CDN 에지 캐시 정책은 정적 확장자(`.css` 등)에 대해 임의로 장기 캐시 헤더(`Cache-Control: max-age=14400`, 4시간)를 부가합니다.
Vite 개발 서버가 제공하는 소스 코드 파일명에는 해시가 포함되지 않으므로, 개발 액티비티를 열었을 때 디스코드 내장 브라우저가 과거 CSS 모듈을 4시간 동안 재사용하여 화면 스타일이 깨지는 현상이 발생했습니다.
캐시 바이패스 규칙을 적용하여 개발 서버의 변경 사항이 즉시 디스코드 액티비티 화면에 반영되도록 조치했습니다.

운영 환경(`https://lol.hansoljj.com/*`)의 경우 Vite 프로덕션 빌드 단계에서 모든 자산 파일명에 내용 기반 고유 해시(`assets/[name].[hash].js/css`)가 부여되며 HTML은 no-cache로 서빙되므로 별도의 에지 캐시 바이패스 규칙이 필요하지 않습니다.

---

## 6. 디스코드 개발자 포털 설정

### 6-1. 개발용 앱 (`롤랜덤챔프봇-dev`)
- **Application ID**: `1554005426436313159`
- **테스트 환경**: TEST2 길드
- **Activities 활성화**: 켜짐 (Embedded App)
- **URL Mappings**:
  - `/` → `lol-dev.hansoljj.com`
  - `/ddragon` → `ddragon.leagueoflegends.com` (리그 오브 레전드 Data Dragon CDN 자산 프록시)

### 6-2. 운영용 앱 (`롤랜덤챔프봇`)
- **Application ID**: `1354988564458377216`
- **현재 동작 방식**: 디스코드 액티비티(`pick_mode: activity`, 2026-09-29 전환). 되돌릴 때는 `config.json`의 `pick_mode`를 `embed`로 바꾸고 `pm2 restart lol-bot`을 합니다.
- **Activities**: 켜짐. URL 매핑 `/` → `lol.hansoljj.com`, `/ddragon` → `ddragon.leagueoflegends.com`. Max Participants 6, Supported Platforms는 dev 앱과 같게 맞춤.
- **OAuth2 Redirects**: `https://127.0.0.1`. 액티비티는 리디렉션을 실제로 쓰지 않지만, 하나도 없으면 디스코드가 로그인 승인(`authorize`)을 거절합니다.
- **앱 인증**: 완료(2026-09-29, Stripe 신원 확인 자동 승인, `verification_state` 6). 인증된 앱은 "공개 봇" 설정을 끌 수 없습니다.
- **App Testers**: 친구들을 테스터로 등록해서 씁니다. 아래 "앱 인증과 액티비티 공개는 별개" 참고.

### 앱 인증과 액티비티 공개는 별개
- 앱 인증을 마쳐도 액티비티는 여전히 **개발자 팀과 App Testers만** 실행할 수 있었습니다. 다른 사용자는 디스코드가 페이지를 불러오기 전에 "활동 실행 실패 / 활동 실행 불가능"으로 막습니다(우리 서버에 요청이 오지 않음).
- 권한(활동 사용, 외부 앱 사용, 앱 명령, 메시지 보내기), 명령 권한, 플랫폼, 리디렉션을 모두 확인했지만 원인이 아니었고, 테스터로 추가하자마자 열렸습니다.
- 모든 사용자에게 열려면 Discovery 활성화가 필요한지, 디스코드 내부 공개 단계 변경이 필요한지는 공식 문서가 모호해서 확정하지 못했습니다. Discovery를 켜면 앱 디렉터리에 공개되고, 봇 코드에 서버 제한이 없어 다른 서버의 `/승리`가 전적에 섞일 수 있으므로 켜기 전에 서버 제한을 먼저 넣어야 합니다.
- **테스터 등록 방법**: 포털의 운영 앱 → App Testers에 친구의 사용자명(표시 이름 아님)을 추가합니다. 등록자와 디스코드 친구여야 하며, "대기 중인 초대" 상태에서도 바로 실행되는 것을 확인했습니다. 짧은 시간에 여러 번 시도하면 `The resource is being rate limited`가 뜨니 잠시 뒤 한 명씩 추가합니다. 테스터 규칙상 서버 인원이 25명 미만이어야 합니다(투기장 11명).

### 6-3. Cloudflare Access 및 URL 매핑 시 유의사항
- **Cloudflare Access 미적용**: 디스코드 내장 브라우저 프록시가 `lol-dev.hansoljj.com` 및 `lol.hansoljj.com`으로 접근해야 하므로, Cloudflare Zero Trust Access 인증 정책을 걸지 않습니다. 적용 시 디스코드 액티비티가 로드되지 않습니다.
- **URL 매핑 등록 형식**: 디스코드 개발자 포털의 target에는 프로토콜(`https://`)이나 파일 경로(`index.html`)를 넣지 않고 순수 호스트 이름만 등록합니다.
- **API 경로 라우팅**: `/pick-api` 경로는 개발자 포털 URL 매핑에 등록하지 않습니다. 개발 환경은 Vite 내부 프록시가 백엔드로 전달하며, 운영 환경은 Cloudflare 터널 ingress의 `path: ^/pick-api` 규칙이 8790 포트로 직접 라우팅합니다.

---

## 7. 운영 전환 체크리스트 (Embed → Activity)

운영 환경의 픽 방식을 기존 텍스트 채널 임베드에서 디스코드 액티비티로 전환할 때는 아래 단계를 순서대로 수행합니다. **2026-09-29에 모든 단계를 마치고 전환했습니다.**

1. **디스코드 개발자 포털 액티비티 활성화 및 URL 매핑 등록**
   - 개발자 포털의 운영 앱(`롤랜덤챔프봇`) 설정에서 `Activities`를 활성화합니다.
   - URL Mapping에 `/` → `lol.hansoljj.com` 및 `/ddragon` → `ddragon.leagueoflegends.com`을 등록합니다.
   - OAuth2 → Redirects에 `https://127.0.0.1`을 넣습니다. 비어 있으면 로그인 승인이 실패합니다.
2. **맥미니 `.env` 파일에 OAuth2 인증 키 주입**
   - 맥미니 저장소 루트의 `.env` 파일에 운영 앱의 `DISCORD_CLIENT_ID` 및 `DISCORD_CLIENT_SECRET`을 설정합니다.
   - 키가 주입되어야 운영 봇(pm2 `lol-bot`)이 기동될 때 포트 8790에서 `/pick-api` 백엔드 서버를 함께 시작합니다.
   - 완료(2026-09-29). 키는 봇이 시작할 때만 읽으므로, 전환할 때 `pm2 restart lol-bot`으로 반영합니다.
3. **픽 화면(프론트엔드)에 운영 앱 번호 넣기**
   - 픽 화면은 켜질 때 디스코드 SDK에 자기 앱 번호(Application ID)를 알려야 하고, 번호가 없으면 디스코드 로그인에서 실패합니다.
   - 브라우저 코드는 맥미니 `.env`를 읽지 못하므로, Vite가 빌드할 때 파일에서 번호를 읽어 JS에 넣습니다. `npm run dev`(lol-dev)는 `web/activity/.env.development`(dev 앱 번호)를, `npm run build`(운영)는 `web/activity/.env.production`(운영 앱 번호)을 읽습니다.
   - 완료(2026-09-29). `web/activity/.env.production`에 `VITE_DISCORD_CLIENT_ID=1354988564458377216`을 커밋했습니다. 앱 번호는 공개 값이라 git에 올려도 됩니다.
4. **봇 게임 모드 및 채널 설정 변경**
   - `config.json`에서 `pick_mode`를 `"activity"`로 변경합니다.
   - `channels` 설정을 `["팀짜기"]` 단일 채널로 단순화합니다 (액티비티 모드에서는 음성 채널별 개별 임베드 전송이 불필요합니다).
5. **디스코드 앱 인증과 테스터 등록**
   - 앱 인증 조건: 앱이 개발자 팀 소속, 약관 URL(`https://lol.hansoljj.com/terms`)과 개인정보 처리방침 URL(`https://lol.hansoljj.com/privacy`), 설치 링크, 팀 멤버 전원의 이메일 인증과 2단계 인증. 앱을 팀으로 옮기는 것은 되돌릴 수 없습니다.
   - 인증만으로는 친구들이 실행하지 못했으므로(6-2절), 플레이어들을 App Testers로 등록합니다.
6. **확인**
   - 개발자 본인 계정은 항상 열리므로 확인에 쓰지 않습니다. **테스터로 등록한 친구 계정**으로, 음성 채널이나 `/실행`(Entry Point)으로 연 액티비티에 들어가지는지 확인합니다.

---

## 8. 인프라 변경 이력

과거 기획 및 과도기 구성에서 현재 설정으로 변경된 주요 내역입니다.

| 항목 | 과거 계획 / 과도기 상태 | 현재 확정 상태 | 변경 사유 |
|---|---|---|---|
| `pick.hansoljj.com` | 봇 액티비티 API 전용 도메인으로 계획 | 미사용 폐기 | `lol.hansoljj.com/pick-api` 경로 라우팅으로 일원화하여 도메인 관리 단순화 |
| `arena.hansoljj.com` 서빙 | Cloudflare Pages 연동으로 배포 | 맥미니 정적 웹 서버(8791)로 인입 후 `https://lol.hansoljj.com`으로 301 리다이렉트 | 2026-09-29 Pages 사용자 지정 도메인 분리, 기존 공유 링크 보존 및 메인 도메인 통일 |
| 액티비티 URL 매핑 | `/` → `arena.hansoljj.com/pick` 계획 | `/` → `lol.hansoljj.com` (개발은 `lol-dev.hansoljj.com`) | `?frame_id=` 쿼리 파라미터 기반으로 웹 서버 루트에서 대시보드와 픽 화면을 자동 분기 |
| finance 터널 공용 사용 | 맥미니 기존 finance 터널에 롤 ingress 추가 계획 | 롤 전용 독립 터널 `lol` 생성 및 분리 | finance 서비스 중단 방지 및 설정 변경 시 상호 격리 보장 |
| 운영 픽 방식 | 채널 버튼(`pick_mode: embed`), 3채널 전송 | 액티비티(`pick_mode: activity`), `channels: ["팀짜기"]` | 2026-09-29 운영 전환. 친구들은 App Testers로 등록 |
| `lol_arena` 저장소 | 대시보드 원본과 Pages 배포 | 지원 중단 표시, 전적 백업 전용. 로컬 클론 삭제 | 2026-09-29 대시보드를 `lol_discord_bot/web/`으로 이전 완료 |
| Windows 개발 환경 터널 | Windows 서비스로 등록된 대시보드 관리형 터널이 `lol-dev`를 처리 | 그 터널의 `lol-dev` 공개 호스트 이름을 지우고, `lol-dev` DNS를 맥미니 `lol` 터널로 옮김. Windows의 터널 자체와 cloudflared 서비스는 남아 있을 수 있으나 쓰지 않는다 | 2026-09-29 개발·운영 환경을 모두 맥미니로 단일화 |

