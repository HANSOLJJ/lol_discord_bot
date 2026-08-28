##
# @file got_champe.py
# @brief 롤 투기장 3:3 디스코드 봇 본체 (팀 랜덤 배정, 순차 챔피언 픽, 승리 기록).
# @details 온라인 유저(또는 DEV_MODE의 가상 유저) 중 6명을 뽑아 두 팀으로 나누고, 승수 낮은
#          순으로 픽 순서를 정해 순차적으로 랜덤 챔피언을 고르게 한다. 승리 팀을 선택하면
#          wins.json(개인 누적 승수)을 갱신하고 game_recorder.record_game()으로 판을 기록한다.
#          팀짜기/TEAM1/TEAM2 3채널에 결과 embed을 동시 전송한다. DEV_MODE면 wins_dev.json으로
#          테스트를 분리한다.
import discord
import requests
import random
import os
import logging
import asyncio
import functools
import copy
import shutil
import time
from discord.ui import View, Button, button
from discord import Interaction, Embed, SelectOption
from discord.ui import Select
from dotenv import load_dotenv
import json
import unicodedata
import paths
from game_recorder import (
    record_game,
    get_current_season,
    start_new_season,
    SeasonMismatchError,
)

intents = discord.Intents.default()
intents.presences = True
intents.members = True
bot = discord.Bot(intents=intents)

#  === 환경변수 로드 ===
load_dotenv()
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"


# === Mock User for DEV_MODE ===
##
# @brief DEV_MODE에서 실제 디스코드 멤버 대신 사용하는 가상 유저.
class MockUser:

    ##
    # @brief 가상 유저 속성(id, name, mention 등)을 초기화한다.
    # @param user_id 유저 ID.
    # @param name 유저 이름(display_name/mention에도 사용).
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.mention = f"@{name}"
        self.bot = False

    ##
    # @brief 유저 이름을 문자열로 반환한다.
    # @return 유저 이름 문자열.
    def __str__(self):
        return self.name


# === 전역 상태 ===
champion_list = []
excluded = set()
selected_users = {}  # user_id: champ_name
MAX_PLAYERS = 6
DEFAULT_PICK_TIMEOUT = 20  # config.json에 pick_timeout이 없을 때 쓰는 폴백(초)
# 마감 뒤 자동 배정까지의 유예. 디스코드가 이미 접수한 클릭이 봇까지 배달되는 시간을
# 벌어주기 위한 것이다. 이 구간에 눌러서 통과하는 게 아니라(그건 아래 접수 시각으로 거른다),
# 마감 전에 눌렀는데 아직 도착 못 한 클릭을 기다려 주는 시간이다.
PICK_GRACE_SECONDS = 1.0
# 봇 시계와 디스코드 시계 차이를 감안한 여유. 둘 다 NTP로 맞춰져 있어 보통 훨씬 작다.
CLOCK_TOLERANCE_SECONDS = 0.5
round_counter = 1
current_teams = {}  # {'team1': [member1, ...], 'team2': [member4, ...]}
overall_results = {}  # user_id: {'mention': str, 'results': ["O", "X"]}
wins_data = {}  # user_id: {'name': str, 'wins': int}
pick_order = []  # 픽 순서 (member 객체 리스트)
current_pick_index = 0  # 현재 픽 순서
config = {}  # 설정 (pick_timeout, champion_count, channels)
current_timer_task = None  # 현재 실행 중인 타이머 Task
champion_messages = {}  # {channel_id: message} - 여러 채널의 챔피언 선택 메시지
champion_views = {}  # {channel_id: view} - 여러 채널의 View
current_game_channels = []  # 현재 게임에 사용 중인 채널 리스트
current_game_champions = []  # 현재 게임에서 제시된 챔피언 리스트
game_started = False  # 게임이 시작되었는지 여부 (시작 버튼 눌렀는지)
victory_processed = False  # 승리 처리 완료 여부 (중복 방지)
current_game_id = 0  # 게임 세대 번호(/게임시작마다 +1) - 이전 게임의 버튼·타이머 무효화용
pick_lock = asyncio.Lock()  # 게임 상태 변경 직렬화 (연타·타이머 동시 실행 방지)
victory_messages = []  # [(message, view)] - 띄워둔 승리 드롭다운(처리 후 비활성화용)
embed_update_pending = False  # 아직 화면에 못 민 변경이 있는지
embed_update_task = None  # 화면 갱신을 밀고 있는 태스크
current_pick_deadline = 0  # 현재 차례의 선택 마감 시각(유닉스 초) - embed 카운트다운용


