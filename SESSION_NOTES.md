# 🚀 Quick Start - 다음 세션 참고용

## 🆕 2026-07-14 대규모 확장 (전적 데이터 + 웹 대시보드)

봇 코어 외에 **전적 아카이브 → 웹 대시보드 → 자동 배포** 계층이 추가됨. 자세한 배경은 `CLAUDE.md`(프로젝트)와 `PARSE_REPORT.md` 참고.

### 데이터 흐름 (한 판이 끝나면)
```
/승리 클릭
  → wins.json 갱신 (개인 누적 승수, 기존)
  → game_recorder.record_game(): history_data.json/.js 에 판 상세 append
       (팀·챔프·승자·시간, 라운드가 직전 이하로 회귀하면 시즌 자동 +1)
  → game_recorder.upload_async(): history_data.js 를 호스팅에 SFTP 자동 업로드
       (백그라운드 스레드 + try/except 2중 방어 → 실패해도 봇 무영향, 다음 판이 만회)
  → 대시보드 dcom.co.kr/arena 실시간 반영
```

### 핵심 파일 (신규)
| 파일 | 역할 |
|---|---|
| `game_recorder.py` | 판 기록 + 시즌 감지 + 호스팅 SFTP 업로드 |
| `history_data.json` | 전 판 상세 마스터 데이터 (스키마: round, round_orig, season, team1/2, winner, time, sources) |
| `history_data.js` | 위를 `window.HISTORY_DATA=`로 감싼 대시보드 로드용 |
| `stats.html` | 정적 전적 대시보드 (개인/2·3인 시너지/챔피언/3:3 매치업) |
| `parse_all_history.py` | 디스코드 3채널 풀스캔 복구 (재해복구 전용, 평상시 미사용) |
| `wins_prev_season.json` | 시즌1(150판) 집계 백업 |
| `PARSE_REPORT.md` | 과거 전적 복구·검증·유령 라운드 조사 리포트 |

### 배포 (dcom.co.kr/arena)
- Cafe24 정적 호스팅. SSH MCP 서버명 `dcom`, 원격 `~/www/arena/` (`index.html`=stats.html, `history_data.js`=데이터)
- **데이터는 봇이 자동 업로드** (`.env`의 `ARENA_SSH_*`). `stats.html` 수정 시에만 index.html 수동 재업로드
- **왜 PC/맥에서 봇을 돌리나**: Cafe24 웹호스팅은 Python 2.7 + crontab/openssl-dev 부재 + 상시 데몬 금지라 봇 상주 불가. 대시보드(정적)만 올림

### 새 시즌 시작
`wins.json` 백업 후 리셋 → 다음 판이 R1로 기록되며 시즌 자동 +1. 대시보드 드롭다운에 시즌이 자동 추가됨 (하드코딩 없음)

---

## 📌 현재 상태 (2025-11-14, 봇 코어 기준)

### ✅ 완료된 기능
- [x] 시작 버튼 (수동 게임 시작)
- [x] 랜덤 팀 배정
- [x] 팀별 색상 구분 (🔵/🔴)
- [x] 큰 폰트 타이머 표시
- [x] 전적 시스템 (오늘/누적)
- [x] 성능 최적화 (병렬 처리)
- [x] 코드 주석 추가
- [x] **다중 채널 동시 메시지** (명령 채널 + TEAM1 + TEAM2)
- [x] **asyncio.gather() 병렬 처리** (지연 3배 개선)

### ⚠️ 실제 모드 사용 전 필수 작업
```json
// wins.json 업데이트 필요
{
  "365414320332472332": {    // ✅ 정한솔 (실제 ID)
    "name": "정한솔",
    "wins": 42
  },
  "100000000000000001": {    // ❌ 나머지 5명은 가짜 ID
    "name": "jaecheol232",   // 실제 Discord ID로 변경 필요!
    "wins": 31
  }
  // ... 나머지 4명도 실제 ID 필요
}
```

**Discord ID 확인 방법:**
1. Discord 개발자 모드 활성화 (설정 → 고급 → 개발자 모드)
2. 유저 우클릭 → "ID 복사"
3. wins.json에 해당 ID로 업데이트

---

## 🔧 모드 전환 방법

