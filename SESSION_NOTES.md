# 🚀 Quick Start - 다음 세션 참고용

## 📌 현재 상태 (2025-11-14)

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
| `config.json` | 게임 설정 + **채널 설정** | ✅ 필요시 (team1/team2 채널명) |
| `wins.json` | **실제 모드 전적** | ⚠️ ID 업데이트 필요 |
| `wins_dev.json` | 개발 모드 전적 | ✅ 사용 중 |
| `.env` | 환경변수 | ✅ 현재 DEV_MODE=true |

**config.json 채널 설정:**
```json
{
  "channels": {
    "team1": "TEAM1",  // Discord 서버의 팀1 음성 채널 이름
    "team2": "TEAM2"   // Discord 서버의 팀2 음성 채널 이름
  }
}
```
→ `/게임시작` 실행 시 **명령 실행 채널 + TEAM1 + TEAM2**에 동시 메시지

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
- [ ] `/전적` 명령어 - 개인 전적 조회
- [ ] `/랭킹` 명령어 - 승률 순위
- [ ] 챔피언 밴 시스템
- [ ] 통계 시각화

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

**마지막 업데이트**: 2026-01-19
**현재 Round**: 88 (DEV_MODE), 75 (실제 모드)
**다중 채널**: ✅ 지원 (명령 채널 + TEAM1 + TEAM2)