# === 설정 로드 ===
##
# @brief config.json에서 게임 설정을 로드한다.
# @details 파일이 없으면 기본값(pick_timeout=DEFAULT_PICK_TIMEOUT, champion_count=8,
#          channels=[팀짜기,TEAM1,TEAM2])을 반환한다.
# @return pick_timeout(초), champion_count, channels를 담은 dict.
def load_config():
    try:
        with open(paths.CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("[WARNING] config.json not found, using defaults")
        return {
            "pick_timeout": DEFAULT_PICK_TIMEOUT,
            "champion_count": 8,
            "channels": ["팀짜기", "TEAM1", "TEAM2"],
        }


##
# @brief 명령 실행 채널 + config.json의 channels에 나열된 채널들을 반환한다.
# @param guild 디스코드 길드(서버) 객체.
# @param command_channel 명령이 실행된 채널(결과 리스트의 첫 번째로 무조건 포함).
# @return [command_channel, ...config 채널들] 채널 객체 리스트(중복 제거, 이름 대소문자 완전 일치).
def get_game_channels(guild, command_channel):
    channel_names = config.get("channels", [])
    channels = [command_channel]  # 명령 실행 채널 무조건 포함 (=channels[0])

    for name in channel_names:
        # 채널 이름으로 검색 (대소문자 완전 일치)
        channel = discord.utils.get(guild.channels, name=name)
        if channel:
            # 중복 체크 (명령 채널과 같으면 추가 안 함)
            if channel.id not in [ch.id for ch in channels]:
                channels.append(channel)
        else:
            print(f"[WARNING] 채널 '{name}'을 찾을 수 없습니다!")

    return channels


# === 전적 데이터 로드/저장 ===
##
# @brief DEV_MODE에 따라 사용할 전적 파일명을 반환한다.
# @return paths.wins_file() 경로 (data/wins.json 또는 data/wins_dev.json).
def get_wins_file():
    return paths.wins_file(DEV_MODE)


##
# @brief 전적 데이터를 로드한다(DEV_MODE에 따라 파일 선택).
# @details 구조는 {total_rounds: int, user_id: {name, wins}} 형태다. total_rounds가 없으면
#          총 승수를 3으로 나눠(한 판당 3명 승리) 자동 계산해 추가한다. 파일이 없으면 {total_rounds: 0}을 반환한다.
# @return 전적 데이터 dict.
def load_wins():
    filename = get_wins_file()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            # total_rounds가 없으면 계산해서 추가
            if "total_rounds" not in data:
                total_wins = sum(
                    user.get("wins", 0)
                    for uid, user in data.items()
                    if uid != "total_rounds"
                )
                data["total_rounds"] = total_wins // 3  # 한 판당 3명 승리
            return data
    except FileNotFoundError:
        print(f"[WARNING] {filename} not found, returning empty dict")
        return {"total_rounds": 0}


##
# @brief 전적 데이터를 파일에 저장한다(DEV_MODE에 따라 파일 선택).
# @details 임시 파일에 쓴 뒤 os.replace로 교체한다. 쓰기 도중 크래시가 나도 기존 전적이
#          절손되지 않는다.
# @param data 저장할 전적 데이터(load_wins와 동일한 구조).
def save_wins(data):
    filename = get_wins_file()
    tmp_filename = filename + ".tmp"
    with open(tmp_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_filename, filename)
    print(f"[SAVED] Wins data saved to {filename}")


# === 챔피언 데이터 불러오기 ===
##
# @brief Riot Games Data Dragon API에서 챔피언 데이터를 가져온다.
# @return [{"name": 챔피언 이름, "image": 이미지 URL}, ...] 리스트.
def fetch_champion_data():
    version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
    version = requests.get(version_url).json()[0]

    champ_data_url = (
        f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/champion.json"
    )
    champ_data = requests.get(champ_data_url).json()["data"]

    champions = []
    for champ in champ_data.values():
        name = champ["name"]
        champ_id = champ["id"]
        image_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{champ_id}.png"
        champions.append({"name": name, "image": image_url})
    return champions


# === 무작위 챔피언 선택 (제외 리스트 반영) ===
##
# @brief 이미 선택된 챔피언을 제외하고 랜덤으로 챔피언을 뽑는다.
# @param champion_list 전체 챔피언 리스트.
# @param excluded_champs 제외할 챔피언 이름 집합.
# @param count 뽑을 챔피언 수(기본값 8).
# @return 선택된 챔피언 리스트(남은 챔피언이 count보다 적으면 빈 리스트).
def pick_random_champions(champion_list, excluded_champs, count=8):
    available = [
        champ for champ in champion_list if champ["name"] not in excluded_champs
    ]
    if len(available) < count:
        return []
    return random.sample(available, count)


# === 픽 순서 계산 (승수 낮은 순, 동률 시 랜덤) ===
##
# @brief 승리 수 기준으로 픽 순서를 계산한다.
# @details 승수 낮은 순으로 정렬하며(승수가 낮을수록 먼저 픽), 동률이면 랜덤하게 섞는다.
# @param members 픽 순서를 정할 멤버 리스트.
# @return 픽 순서대로 정렬된 멤버 리스트.
def calculate_pick_order(members):
    # 각 멤버의 승수 가져오기
    member_wins = []
    for member in members:
        uid_str = str(member.id)
        user_data = wins_data.get(uid_str)
        wins = user_data.get("wins", 0) if isinstance(user_data, dict) else 0
        member_wins.append((member, wins))

    # 승수별로 그룹화
    from collections import defaultdict

    wins_groups = defaultdict(list)
    for member, wins in member_wins:
        wins_groups[wins].append(member)

    # 각 그룹 내에서 랜덤 섞기
    for wins_count in wins_groups:
        random.shuffle(wins_groups[wins_count])

    # 승수 낮은 순으로 정렬하여 최종 순서 생성
    sorted_wins = sorted(wins_groups.keys())
    final_order = []
    for wins_count in sorted_wins:
        final_order.extend(wins_groups[wins_count])

    return final_order


# === 팀 확인 헬퍼 ===
##
# @brief 멤버가 어느 팀 소속인지 확인한다.
# @param member 확인할 멤버 객체.
# @return "team1" 또는 "team2", 없으면 None.
def get_member_team(member):
    if not current_teams:
        return None
    if member in current_teams.get("team1", []):
        return "team1"
    elif member in current_teams.get("team2", []):
        return "team2"
    return None


# === 문자 폭 계산 (한글/영어 고려) ===
##
# @brief 텍스트의 실제 화면 폭을 계산한다(한글/영어 고려).
# @details 한글·한자·전각 문자는 폭 2, 영어·숫자·반각 문자는 폭 1로 센다.
# @param text 폭을 계산할 문자열.
# @return 화면 폭(정수).
def get_display_width(text):
    width = 0
    for char in text:
        ea_width = unicodedata.east_asian_width(char)
        if ea_width in ("F", "W"):  # Fullwidth, Wide (전각)
            width += 2
        else:  # Halfwidth, Narrow, Ambiguous, Neutral (반각)
            width += 1
    return width


# === 선택 현황 업데이트 ===
##
# @brief 현재 챔피언 선택 현황 문자열을 생성한다.
# @details 팀별 이모지(🔵 team1, 🔴 team2), 각 플레이어 승수, 선택 완료/대기 상태를 표시한다.
# @return 디스코드 메시지로 표시할 선택 현황 문자열.
def get_selection_status():
    status = ""

    # 최대 display_name 폭 계산 (한글/영어 고려)
    max_name_width = (
        max(get_display_width(member.display_name) for member in pick_order)
        if pick_order
        else 0
    )

    for i, member in enumerate(pick_order):
        team = get_member_team(member)
        check_emoji = "🔵" if team == "team1" else "🔴"

        # 승수 가져오기
        uid_str = str(member.id)
        user_data = wins_data.get(uid_str)
        wins = user_data.get("wins", 0) if isinstance(user_data, dict) else 0

        # 이름 폭 기준 패딩 계산 ("--완료" 열 정렬용)
        current_width = get_display_width(member.display_name)
        padding_width = max_name_width - current_width
        padding_count = (padding_width + 1) // 2  # 전각 공백 개수 (전각 1개 = 폭 2)
        name_padding = "　" * padding_count

        if member.id in selected_users:
            # 이미 선택 완료 (승수를 3자리로 고정, "--완료"만 간격 조정)
            status += f"{check_emoji} {member.mention}({wins:3d}승){name_padding}　　　--완료\n"
        else:
            # 선택 대기 중 (승수를 3자리로 고정)
            status += f"{check_emoji} {member.mention}({wins:3d}승)\n"
    return status


##
# @brief 현재 차례 안내 문구를 만든다(남은 시간은 디스코드 상대 시각으로 표시).
# @details `<t:유닉스초:R>`은 각 클라이언트가 스스로 카운트다운하므로 서버가 매초 embed을
#          편집할 필요가 없다. 예전엔 1초마다 채널 수만큼 편집을 날려서 디스코드 편집
#          rate limit을 다 써버렸고, 그 탓에 픽할 때 화면 갱신이 밀렸다.
# @param picker 현재 차례인 멤버.
# @param deadline_ts 선택 마감 시각(유닉스 타임스탬프, 초).
# @return embed description 문자열.
def turn_description(picker, deadline_ts):
    return (
        f"## 현재 차례 - {picker.mention} 님의 차례입니다!\n\n"
        f"## ⏰ 마감 <t:{deadline_ts}:R>"
    )


##
# @brief 지금부터 pick_timeout 초 뒤의 마감 유닉스 타임스탬프를 만든다.
# @details 내림 대신 반올림한다. 내리면 화면 카운트다운이 실제 마감보다 최대 1초 먼저
#          0에 닿아, 다 셌는데 자동 배정이 안 되는 것처럼 보인다.
# @return int 마감 시각(초).
def pick_deadline():
    return round(time.time()) + config.get("pick_timeout", DEFAULT_PICK_TIMEOUT)


##
# @brief 모든 채널의 챔피언 선택 embed을 갱신한다.
# @details pick_lock을 잡지 않은 상태에서 호출한다. 락 안에서 확정해 둔 문자열을 인자로
#          받으므로, 호출 시점에 상태가 더 진행돼 있어도 표시가 뒤섞이지 않는다.
# @param selection_status field 0(선택 현황 및 픽순)에 넣을 문자열.
# @param description None이 아니면 embed description도 교체한다.
#                    (선택 취소 때는 현재 차례 표시를 그대로 둬야 하므로 None을 넘긴다)
# @return 없음.
async def broadcast_embed_update(selection_status, description=None):
    # @brief 단일 채널 embed에 선택 현황(과 description)을 반영한다.
    async def update_one(channel_id, message):
        try:
            embed = message.embeds[0].copy()
            if description is not None:
                embed.description = description
            embed.set_field_at(
                0, name="선택 현황 및 픽순", value=selection_status, inline=False
            )
            await message.edit(embed=embed, view=champion_views.get(channel_id))
        except:
            pass  # 메시지 삭제됨 등의 에러 무시

    await asyncio.gather(
        *[update_one(cid, msg) for cid, msg in champion_messages.items()],
        return_exceptions=True,
    )


##
# @brief 채널 embed 갱신을 예약한다. 연속된 요청은 하나로 합쳐진다.
# @details 픽이 몰아칠 때 중간 상태를 전부 밀어넣으면 디스코드 편집 rate limit에 걸려
#          오히려 화면이 늦게 따라온다. 화면에 필요한 건 마지막 상태뿐이므로 합쳐서 민다.
#          내용은 미는 시점에 현재 상태에서 다시 만든다 — 요청이 어떤 순서로 들어오든
#          화면에 최신 상태가 남게 하기 위해서다(응답 전송이 끼면 요청 순서가 뒤섞인다).
# @return 없음.
def request_embed_update():
    global embed_update_pending, embed_update_task

    embed_update_pending = True
    if embed_update_task is None or embed_update_task.done():
        embed_update_task = asyncio.create_task(flush_embed_updates())


##
# @brief 예약된 embed 갱신을 밀어낸다. 미는 동안 새 요청이 오면 최신 상태로 한 번 더 민다.
# @return 없음.
async def flush_embed_updates():
    global embed_update_pending

    while embed_update_pending:
        embed_update_pending = False

        if pick_order and current_pick_index < len(pick_order):
            description = turn_description(
                pick_order[current_pick_index], current_pick_deadline
            )
        else:
            description = "## ✅ 모든 선택 완료!"

        await broadcast_embed_update(get_selection_status(), description)


##
# @brief 전원 픽 완료 메시지와 승리 팀 선택 View를 모든 게임 채널에 보낸다.
# @details 띄운 드롭다운은 victory_messages에 담아 승리 처리 후 일괄 비활성화할 수 있게 한다.
# @return 없음.
async def send_pick_complete():
    msg = f"{MAX_PLAYERS}명 모두 선택 완료!\n"
    for member in pick_order:
        msg += f"- {member.mention}: **{selected_users.get(member.id, '❓')}**\n"

    # @brief 완료 메시지와 승리 선택 View를 단일 채널에 전송한다.
    async def send_one(channel):
        try:
            await channel.send(msg)
            victory_view = VictoryView()
            victory_msg = await channel.send(
                "🎯 승리한 팀을 선택해주세요:", view=victory_view
            )
            victory_messages.append((victory_msg, victory_view))
        except:
            pass

    await asyncio.gather(
        *[send_one(ch) for ch in current_game_channels], return_exceptions=True
    )


# === 개인별 선택 타이머 ===
##
# @brief 개인별 챔피언 선택 타이머를 관리한다.
# @details 마감까지 기다렸다가, 그때도 선택이 없으면 현재 게임 챔피언 중 랜덤으로 자동
#          배정한다. 남은 시간 표시는 embed의 `<t:...:R>`을 각 클라이언트가 스스로
#          카운트다운하므로 여기서 매초 편집하지 않는다(편집 rate limit 절약).
#          다른 플레이어가 선택을 끝내면 취소되거나 index 검증으로 종료된다.
# @param picker_index 현재 선택할 플레이어의 인덱스.
# @param game_id 이 타이머를 건 게임의 세대 번호. 현재 세대와 달라지면(=새 게임 시작) 종료한다.
# @param deadline_ts 마감 시각(유닉스 초). embed에 표시한 값과 같은 값을 받는다.
#                    실제 자동 배정은 여기에 PICK_GRACE_SECONDS를 더한 시점에 한다.
async def pick_timeout_handler(picker_index, game_id, deadline_ts):
    global selected_users, excluded, current_pick_index, current_timer_task
    global current_pick_deadline

    try:
        await asyncio.sleep(max(0, deadline_ts + PICK_GRACE_SECONDS - time.time()))
    except asyncio.CancelledError:
        # 타이머 취소됨 (정상 선택)
        return

    # 타임아웃 후에도 선택 안했으면 자동 배정.
    # 픽 버튼과 같은 락으로 상태 변경만 직렬화하고, 통신은 락 밖에서 한다.
    assigned = None  # (배정된 챔피언 이름, 팀 이모지) - 배정이 일어났을 때만 채워진다
    all_picked = False

    async with pick_lock:
        # 락을 기다리는 사이 사람이 이미 골랐을 수 있으므로 재확인한다
        if picker_index != current_pick_index or game_id != current_game_id:
            return

        current_picker = pick_order[picker_index]
        if current_picker.id not in selected_users:
            # 현재 게임의 챔피언 중 남은 챔피언에서 랜덤 선택
            available_champs = [
                champ
                for champ in current_game_champions
                if champ["name"] not in excluded
            ]

            if available_champs:
                random_champ = random.choice(available_champs)
                champ_name = random_champ["name"]
                selected_users[current_picker.id] = champ_name
                excluded.add(champ_name)

                # 팀별 버튼 스타일 및 이모지
                team = get_member_team(current_picker)
                team_emoji = "🔵" if team == "team1" else "🔴"
                button_style = (
                    discord.ButtonStyle.primary
                    if team == "team1"
                    else discord.ButtonStyle.danger
                )

                # 모든 채널의 챔피언 버튼 스타일 변경
                for view in champion_views.values():
                    for item in view.children:
                        if (
                            isinstance(item, ChampionButton)
                            and item.champ_name == champ_name
                        ):
                            item.label = f"{team_emoji} {champ_name}"
                            item.style = button_style
                            break

                current_pick_index += 1
                assigned = (champ_name, team_emoji)
                all_picked = len(selected_users) >= MAX_PLAYERS

                if not all_picked:
                    # 다음 차례 시작: 마감 시각을 새로 잡고 타이머를 건다
                    current_pick_deadline = pick_deadline()
                    current_timer_task = asyncio.create_task(
                        pick_timeout_handler(
                            current_pick_index, game_id, current_pick_deadline
                        )
                    )

    if assigned is None:
        return

    # === 락 밖: 화면 갱신과 알림 ===
    champ_name, team_emoji = assigned
    request_embed_update()

    # @brief 시간 초과 자동 배정 알림을 단일 채널에 전송한다.
    async def send_timeout_msg(channel):
        try:
            await channel.send(
                f"⏰ **{current_picker.mention}** 님 시간 초과! "
                f"{team_emoji} **{champ_name}** 자동 배정되었습니다."
            )
        except:
            pass

    await asyncio.gather(
        *[send_timeout_msg(ch) for ch in current_game_channels],
        return_exceptions=True,
    )

    if all_picked:
        await send_pick_complete()


# === 상호작용 공통 가드 ===
##
# @brief 버튼·셀렉트 콜백의 공통 처리(낡은 게임 차단 → 필요 시 ACK → 예외 보고).
# @details 클릭의 "운송"만 책임진다. 상태 보호(pick_lock)는 각 콜백이 자기 임계 구역에만
#          직접 건다 — 디스코드 통신까지 락에 넣으면 연타 시 클릭들이 API 왕복만큼
#          줄줄이 밀리기 때문이다.
# @param defer True면 응답 전에 ACK해 3초 제한을 푼다. 파일 I/O처럼 느린 작업이 있는
#              콜백에만 쓴다. 응답이 한 번 더 왕복하므로 체감 반응이 느려져서, 메모리
#              작업만 하는 콜백(픽 버튼 등)에는 쓰지 않는다.
#              defer=True인 본문은 interaction.followup을, False인 본문은
#              interaction.response를 써야 한다.
def interaction_guard(defer=False):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            if getattr(self, "game_id", current_game_id) != current_game_id:
                await interaction.response.send_message(
                    "⚠️ 이전 게임의 버튼입니다!", ephemeral=True
                )
                return

            if defer:
                await interaction.response.defer(invisible=False, ephemeral=True)

            try:
                await func(self, interaction, *args, **kwargs)
            except Exception as e:
                print(f"[ERROR] {func.__qualname__} 처리 실패: {e}")
                try:
                    msg = f"❌ 처리 중 오류가 발생했습니다: {e}"
                    if interaction.response.is_done():
                        await interaction.followup.send(msg, ephemeral=True)
                    else:
                        await interaction.response.send_message(msg, ephemeral=True)
                except Exception:
                    pass

        return wrapper

    return decorator


##
# @brief 띄워둔 승리 팀 드롭다운을 모두 비활성화한다.
# @details 승리가 확정된 뒤에도 3채널의 드롭다운이 계속 눌리는 것을 막는다. 메시지가
#          지워졌거나 편집에 실패해도 무시한다(정합성은 victory_processed가 담당).
async def disable_victory_views():
    for message, view in victory_messages:
        try:
            view.disable_all_items()
            view.stop()
            await message.edit(view=view)
        except Exception:
            pass
    victory_messages.clear()


# === 시작 버튼 클래스 ===
##
# @brief 게임 시작 버튼. /게임시작 후 수동으로 챔피언 선택을 시작한다.
# @details 클릭 시 타이머를 시작하고 시작 버튼을 모든 채널 View에서 제거한다.
class StartButton(Button):

    ##
    # @brief 시작 버튼 라벨·스타일·custom_id를 설정하고 생성 시점의 게임 세대를 기억한다.
    def __init__(self):
        super().__init__(
            label="🚀 챔피언 선택 시작",
            style=discord.ButtonStyle.success,
            custom_id="start_button",
        )
        self.game_id = current_game_id

    ##
    # @brief 시작 버튼 클릭 처리. 게임을 시작하고 첫 플레이어 타이머를 건다.
    # @param interaction 버튼 클릭 상호작용 객체.
    @interaction_guard()
    async def callback(self, interaction: Interaction):
        global game_started, current_timer_task, current_pick_deadline

        # 임계 구역: 시작 여부 확인과 설정만 (연타로 두 번 시작되는 것을 막는다)
        async with pick_lock:
            already_started = game_started
            game_started = True

        if already_started:
            await interaction.response.send_message(
                "⚠️ 이미 게임이 시작되었습니다!", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🚀 **챔피언 선택을 시작합니다!**", ephemeral=False
        )

        # 클릭 채널을 제외한 나머지 게임 채널에도 시작 알림 전파
        # @brief 클릭 채널 외 나머지 채널에 시작 알림을 전송한다.
        async def send_start_msg(channel):
            try:
                await channel.send("🚀 **챔피언 선택을 시작합니다!**")
            except:
                pass

        await asyncio.gather(
            *[
                send_start_msg(ch)
                for ch in current_game_channels
                if ch.id != interaction.channel.id
            ],
            return_exceptions=True,
        )

        # 모든 채널의 View에서 시작 버튼 제거
        for channel_id, view in champion_views.items():
            for item in view.children[:]:
                if isinstance(item, StartButton):
                    view.remove_item(item)

        # 첫 번째 유저 타이머 시작. 마감 시각은 embed의 카운트다운에 함께 쓰인다
        current_pick_deadline = pick_deadline()
        current_timer_task = asyncio.create_task(
            pick_timeout_handler(0, self.game_id, current_pick_deadline)
        )
        request_embed_update()


# === 챔피언 선택 버튼 클래스 ===
##
# @brief 챔피언 선택 버튼. 챔피언마다 하나씩 생성된다.
# @details 자기 차례에만 선택 가능하며(DEV_MODE 제외), 선택 시 팀별 색상(🔵 team1 파랑, 🔴 team2 빨강)을
#          적용한다. 본인이 고른 챔피언을 재클릭하면 선택이 취소된다.
class ChampionButton(Button):

    ##
    # @brief 챔피언 이름으로 버튼을 초기화하고 생성 시점의 게임 세대를 기억한다.
    # @param champ_name 이 버튼이 나타내는 챔피언 이름.
    def __init__(self, champ_name):
        super().__init__(label=champ_name, style=discord.ButtonStyle.secondary)
        self.champ_name = champ_name
        self.game_id = current_game_id

    ##
    # @brief 모든 채널 View에서 이 챔피언 버튼의 라벨·색을 바꾼다.
    # @param label 새 라벨.
    # @param style 새 버튼 스타일.
    # @return 없음.
    def restyle_everywhere(self, label, style):
        for view in champion_views.values():
            for item in view.children:
                if (
                    isinstance(item, ChampionButton)
                    and item.champ_name == self.champ_name
                ):
                    item.label = label
                    item.style = style
                    break

    ##
    # @brief 챔피언 버튼 클릭 처리. 턴 검증 후 선택/취소하고 다음 차례로 넘긴다.
    # @details 상태 판단·변경만 pick_lock 안에서 하고 디스코드 통신은 락 밖에서 한다.
    #          통신까지 락에 넣으면 연타 시 클릭들이 API 왕복만큼 줄줄이 밀린다.
    #          락이 판단과 기록을 직렬화하므로 늦게 들어온 클릭은 앞선 클릭이 반영된
    #          상태를 보고 정확히 거절된다(직렬화 전에는 첫 클릭이 응답을 기다리는 사이
    #          두 번째 클릭이 끼어들어 챔피언 기록 없이 차례만 넘어갔다).
    # @param interaction 버튼 클릭 상호작용 객체.
    @interaction_guard()
    async def callback(self, interaction: Interaction):
        global selected_users, excluded, current_pick_index, current_timer_task
        global current_pick_deadline

        result = None  # None=거절 / "cancel"=선택 취소 / "pick"=선택 확정
        all_picked = False

        # 마감 전에 누른 클릭인지는 "디스코드가 인터랙션을 접수한 시각"으로 판단한다.
        # 봇이 처리한 시각으로 보면 게이트웨이 배달 지연과 락 대기가 전부 유저 탓이 된다.
        # (인터랙션 ID는 스노플레이크라 접수 시각이 들어 있고, 클라이언트가 못 위조한다)
        clicked_at = discord.utils.snowflake_time(interaction.id).timestamp()

        # === 임계 구역: 상태 판단과 변경만 (디스코드 통신 없음) ===
        async with pick_lock:
            if not game_started:
                reply = "⚠️ 먼저 '🚀 챔피언 선택 시작' 버튼을 눌러주세요!"
            elif not pick_order:
                reply = "⚠️ 먼저 `/게임시작`으로 게임을 시작해주세요!"
            elif current_pick_index >= len(pick_order):
                reply = "⚠️ 모든 선택이 완료되었습니다!"
            else:
                current_picker = pick_order[current_pick_index]

                # 턴제 확인 (DEV_MODE가 아닐 때만)
                if not DEV_MODE and interaction.user.id != current_picker.id:
                    reply = f"⚠️ 지금은 **{current_picker.mention}** 님의 차례입니다!"

                # 마감 뒤에 누른 클릭은 거절한다. 유예는 배달 지연을 기다리는 시간이지
                # 마감을 늘려주는 시간이 아니다.
                elif clicked_at > current_pick_deadline + CLOCK_TOLERANCE_SECONDS:
                    reply = "⏰ 선택 시간이 지났습니다!"

                # 본인이 고른 챔피언 재클릭 = 선택 취소
                elif (
                    current_picker.id in selected_users
                    and selected_users[current_picker.id] == self.champ_name
                ):
                    del selected_users[current_picker.id]
                    excluded.discard(self.champ_name)
                    self.restyle_everywhere(
                        self.champ_name, discord.ButtonStyle.secondary
                    )
                    result = "cancel"
                    reply = f"↩️ **{self.champ_name}** 선택 취소"

                elif self.champ_name in selected_users.values():
                    reply = "⚠️ 이미 선택된 챔피언입니다!"

                elif current_picker.id in selected_users:
                    reply = "⚠️ 이미 챔피언을 선택하셨습니다!"

                else:
                    # 선택 확정
                    if current_timer_task and not current_timer_task.done():
                        current_timer_task.cancel()

                    selected_users[current_picker.id] = self.champ_name
                    excluded.add(self.champ_name)

                    team = get_member_team(current_picker)
                    team_emoji = "🔵" if team == "team1" else "🔴"
                    self.restyle_everywhere(
                        f"{team_emoji} {self.champ_name}",
                        (
                            discord.ButtonStyle.primary
                            if team == "team1"
                            else discord.ButtonStyle.danger
                        ),
                    )

                    current_pick_index += 1
                    result = "pick"
                    reply = f"{team_emoji} **{self.champ_name}** 선택 완료!"
                    all_picked = len(selected_users) >= MAX_PLAYERS

                    if not all_picked:
                        # 다음 차례 시작: 마감 시각을 새로 잡고 타이머를 건다
                        # (이전 타이머는 index 체크로 스스로 종료)
                        current_pick_deadline = pick_deadline()
                        current_timer_task = asyncio.create_task(
                            pick_timeout_handler(
                                current_pick_index, self.game_id, current_pick_deadline
                            )
                        )

        # === 락 밖: 응답과 화면 갱신 (클릭끼리 서로 기다리지 않는다) ===
        await interaction.response.send_message(reply, ephemeral=True)

        if result is None:
            return

        request_embed_update()

        if all_picked:
            await send_pick_complete()


# === /게임시작 (기존 팀짜기) ===
##
# @brief /게임시작 슬래시 커맨드. 팀을 나누고 랜덤 챔피언 픽을 준비한다.
# @details 온라인 유저(또는 DEV_MODE의 가상 유저) 중 6명을 뽑아 두 팀으로 나누고, 승수 기반
#          픽 순서를 계산한 뒤 각 채널에 팀 구성 embed과 챔피언 선택 View를 전송한다.
#          타이머는 시작 버튼을 누를 때까지 시작하지 않는다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
@bot.slash_command(name="게임시작", description="팀을 나누고 랜덤 챔피언을 보여줍니다.")
async def 게임시작(ctx):
    global current_teams, selected_users, pick_order, current_pick_index, current_timer_task
    global champion_messages, champion_views, current_game_champions, game_started, current_game_channels, victory_processed
    global current_game_id

    if DEV_MODE:
        # DEV_MODE: wins.json에서 가상 유저 생성
        if not wins_data:
            await ctx.respond("⚠️ wins.json 파일이 비어있습니다!", ephemeral=True)
            return

        # total_rounds 제외하고 유저만 생성
        members = [
            MockUser(int(uid), data["name"])
            for uid, data in wins_data.items()
            if uid != "total_rounds" and isinstance(data, dict)
        ]
        if len(members) < MAX_PLAYERS:
            await ctx.respond(
                f"⚠️ wins.json에 {MAX_PLAYERS}명 필요 (현재: {len(members)}명)",
                ephemeral=True,
            )
            return
    else:
        # 실제 모드: 온라인 유저 확인
        members = [
            member
            for member in ctx.guild.members
            if not member.bot and member.status != discord.Status.offline
        ]

        if len(members) < MAX_PLAYERS:
            await ctx.respond(
                f"⚠️ 온라인 일반 유저가 {MAX_PLAYERS}명 필요", ephemeral=True
            )
            return

    # 게임 상태 초기화
    # 세대를 올려 이전 게임의 버튼·드롭다운을 무효화하고, 살아있는 타이머를 끊는다.
    # (취소하지 않으면 이전 게임 타이머가 새 게임에 자동 배정을 쏠 수 있다)
    current_game_id += 1
    if current_timer_task and not current_timer_task.done():
        current_timer_task.cancel()
    current_timer_task = None
    await disable_victory_views()
    selected_users.clear()
    game_started = False
    victory_processed = False
    current_pick_index = 0
    champion_messages.clear()
    champion_views.clear()
    half = MAX_PLAYERS // 2

    if DEV_MODE:
        # 테스트 모드: wins.json의 6명 사용
        selected = members[:MAX_PLAYERS]
    else:
        selected = random.sample(members, MAX_PLAYERS)

    # 픽 순서 계산 (승수 기반)
    pick_order = calculate_pick_order(selected)

    # 팀 구성 (랜덤 분할)
    shuffled_for_teams = selected.copy()
    random.shuffle(shuffled_for_teams)
    current_teams = {
        "team1": shuffled_for_teams[:half],
        "team2": shuffled_for_teams[half:],
    }

    # 게임에 사용할 채널들 먼저 확보 (명령 실행 채널 + config 채널들)
    current_game_channels = get_game_channels(ctx.guild, ctx.channel)
    if not current_game_channels:
        await ctx.channel.send(
            "⚠️ 설정된 채널을 찾을 수 없습니다. config.json을 확인해주세요!"
        )
        return

    embed = Embed(title=f"🔀 ROUND {round_counter}: 팀 구성", color=0xFFD700)
    for key in ["team1", "team2"]:
        team_emoji = "🔵" if key == "team1" else "🔴"
        embed.add_field(
            name=f"{team_emoji} {key.upper()}",
            value="\n".join([m.mention for m in current_teams[key]]),
            inline=True,
        )
    # 명령 채널(channels[0])은 respond로, 나머지 채널은 send로 전파
    await ctx.respond(embed=embed)

    async def send_team_embed(channel):
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] 팀 구성 embed 전송 실패 ({channel.name}): {e}")

    await asyncio.gather(
        *[send_team_embed(ch) for ch in current_game_channels[1:]],
        return_exceptions=True,
    )

    # 자동으로 챔피언 추천도 실행
    champ_count = config.get("champion_count", 8)
    picked_champ = pick_random_champions(champion_list, excluded, champ_count)

    if not picked_champ:
        # excluded는 세션 내 챔피언 중복을 막으려고 계속 쌓이기만 해서, 판을 거듭하면
        # 남은 챔피언이 champion_count보다 적어진다. 이때 한 번 비우고 재시도한다.
        excluded.clear()
        picked_champ = pick_random_champions(champion_list, excluded, champ_count)
        if picked_champ:
            await asyncio.gather(
                *[
                    ch.send("♻️ 챔피언 풀이 소진되어 제외 목록을 초기화했습니다.")
                    for ch in current_game_channels
                ],
                return_exceptions=True,
            )

    if not picked_champ:
        # 챔피언 목록 자체가 부족(Data Dragon 로드 실패 등) - 버튼 0개로 진행하지 않는다
        await ctx.channel.send(
            f"⚠️ 챔피언 데이터가 부족합니다 (필요 {champ_count}명). "
            "봇을 재시작하거나 config.json의 champion_count를 확인해주세요!"
        )
        return

    current_game_champions = picked_champ  # 현재 게임 챔피언 저장
    champ_names = [champ["name"] for champ in picked_champ]

    # Embed 생성 - description에 게임 시작 대기 메시지
    embed2 = Embed(title=f"무작위 챔피언 {champ_count}명", color=0x00CCFF)
    embed2.description = (
        f"## 🚀 준비 완료!\n"
        f"**'{pick_order[0].mention}' 님부터 시작합니다.**\n\n"
        f"아래 **'🚀 챔피언 선택 시작'** 버튼을 눌러 게임을 시작하세요!"
    )

    # Field 0: 선택 현황 및 픽순
    embed2.add_field(
        name="선택 현황 및 픽순",
        value=get_selection_status(),
        inline=False,
    )

    # 각 채널에 챔피언 선택 메시지 전송
    for channel in current_game_channels:
        try:
            # View 생성 - 시작 버튼 + 챔피언 버튼들 (각 채널마다 독립적인 View 필요)
            view = View(timeout=None)
            view.add_item(StartButton())  # 시작 버튼 추가
            for champ in champ_names:
                view.add_item(ChampionButton(champ))

            # 메시지 전송
            message = await channel.send(embed=embed2, view=view)

            # 저장
            champion_messages[channel.id] = message
            champion_views[channel.id] = view
        except Exception as e:
            print(f"[ERROR] Failed to send message to channel {channel.name}: {e}")

    # 타이머는 시작 버튼을 누를 때까지 시작하지 않음