### `.env` 파일 수정
```env
# 개발 모드 (테스트용 - 현재)
DEV_MODE=true

# 실제 모드 (Discord 서버에서 사용)
DEV_MODE=false
```

**변경 후 봇 재시작 필수!**

---

## 📂 주요 파일 설명

| 파일 | 설명 | 수정 필요 |
|------|------|----------|
| `got_champe.py` | 메인 봇 코드 | ❌ 완료 |
| `game_recorder.py` | 판 기록 + 시즌 감지 + 호스팅 업로드 | ❌ 완료 |
| `config.json` | 게임 설정 + **채널 리스트** | ✅ 필요시 (채널명) |
| `wins.json` | **실제 모드 개인 전적** | ⚠️ ID 업데이트 필요 |
| `wins_dev.json` | 개발 모드 전적 | ✅ 사용 중 |
| `history_data.json/.js` | 판 상세 마스터 데이터 (자동 생성) | ❌ 봇이 관리 |
| `stats.html` | 웹 전적 대시보드 | ✅ 수정 시 index.html 재업로드 |
| `.env` | 환경변수 (토큰, DEV_MODE, ARENA_SSH_*) | ✅ 실운영 DEV_MODE=false |

**config.json 채널 설정 (리스트로 변경됨, 2026-07-14):**
```json
{
  "pick_timeout": 20,
  "champion_count": 8,
  "channels": ["팀짜기", "TEAM1", "TEAM2"]
}
```
→ `channels[0]`(팀짜기)이 명령 채널, 나머지는 결과/진행 전파 대상. 이름은 대소문자까지 완전 일치해야 검색됨

---

## 🎮 주요 명령어

```
/게임시작           # 팀 배정 + 챔피언 제시
🚀 챔피언 선택 시작   # 버튼 클릭 (타이머 시작)
(챔피언 버튼 클릭)   # 순서대로 선택
/승리 또는 드롭다운   # 승리 팀 선택
```

---

## 🐛 문제 해결

### 문제: "invalid literal for int() with base 10: 'total_rounds'"
**원인:** wins_data.items()에서 "total_rounds"를 int()로 변환 시도
**해결:** ✅ 이미 수정됨 (uid != "total_rounds" 조건 추가)

### 문제: 타이머가 중복으로 표시됨
**원인:** 이전 타이머가 종료 안 됨
**해결:** ✅ index 검증으로 자동 종료

### 문제: 반응이 느림
**원인:** 메시지를 두 번 편집 (view → embed)
**해결:** ✅ 한 번에 통합 업데이트

### 문제: 3개 채널 업데이트 시 지연 발생 (타이머 부정확)
**원인:** 순차 처리로 인한 1~2초 지연
**해결:** ✅ asyncio.gather() 병렬 처리로 0.5초 내 완료

---

## 💡 다음에 할 일 (제안)

### 1순위: 실제 모드 테스트
1. Discord 서버에 **TEAM1**, **TEAM2** 음성 채널 생성 (또는 config.json 수정)
2. 나머지 5명의 실제 Discord ID 확인
3. `wins.json` 업데이트
4. `.env`에서 `DEV_MODE=false`로 변경
5. 봇 재시작 후 실제 서버에서 테스트
6. 다중 채널 동시 메시지 확인

### 2순위: 추가 기능 (선택사항)
- [x] 통계 시각화 — 웹 대시보드로 완료 (stats.html)
- [ ] `/전적` 명령어 - 개인 전적 조회 (대시보드로 대체 가능)
- [ ] `/랭킹` 명령어 - 승률 순위
- [ ] 챔피언 밴 시스템

---

## 📋 코드 구조 참고

### 주요 함수
```python
load_config()              # config.json 로드 (채널 설정 포함)
load_wins()                # 전적 데이터 로드
fetch_champion_data()      # LoL 챔피언 API 호출
get_game_channels()        # 명령 채널 + team1 + team2 채널 가져오기
calculate_pick_order()     # 픽 순서 계산 (승수 기반)
get_selection_status()     # 선택 현황 문자열 생성
update_champion_message()  # 모든 채널 embed 동시 업데이트 (병렬 처리)
pick_timeout_handler()     # 개인별 타이머 관리 (병렬 처리)

# game_recorder.py (승리 처리 시 호출)
record_game()              # history_data 판 append + 시즌 자동 감지
upload_async()             # history_data.js 호스팅 SFTP 업로드 (백그라운드)
```

