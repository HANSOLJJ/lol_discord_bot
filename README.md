# 🎮 League of Legends 챔피언 픽 Discord Bot

## 📋 프로젝트 개요

6명의 플레이어가 리그 오브 레전드 챔피언을 순서대로 선택하는 Discord 봇입니다.

### 🎯 주요 기능

1. **팀 구성**: 6명을 랜덤으로 3:3 팀으로 나눔
2. **챔피언 선택**:
   - 8개의 랜덤 챔피언 제시
   - 승수가 낮은 사람부터 순서대로 선택 (공평성)
   - 개인별 제한 시간 (설정 가능)
   - 시간 초과 시 자동 랜덤 배정
3. **전적 관리**:
   - 승/패 기록 자동 저장
   - 판별 상세 기록(팀·챔프·승자) 자동 저장 → `history_data.json`
   - 오늘의 전적 및 누적 전적 표시
   - 승률 자동 계산
   - **웹 전적 대시보드** ([hansoljj.github.io/lol_arena](https://hansoljj.github.io/lol_arena/), 원본은 `lol_arena` repo)
4. **시각적 표시**:
   - 팀별 색상 구분 (🔵 team1 파란색, 🔴 team2 빨간색)
   - 실시간 타이머 표시 (큰 폰트)
   - 선택 현황 및 픽순 한눈에 확인
5. **다중 채널 동시 지원**:
   - 명령 실행 채널 + 팀 음성 채널(TEAM1, TEAM2)에 동시 메시지
   - 각 팀이 음성 채널 채팅에서도 진행 상황 확인 가능
   - 병렬 처리로 지연 최소화 (1초 단위 정확한 타이머)

---

## 📁 프로젝트 구조

```
lol_discord_bot/
├── got_champe.py          # 메인 봇 코드
├── game_recorder.py       # 판 기록 모듈 (history_data 자동 갱신, 시즌 감지, GitHub Pages 업로드)
├── parse_all_history.py   # 디스코드 채널 재파싱 (재해복구용)
├── paths.py               # 모든 데이터/산출물 경로 상수 (single source of truth)
├── config.json            # 게임 설정 (timeout, 챔피언 수, 채널)
├── requirements.txt       # 파이썬 패키지 목록
├── .env                   # 환경변수 (토큰, DEV_MODE, ARENA_GH_*)
├── README.md / CLAUDE.md  # 문서 (루트)
├── data/                  # 전적 데이터 (봇 I/O, gitignore)
│   ├── wins.json          #   개인 누적 전적 (실제 모드)
│   ├── wins_dev.json      #   개발용 전적
│   └── history_data.json  #   전 판 상세 마스터 데이터
├── dashboard/             # 봇이 업로드용 js 생성하는 스테이징 (gitignore)
│   └── history_data.js    #   대시보드 데이터 (자동 생성 → lol_arena repo로 PUT)
├── docs/                  # 문서
│   └── PARSE_REPORT.md    #   과거 전적 복구·검증 리포트
├── backup/                # 백업 (bak, 구시즌 집계)
└── logs/                  # 봇 로그
```

---

## ⚙️ 설정 파일

### 1. `.env`
```env
DISCORD_TOKEN=your_discord_bot_token_here
DEV_MODE=true    # 개발 모드: true, 실제 모드: false
```

**DEV_MODE 차이점:**

| 항목 | DEV_MODE=true | DEV_MODE=false |
|------|---------------|----------------|
| 사용 파일 | `wins_dev.json` | `wins.json` |
| 유저 생성 | MockUser (가상) | 실제 Discord 유저 |
| 턴제 검증 | ❌ 없음 (누구나 선택 가능) | ✅ 있음 (자기 차례만) |
| 용도 | 테스트 및 개발 | 실제 Discord 서버 |

### 2. `config.json`
```json
{
  "pick_timeout": 15,      // 챔피언 선택 제한 시간 (초)
  "champion_count": 8,     // 제시할 챔피언 수
  "channels": {
    "team1": "TEAM1",      // 팀1 음성 채널 이름 (자유롭게 변경 가능)
    "team2": "TEAM2"       // 팀2 음성 채널 이름 (자유롭게 변경 가능)
  }
}
```

**채널 설정:**
- `team1`, `team2`: 팀 음성 채널 이름 (Discord 서버에 존재해야 함)
- `/게임시작` 실행 시 **명령 실행 채널 + team1 + team2**에 동시 메시지 전송
- 중복 제거: 명령 채널이 team1/team2와 같으면 한 번만 전송

### 3. `wins.json` / `wins_dev.json`
```json
{
  "total_rounds": 74,            // 총 게임 판수 (자동 증가)
  "365414320332472332": {        // Discord User ID (실제 모드)
    "name": "정한솔",
    "wins": 42
  },
  "100000000000000001": {        // 가짜 ID (개발 모드)
    "name": "jaecheol232",
    "wins": 31
  }
}
```

**⚠️ 중요:**
- **실제 모드(`wins.json`)**: 반드시 실제 Discord User ID 사용
- **개발 모드(`wins_dev.json`)**: 가짜 ID 사용 가능

---

## 🚀 실행 방법

### 1. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 설정
1. `.env` 파일에 Discord Bot Token 추가
2. `DEV_MODE` 설정 (개발: `true`, 실제: `false`)
3. 실제 모드 사용 시 `wins.json`에 실제 Discord User ID 입력

### 3. 봇 실행
```bash
python got_champe.py
```

### 📌 wins.json으로 실행하기 (실제 모드)

실제 Discord 유저로 게임을 돌리고 전적을 `wins.json`에 기록하려면 아래 순서대로 한다.

1. **`.env`에 실제 모드 설정**

   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   DEV_MODE=false
   ```

   - `DEV_MODE=false`(또는 미설정)이면 봇이 자동으로 `wins.json`을 읽고 쓴다.
   - `DEV_MODE=true`이면 대신 `wins_dev.json`을 사용하므로, 실제 전적을 쓰려면 반드시 `false`로 둔다.

2. **`data/wins.json`에 6명의 실제 Discord User ID 입력**
   - 처음이라면 아래 형식으로 `data/wins.json`을 새로 만든다 (key는 **실제 Discord User ID**, `total_rounds`는 누적 판수).

     ```json
     {
       "total_rounds": 141,
       "365414320332472332": { "name": "정한솔", "wins": 77 },
       "390449986992865281": { "name": "보링",   "wins": 71 }
     }
     ```

   - User ID 확인: Discord 설정 → 고급 → 개발자 모드 켜기 → 유저 우클릭 → "ID 복사".
   - `total_rounds`와 각 유저의 `wins`는 게임이 끝날 때마다 봇이 자동으로 갱신하므로 처음 한 번만 채워두면 된다.

3. **봇 실행**

   ```bash
   python got_champe.py
   ```

   - 정상 실행 시 콘솔에 `[DEV_MODE] False`가 찍히면 `wins.json` 모드로 동작 중인 것이다.

4. **Discord에서 게임 진행**
   - `/게임시작` → "🚀 챔피언 선택 시작" → 챔피언 선택 → `/승리`로 결과 확정.
   - 결과가 확정되면 `wins.json`의 승수와 `total_rounds`가 자동 저장된다.

> ⚠️ 실제 모드에서는 자기 차례에만 챔피언을 선택할 수 있다(턴제 검증). 또한 정기적으로 `wins.json`을 백업해 두는 것을 권장한다.

### 4. Discord에서 사용
```
/게임시작          # 팀 배정 및 챔피언 제시
🚀 챔피언 선택 시작  # 버튼 클릭하여 게임 시작
(챔피언 버튼 클릭)  # 순서대로 챔피언 선택
/승리              # 승리 팀 선택 후 전적 업데이트
```

---

## 🎮 게임 흐름

1. **`/게임시작`** 명령 실행
   - 6명 선택 (DEV_MODE: wins_dev.json, 실제: 온라인 유저)
   - 랜덤 3:3 팀 배정
   - 픽 순서 계산 (승수 낮은 순)
   - 랜덤 챔피언 8개 제시

2. **"🚀 챔피언 선택 시작" 버튼 클릭**
   - 타이머 시작
   - 첫 번째 플레이어 차례

3. **챔피언 선택**
   - 자기 차례에 챔피언 버튼 클릭
   - 시간 초과 시 자동 랜덤 배정
   - 팀별 색상으로 표시 (🔵/🔴)

4. **모두 선택 완료**
   - "승리한 팀 선택" 드롭다운 표시

5. **`/승리` 또는 드롭다운 선택**
   - 승리 팀 선택
   - 전적 자동 업데이트
   - 오늘의 전적 및 누적 전적 표시

---

## 📈 전적 대시보드

- **보기**: <https://hansoljj.github.io/lol_arena/> 또는 로컬에서 `lol_arena` clone의 `index.html` 더블클릭 (같은 폴더의 `history_data.js`를 읽음)
- **대시보드 원본**: 별도 public repo [`lol_arena`](https://github.com/HANSOLJJ/lol_arena) = GitHub Pages 본체. `index.html`(UI) + `history_data.js`(데이터)만 있음. 봇은 이 repo에 데이터만 push
- **탭**: 개인(행 클릭 → 챔프별 승률, 주력 챔프 TOP5 초상화, 번 돈 정산 승 +5000/패 -5000원) / 2인 시너지 / 3인 시너지 / 챔피언 / 3:3 매치업
- **필터**: 시즌·세션(기간), 인원 선택(탭별 1~3명), 최소 판수 슬라이더, 컬럼 클릭 정렬
- **데이터 갱신**: 봇이 `/승리` 처리 시 자동 (`history_data.json` + `history_data.js`) → **lol_arena repo에 Contents API로 자동 커밋** (GitHub Pages 실시간 반영, `.env`의 `ARENA_GH_*` 설정 필요. 실패해도 봇 동작에 영향 없고 다음 판 업로드 때 자동 만회)
- **UI 수정**: `index.html`은 `lol_arena` repo에서 직접 편집·`git push` (봇 무관)
- **새 시즌**: `data/wins.json` 백업 후 리셋 → 다음 판이 R1로 기록되며 시즌 자동 +1
- **재해복구**: 데이터 파일이 날아가면 `parse_all_history.py`로 디스코드 3채널에서 재파싱 (`data/history_data.json` 재생성)
- **경로 변경**: 모든 데이터/산출물 경로는 `paths.py` 한 곳에서 관리

---

## 🔑 핵심 알고리즘

### 픽 순서 계산
```python
def calculate_pick_order(members):
    """
    승수 낮은 순서대로 정렬
    동률 시 랜덤 섞기
    """
    # 1. 승수별로 그룹화
    # 2. 각 그룹 내 랜덤 섞기
    # 3. 승수 낮은 순으로 합치기
```

### 턴제 검증 (실제 모드)
```python
if not DEV_MODE:
    if interaction.user.id != current_picker.id:
        # 자기 차례 아니면 경고
        return
```

### 타이머 중복 방지
```python
if picker_index != current_pick_index:
    # 다른 사람이 선택 완료하면 타이머 자동 종료
    return
```

---

## 🐛 알려진 이슈 및 해결

### ✅ 해결됨
1. **타이머 오버랩**: index 검증으로 해결
2. **메시지 스팸**: embed 통합 업데이트로 해결
3. **반응 느림**: API 호출 최적화로 해결
4. **팀 고정**: 랜덤 섞기로 해결

### ⚠️ 주의사항
1. **실제 모드 전 `data/wins.json` 확인**
   - 모든 유저의 실제 Discord ID 필요
   - ID 확인: Discord 개발자 모드 → 유저 우클릭 → "ID 복사"

2. **전적 백업**
   - 정기적으로 `data/wins.json` 백업 권장

### 🔧 자주 겪는 오류
- **"Unknown interaction"**: 상호작용 응답(`interaction.response`)을 3초 이내에 호출해야 함
- **자기 차례인데 챔피언이 안 눌림**: 실제 모드는 턴제 검증 — `data/wins.json`의 유저 ID가 실제 ID와 맞는지 확인
- **봇 시작 로그로 모드 확인**: `[DEV_MODE] False` = 실제 모드(`data/wins.json`), `True` = 개발 모드(`data/wins_dev.json`)

---

## 📊 데이터 구조

### 전역 상태
```python
champion_list = []              # 전체 챔피언 리스트
selected_users = {}             # user_id: 선택한 챔피언
pick_order = []                 # 픽 순서 (member 객체)
current_pick_index = 0          # 현재 차례
current_teams = {}              # 팀 구성
overall_results = {}            # 세션 전적
wins_data = {}                  # 영구 전적
game_started = False            # 게임 시작 여부
champion_messages = {}          # {channel_id: message} - 다중 채널 메시지
champion_views = {}             # {channel_id: view} - 다중 채널 View
current_game_channels = []      # 현재 게임 사용 중인 채널 리스트
```

---

## 🔮 향후 개선 가능 사항

1. **통계 명령어 추가**
   - `/전적` - 개인 전적 조회
   - `/랭킹` - 승률 순위

2. **챔피언 제외 기능**
   - 특정 챔피언 제외 리스트

3. **밴픽 모드**
   - 챔피언 밴 단계 추가

4. **다중 서버 지원**
   - 서버별 전적 분리

---

## 📝 라이센스

이 프로젝트는 개인 학습 및 사용 목적으로 제작되었습니다.

---

## 🤝 기여

버그 발견 시 Issues에 제보해주세요!

---

## 📞 문의

프로젝트 관련 문의사항은 Discord 서버에서 문의해주세요.