# === 승리 셀렉트 ===
##
# @brief 승리한 팀을 고르는 셀렉트 메뉴.
# @details 각 팀 멤버가 고른 챔피언을 라벨에 표시하고, 선택 시 전적·판 기록을 갱신한다.
class VictorySelect(Select):

    ##
    # @brief 양 팀 옵션(팀명 + 픽한 챔피언 목록)을 만들어 셀렉트를 초기화한다.
    # @details 생성 시점의 게임 세대를 기억해 이전 판의 드롭다운 조작을 막는다.
    def __init__(self):
        # @brief 팀 멤버가 고른 챔피언들을 라벨 문자열로 만든다.
        def label_with_champs(team_key):
            members = current_teams.get(team_key, [])
            champ_list = [selected_users.get(m.id, "❓") for m in members]
            champ_text = ", ".join(champ_list)
            return f"TEAM {team_key[-1]} ({champ_text})"

        options = [
            SelectOption(label=label_with_champs("team1"), value="team1"),
            SelectOption(label=label_with_champs("team2"), value="team2"),
        ]
        super().__init__(
            placeholder="승리한 팀을 선택",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.game_id = current_game_id

    ##
    # @brief 승리 팀 선택 처리. 전적·wins_data·판 기록을 갱신하고 결과를 방송한다.
    # @details 검증을 전부 통과한 뒤에야 victory_processed를 세운다. 이 순서가 뒤집히면
    #          픽 미완료 상태의 클릭 한 번으로 그 판이 영구 기록불능이 된다.
    # @param interaction 셀렉트 상호작용 객체.
    @interaction_guard(defer=True)
    async def callback(self, interaction: Interaction):
        global round_counter, current_teams, wins_data, victory_processed

        # === 임계 구역: 검증과 래치만. 통과하면 이 판은 이 클릭이 독점한다 ===
        async with pick_lock:
            if victory_processed:
                problem = "⚠️ 이미 승리 처리가 완료되었습니다!"
            elif not current_teams:
                problem = "⚠️ 먼저 `/게임시작`으로 팀을 구성해주세요!"
            else:
                # 전원이 챔피언을 골랐는지 확인한다 (플래그를 세우기 전에)
                problem = next(
                    (
                        f"❌ {member.mention} 님이 챔피언을 선택하지 않았습니다!"
                        for key in current_teams
                        for member in current_teams[key]
                        if member.id not in selected_users
                    ),
                    None,
                )
                if problem is None:
                    victory_processed = True

        if problem:
            await interaction.followup.send(problem, ephemeral=True)
            return

        # 래치를 잡았으므로 이 아래는 다른 클릭이 들어올 수 없다 (락 불필요)
        team_key = self.values[0]

        # 누적 전적(영구)은 사본에 갱신한 뒤 저장에 성공해야 전역에 반영한다.
        # 저장이 실패했는데 메모리만 올라가면 다음 판부터 승수가 어긋난다.
        new_wins = copy.deepcopy(wins_data)
        for member in current_teams[team_key]:
            uid_str = str(member.id)
            if uid_str in new_wins:
                new_wins[uid_str]["wins"] += 1
            else:
                # 새 유저 추가
                new_wins[uid_str] = {"name": member.display_name, "wins": 1}
        new_wins["total_rounds"] = new_wins.get("total_rounds", 0) + 1

        try:
            save_wins(new_wins)
        except Exception as e:
            victory_processed = False  # 롤백 - 다시 선택해 복구할 수 있게 한다
            print(f"[ERROR] 전적 저장 실패: {e}")
            await interaction.followup.send(
                f"❌ 전적 저장에 실패했습니다. 다시 선택해주세요: {e}", ephemeral=True
            )
            return

        wins_data = new_wins

        # 저장 성공 후에 세션 전적(오늘의 결과)을 반영한다
        for key in current_teams:
            for member in current_teams[key]:
                uid = member.id
                if uid not in overall_results:
                    overall_results[uid] = {"mention": member.mention, "results": []}
                overall_results[uid]["results"].append("O" if key == team_key else "X")

        # 라운드 번호 확정. total_rounds와 사이에 await를 두지 않아 두 카운터가 어긋나지 않는다.
        finished_round = round_counter
        round_counter += 1

        # history_data에 판 기록 (대시보드용) - 실패해도 승리 처리에는 영향 없음
        try:
            season = record_game(
                finished_round,
                {
                    tk: [
                        {
                            "id": str(m.id),
                            "name": m.display_name,
                            "champ": str(selected_users.get(m.id, "")),
                        }
                        for m in current_teams[tk]
                    ]
                    for tk in ("team1", "team2")
                },
                team_key,
                DEV_MODE,
            )
            print(f"[RECORD] history_data: 시즌{season} R{finished_round} 기록 완료")
            # record_game 내부에서 호스팅 SFTP 업로드까지 처리 (백그라운드, 실패해도 무영향)
        except SeasonMismatchError as e:
            # 라운드가 회귀했는데 시즌이 그대로 = wins가 리셋됐는데 /시즌시작을 안 한 상황.
            # 잘못된 시즌으로 기록하느니 멈추고 알린다 (승수 저장은 이미 끝났다).
            print(f"[WARN] history_data 기록 중단: {e}")
            await asyncio.gather(
                *[
                    ch.send(f"⚠️ 판 기록이 중단되었습니다.\n{e}")
                    for ch in current_game_channels
                ],
                return_exceptions=True,
            )
        except Exception as e:
            print(f"[WARN] history_data 기록 실패: {e}")

        # @brief 팀 멤버와 픽한 챔피언을 embed용 문자열로 만든다.
        def format_team(key):
            return "\n".join(
                f"{m.mention}: **{selected_users.get(m.id, '챔피언 없음')}**"
                for m in current_teams[key]
            )

        embed = Embed(title=f"🏆 ROUND {finished_round} 결과", color=0x44DD88)
        embed.add_field(name="TEAM 1", value=format_team("team1"), inline=True)
        embed.add_field(name="TEAM 2", value=format_team("team2"), inline=True)
        embed.add_field(name="승리 팀", value=f"**{team_key.upper()}**", inline=False)
        await interaction.followup.send(
            f"✅ **{team_key.upper()}** 승리 기록 완료!", ephemeral=True
        )

        # 남아있는 승리 드롭다운 비활성화 (3채널에 동시에 떠 있을 수 있다)
        await disable_victory_views()

        # 모든 게임 채널에 결과 embed 전송
        # @brief 결과 embed을 단일 채널에 전송한다.
        async def send_result(channel):
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[ERROR] 결과 embed 전송 실패 ({channel.name}): {e}")

        await asyncio.gather(
            *[send_result(ch) for ch in current_game_channels],
            return_exceptions=True,
        )

        current_teams.clear()

        # 전체 전적 출력
        if overall_results:
            # 오늘의 결과 섹션
            today_msg = "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            today_msg += "📊 **오늘의 결과**\n"
            today_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            for uid, record in overall_results.items():
                results = record["results"]
                today_wins = results.count("O")
                today_losses = results.count("X")
                today_total = len(results)
                today_winrate = (
                    (today_wins / today_total * 100) if today_total > 0 else 0
                )

                today_msg += f"{record['mention']}: **{today_wins}승 {today_losses}패** (승률 **{today_winrate:.1f}%**)\n"

            today_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━"

            # 모든 게임 채널에 오늘의 결과 전송
            today_tasks = [ch.send(today_msg) for ch in current_game_channels]
            await asyncio.gather(*today_tasks, return_exceptions=True)

            # 누적 전적 섹션
            total_msg = "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            total_msg += "📈 **누적 전적**\n"
            total_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            for uid, record in overall_results.items():
                # 누적 전적 (wins_data에서)
                uid_str = str(uid)
                user_data = wins_data.get(uid_str)
                if isinstance(user_data, dict):
                    total_wins = user_data.get("wins", 0)
                    total_games = wins_data.get("total_rounds", 0)
                    total_losses = total_games - total_wins
                    total_winrate = (
                        (total_wins / total_games * 100) if total_games > 0 else 0
                    )
                else:
                    total_wins = 0
                    total_losses = 0
                    total_winrate = 0

                total_msg += f"{record['mention']}: **{total_wins}승 {total_losses}패** (승률 **{total_winrate:.1f}%**)\n"

            total_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━"

            # 모든 게임 채널에 누적 전적 전송
            total_tasks = [ch.send(total_msg) for ch in current_game_channels]
            await asyncio.gather(*total_tasks, return_exceptions=True)


##
# @brief 승리 팀 선택 셀렉트를 담는 View.
class VictoryView(View):

    ##
    # @brief View를 초기화하고 VictorySelect를 추가한다.
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VictorySelect())