### 주요 클래스
```python
MockUser                   # DEV_MODE용 가상 유저
StartButton                # 게임 시작 버튼
ChampionButton             # 챔피언 선택 버튼
VictorySelect              # 승리 팀 선택 드롭다운
```

### 전역 상태
```python
game_started = False        # 게임 시작 여부
pick_order = []             # 픽 순서
current_pick_index = 0      # 현재 차례
selected_users = {}         # 선택된 챔피언
wins_data = {}              # 전적 데이터
champion_messages = {}      # {channel_id: message} - 다중 채널 메시지
champion_views = {}         # {channel_id: view} - 다중 채널 View
current_game_channels = []  # 현재 게임 채널 리스트
```

---

## 🔍 디버깅 팁

### 로그 확인
봇 시작 시 출력:
```
[OK] Bot logged in: 봇이름
[DEV_MODE] True
[WINS] Loaded 6 players
[ROUNDS] Starting from Round 88
[CONFIG] pick_timeout=15s, champion_count=8
```

게임 시작 시 출력:
```
[WARNING] 채널 'TEAM1' (team1)을 찾을 수 없습니다!  # 채널이 없을 때
[ERROR] Failed to update message in channel 123456789...  # 메시지 업데이트 실패 시
```

### 일반적인 오류
1. **"Unknown interaction"**: interaction.response를 3초 내 호출 필요
2. **user.id 매칭 실패**: wins.json의 ID 확인
3. **타이머 안 멈춤**: index 검증 로직 확인

---

## 📞 빠른 참조

- **전체 문서**: `README.md` 참고
- **코드 주석**: 각 함수에 docstring 추가됨
- **백업**: `backup/` 디렉토리에 이전 버전 보관

---

## 🎉 주요 변경사항 요약

### 2026-07-14
1. **판 기록 자동화** — `game_recorder.py` 신설. `/승리` 시 `history_data.json/.js`에 판 상세 append, 라운드 리셋으로 시즌 자동 감지
2. **웹 전적 대시보드** — `stats.html` (개인·2/3인 시너지·챔피언·3:3 매치업, 시즌/세션/인원 필터, 챔프 초상화, 번 돈 정산). dcom.co.kr/arena 배포
3. **호스팅 SFTP 자동 업로드** — 판 기록 직후 백그라운드 업로드, 실패해도 봇 무영향
4. **과거 전적 복구** — 3채널 풀스캔으로 182판(시즌1 150 + 시즌2 32) 복구, 시즌1 라운드 연번 재부여
5. **config.json 채널 dict → 리스트**, legacy 파서 삭제

### 2026-01-19
1. **승리 결과/통계 다중 채널 전송**
   - 기존: 승리팀 선택 후 결과가 명령 실행 채널에만 표시
   - 변경: 모든 게임 채널(명령 채널 + TEAM1 + TEAM2)에 동시 전송
   - 결과 embed, 오늘의 결과, 누적 전적 모두 병렬 전송

### 2025-11-14
1. **다중 채널 동시 메시지**
   - 명령 실행 채널 + TEAM1 + TEAM2 음성 채널에 동시 전송
   - 팀원들이 각자 음성 채널에서도 진행 상황 확인 가능

2. **병렬 처리 최적화**
   - `asyncio.gather()`로 3개 채널 동시 업데이트
   - 타이머 정확도 2배 향상 (±1~2초 → ±0.5초)
   - API 호출 속도 3배 개선 (~1.5초 → ~0.5초)

3. **config.json 채널 설정**
   - `channels.team1`, `channels.team2` 추가
   - 팀 채널 이름 자유롭게 변경 가능

---

**마지막 업데이트**: 2026-07-14
**현재 시즌**: 시즌 2 진행중 (32판+), 시즌1 150판 아카이브
**대시보드**: <https://dcom.co.kr/arena/> (판 기록 시 자동 갱신)
**다중 채널**: ✅ 지원 (팀짜기 + TEAM1 + TEAM2)