##
# @brief /승리 슬래시 커맨드. 해당 라운드의 승리 팀 선택 View를 띄운다.
# @details 진행 중인 게임이 없거나 이미 승리 처리된 판이면 드롭다운을 띄우지 않는다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
@bot.slash_command(name="승리", description="해당 라운드의 승리 팀을 선택합니다.")
async def 승리(ctx):
    if not current_teams or victory_processed:
        await ctx.respond(
            "⚠️ 승리 처리할 게임이 없습니다. 먼저 `/게임시작`을 실행해주세요!",
            ephemeral=True,
        )
        return

    view = VictoryView()
    await ctx.respond("승리한 팀을 선택", view=view)
    try:
        victory_messages.append((await ctx.interaction.original_response(), view))
    except Exception:
        pass  # 메시지 확보 실패는 무해 (비활성화만 못 할 뿐 정합성은 플래그가 담당)


##
# @brief /누적결과 슬래시 커맨드. 전체 누적 전적(승/패/승률)을 출력한다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
@bot.slash_command(name="누적결과", description="전체 누적 전적을 확인합니다.")
async def 누적결과(ctx):
    if not wins_data or len(wins_data) <= 1:
        await ctx.respond("⚠️ 전적 데이터가 없습니다!", ephemeral=True)
        return

    total_games = wins_data.get("total_rounds", 0)

    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📈 **누적 전적**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"총 **{total_games}** 라운드 진행\n\n"

    # 승수 내림차순 정렬
    players = [
        (uid, data)
        for uid, data in wins_data.items()
        if uid != "total_rounds" and isinstance(data, dict)
    ]
    players.sort(key=lambda x: x[1].get("wins", 0), reverse=True)

    for rank, (_uid, data) in enumerate(players, 1):
        name = data.get("name", "???")
        wins = data.get("wins", 0)
        losses = total_games - wins
        winrate = (wins / total_games * 100) if total_games > 0 else 0
        msg += (
            f"**{rank}.** {name}: **{wins}승 {losses}패** (승률 **{winrate:.1f}%**)\n"
        )

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━"

    await ctx.respond(msg)


# === 시즌 시작 ===
##
# @brief /시즌시작 확인 UI. 오클릭 방지용 확인/취소 버튼을 제공한다.
# @details 전적을 초기화하는 되돌리기 어려운 동작이라 확인을 한 단계 둔다. ephemeral로
#          띄우므로 실행자 본인에게만 보이고, done 플래그가 연타를 막는다.
class SeasonConfirmView(View):

    ##
    # @brief 확인 View를 초기화한다(30초 후 자동 만료).
    def __init__(self):
        super().__init__(timeout=30)
        self.done = False

    ##
    # @brief 새 시즌 시작 확정. 승수를 백업·초기화하고 시즌 번호를 올린다.
    # @details 승수 초기화를 먼저, 시즌 번호 갱신을 나중에 한다. 중간에 실패하면 다음
    #          /승리가 SeasonMismatchError로 시끄럽게 멈춰 운영자가 알아차릴 수 있다
    #          (반대 순서면 라운드만 이어지면서 조용히 오염된다).
    # @param button 눌린 버튼 객체.
    # @param interaction 버튼 클릭 상호작용 객체.
    @button(label="✅ 새 시즌 시작", style=discord.ButtonStyle.success)
    async def confirm(self, button, interaction: Interaction):
        global wins_data, round_counter

        if self.done:
            await interaction.response.send_message(
                "⚠️ 이미 처리 중입니다.", ephemeral=True
            )
            return
        self.done = True

        # 확인을 기다리는 사이 게임이 시작됐을 수 있다
        if current_teams:
            self.disable_all_items()
            self.stop()
            await interaction.response.edit_message(
                content="⚠️ 진행 중인 게임이 있어 취소되었습니다.", view=None
            )
            return

        self.disable_all_items()
        await interaction.response.edit_message(
            content="⏳ 시즌 초기화 중...", view=self
        )

        try:
            old_season = get_current_season(DEV_MODE)

            # 1) 현재 승수 백업
            backup_path = paths.season_backup_file(DEV_MODE, old_season)
            wins_path = get_wins_file()
            if os.path.exists(wins_path):
                os.makedirs(paths.BACKUP_DIR, exist_ok=True)
                shutil.copy2(wins_path, backup_path)

            # 2) 승수 초기화. 멤버 항목은 유지한다
            #    (/게임시작이 wins 파일의 항목으로 참가자 목록을 만든다)
            new_wins = {"total_rounds": 0}
            for uid, data in wins_data.items():
                if uid == "total_rounds" or not isinstance(data, dict):
                    continue
                new_wins[uid] = {"name": data.get("name", "???"), "wins": 0}
            save_wins(new_wins)
            wins_data = new_wins

            # 3) 시즌 번호 +1. 기존 판 기록은 그대로라 이전 시즌 조회가 계속 가능하다
            new_season = start_new_season(DEV_MODE)

            # 4) 라운드 1부터 재시작
            round_counter = 1
        except Exception as e:
            print(f"[ERROR] 시즌 초기화 실패: {e}")
            self.stop()
            await interaction.followup.send(
                f"❌ 시즌 초기화에 실패했습니다: {e}", ephemeral=True
            )
            return

        self.stop()
        print(f"[SEASON] 시즌 {new_season} 시작 (백업: {backup_path})")

        await interaction.edit_original_response(
            content=f"✅ **시즌 {new_season}** 시작 완료\n백업: `{backup_path}`",
            view=None,
        )

        # 모든 게임 채널에 공지
        channels = get_game_channels(interaction.guild, interaction.channel)
        await asyncio.gather(
            *[
                ch.send(
                    f"🆕 **시즌 {new_season} 시작!** 전적이 초기화되었습니다.\n"
                    f"이전 시즌 기록은 대시보드에서 계속 볼 수 있습니다."
                )
                for ch in channels
            ],
            return_exceptions=True,
        )

    ##
    # @brief 취소 버튼. 아무것도 바꾸지 않고 확인 UI를 닫는다.
    # @param button 눌린 버튼 객체.
    # @param interaction 버튼 클릭 상호작용 객체.
    @button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, button, interaction: Interaction):
        self.done = True
        self.disable_all_items()
        self.stop()
        await interaction.response.edit_message(content="↩️ 취소되었습니다.", view=None)


##
# @brief /시즌시작 슬래시 커맨드. 현재 시즌을 마감하고 새 시즌을 시작한다.
# @details 승수를 backup/에 보관한 뒤 0으로 초기화하고 라운드를 1부터 다시 센다.
#          예전에는 wins 파일을 직접 지워서 시즌을 넘겼는데, 그러면 파일 유실 사고와
#          구분되지 않아 유령 시즌이 생길 수 있었다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
@bot.slash_command(
    name="시즌시작", description="현재 시즌을 마감하고 새 시즌을 시작합니다 (전적 초기화)."
)
async def 시즌시작(ctx):
    if current_teams:
        await ctx.respond(
            "⚠️ 진행 중인 게임이 있습니다. `/승리`로 마무리한 뒤 실행해주세요!",
            ephemeral=True,
        )
        return

    current = get_current_season(DEV_MODE)
    await ctx.respond(
        f"⚠️ **시즌 {current} 마감 → 시즌 {current + 1} 시작**\n\n"
        f"- 현재 승수를 `backup/`에 백업한 뒤 전원 0승으로 초기화합니다\n"
        f"- 라운드를 1부터 다시 셉니다\n"
        f"- 이전 시즌 기록은 대시보드에서 계속 조회할 수 있습니다\n\n"
        f"정말 진행할까요?",
        view=SeasonConfirmView(),
        ephemeral=True,
    )


# === 봇 시작 시 챔피언 로드 ===
##
# @brief 봇 준비 완료 이벤트. 챔피언·전적·설정을 로드하고 커맨드를 동기화한다.
# @details round_counter를 total_rounds+1로 초기화한 뒤 슬래시 커맨드를 등록한다.
@bot.event
async def on_ready():
    global champion_list, wins_data, config, round_counter
    champion_list = fetch_champion_data()
    wins_data = load_wins()
    config = load_config()

    # round_counter 초기화 (total_rounds + 1)
    round_counter = wins_data.get("total_rounds", 0) + 1

    await bot.sync_commands()
    print(f"[OK] Bot logged in: {bot.user}")
    print(f"[DEV_MODE] {DEV_MODE}")
    print(f"[WINS] Loaded {len(wins_data) - 1} players")  # total_rounds 제외
    print(f"[ROUNDS] Starting from Round {round_counter}")
    print(
        f"[CONFIG] pick_timeout={config.get('pick_timeout')}s, champion_count={config.get('champion_count')}"
    )


# === 봇 실행 ===
logging.basicConfig(level=logging.INFO)

token = os.getenv("DISCORD_TOKEN")
if not token:
    print("❌ DISCORD_TOKEN이 .env 파일에 없습니다!")
    exit(1)

bot.run(token)
