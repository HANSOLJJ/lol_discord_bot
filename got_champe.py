##
# @file got_champe.py
# @brief 롤 투기장 3:3 디스코드 봇 본체 (팀 랜덤 배정, 순차 챔피언 픽, 승리 기록).
# @details 온라인 유저(또는 DEV_MODE의 가상 유저) 중 6명을 뽑아 두 팀으로 나누고, 승수 낮은
#          순으로 픽 순서를 정해 순차적으로 랜덤 챔피언을 고르게 한다. 승리 팀을 선택하면
#          wins.json(개인 누적 승수)을 갱신하고 game_recorder.record_game()으로 판을 기록한다.
#          팀짜기/TEAM1/TEAM2 3채널에 결과 embed을 동시 전송한다. DEV_MODE면 wins_dev.json으로
#          테스트를 분리한다. 게임 상태와 공통 게임 함수는 game_core.py에 있고, config의 pick_mode가
#          "activity"면 픽을 디스코드 액티비티(activity_server.py)에서 하고 채널에는 현황판만 둔다.
import discord
import requests
import os
import logging
import asyncio
import functools
import shutil
import time
from discord.ui import View, Button, button
from discord import Interaction, Embed, SelectOption
from discord.ui import Select
from discord.http import Route
from dotenv import load_dotenv
import json
import unicodedata
import paths
from pick_logic import process_pick
from game_recorder import (
    get_current_season,
    start_new_season,
    find_game,
)
from game_core import (
    GameCore,
    MAX_PLAYERS,
    DEFAULT_PICK_TIMEOUT,
    DEFAULT_AUTO_START_SECONDS,
    DEFAULT_PICK_GRACE_SECONDS,
)
from activity_server import ActivityServer, DEFAULT_PORT as DEFAULT_ACTIVITY_PORT

intents = discord.Intents.default()
intents.presences = True
intents.members = True
# py-cord 자동 동기화는 액티비티 Entry Point 명령을 지우려다 Discord에 거절된다. on_ready에서 직접 동기화한다.
bot = discord.Bot(intents=intents, auto_sync_commands=False)

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
# 게임 상태(팀·픽·승수·라운드 등)와 게임 락은 game_core.GameCore가 소유한다. 디스코드 명령·버튼과
# 액티비티 서버가 같은 객체를 쓴다. 저장 함수 save_wins는 아래에서 정의된다.
game = GameCore(dev_mode=DEV_MODE, save_wins=lambda data: save_wins(data))
# 카운트다운은 시계가 아니라 횟수로 센다(show_countdown_step). 한 칸 = 숫자를 1 줄여 그리고, 편집 응답을
# 기다린 뒤, 박자가 찰 때까지(최소 COUNTDOWN_MIN_REST_SECONDS) 쉰다.
# 2026-09-16 실측(게이트웨이 + 웹 클라이언트 DOM 관찰): 디스코드는 1.0초 간격 편집도 하나도 합치지 않고
# 전부 그린다. 숫자가 "빠진 것처럼" 보이는 진짜 원인은 서버가 편집 하나를 가끔 1초 넘게 붙잡았다가 풀어
# 주는 것으로, 시계대로만 보내면 그 직후 다음 편집이 바로 적용돼 앞 숫자가 0.4초만 떠 있다가 넘어간다.
# 그래서 다음 숫자는 직전 편집 응답을 받고 최소 휴식이 지난 뒤에만 보낸다(V1이 문제없던 이유).
DEFAULT_COUNTDOWN_STEP_SECONDS = 1.2  # config.json에 countdown_step_seconds가 없을 때 쓰는 폴백(초)
COUNTDOWN_MIN_REST_SECONDS = 0.8  # 편집 응답을 받은 뒤 다음 숫자까지 최소 휴식(초) = 숫자가 화면에 떠 있는 최소 시간
COUNTDOWN_EDIT_WAIT_SECONDS = 1  # 한 칸에서 편집 응답을 기다리는 최대 시간(초). 느린 채널 하나가 전체를 끝없이 늘리지 않게
# 채널당 편집 최소 간격(초). 틱 사이에 픽 갱신이 끼어도 편집이 몰려 버킷이 바닥나지 않게 한다
# (편집이 끝나자마자 다시 보내 채널당 초당 2~3회가 되면 4초씩 멈췄다, 실측)
CHANNEL_EDIT_MIN_GAP_SECONDS = 0.5
current_timer_task = None  # 현재 실행 중인 타이머 Task
champion_messages = {}  # {channel_id: message} - 여러 채널의 챔피언 선택 메시지(activity 모드는 현황판)
champion_views = {}  # {channel_id: view} - 여러 채널의 View
current_game_channels = []  # 현재 게임에 사용 중인 채널 리스트
victory_messages = []  # [(message, view)] - 띄워둔 승리 드롭다운(처리 후 비활성화용)
embed_update_pending = False  # 아직 화면에 못 민 변경이 있는지
embed_update_task = None  # 화면 갱신을 밀고 있는 태스크
channel_update_latest = {}  # {channel_id: (message, selection_status, description)} - 채널별 아직 못 보낸 최신 갱신
channel_update_tasks = {}  # {channel_id: task} - 채널별 embed 편집 태스크
channel_update_last_at = {}  # {channel_id: 시각} - 채널별 마지막 편집 시작 시각
channel_update_last_sent = {}  # {channel_id: (message, selection_status, description)} - 채널별 마지막으로 보낸 내용
current_pick_deadline = 0  # 현재 차례 마감 시각(유닉스 초). 카운트 중엔 inf, 0에 닿은 순간의 시각으로 확정
current_pick_remaining = 0  # 현재 차례 카운트다운에 표시할 남은 칸(초)
start_remaining = 0  # 자동 시작 카운트다운에 표시할 남은 칸(초). 0이면 카운트다운 중이 아니다
auto_start_task = None  # 자동 시작 카운트다운 태스크


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
            "auto_start_seconds": DEFAULT_AUTO_START_SECONDS,
            "pick_grace_seconds": DEFAULT_PICK_GRACE_SECONDS,
            "countdown_step_seconds": DEFAULT_COUNTDOWN_STEP_SECONDS,
            "champion_count": 8,
            "pick_mode": "embed",  # 운영 봇 픽 방식: "embed"(채널 버튼) | "activity"
            "dev_pick_mode": "activity",  # DEV_MODE 봇 픽 방식
            "channels": ["팀짜기", "TEAM1", "TEAM2"],
        }


##
# @brief 명령 실행 채널 + config.json의 channels에 나열된 채널들을 반환한다.
# @param guild 디스코드 길드(서버) 객체.
# @param command_channel 명령이 실행된 채널(결과 리스트의 첫 번째로 무조건 포함). 액티비티에서
#                        시작한 판처럼 명령 채널이 없으면 None이고, config 채널만 반환한다.
# @return [command_channel, ...config 채널들] 채널 객체 리스트(중복 제거, 이름 대소문자 완전 일치).
def get_game_channels(guild, command_channel):
    channel_names = game.config.get("channels", [])
    # 명령 실행 채널 무조건 포함 (=channels[0])
    channels = [command_channel] if command_channel is not None else []

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
# @details 액티비티는 Data Dragon 영문 ID와 버전으로 초상화를 불러오므로 둘 다 보관한다.
#          판 기록(history_data.json)에는 지금처럼 한국어 이름(name)을 저장한다.
# @return ([{"id": 영문 ID, "name": 챔피언 이름, "image": 이미지 URL}, ...], Data Dragon 버전) 튜플.
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
        champions.append({"id": champ_id, "name": name, "image": image_url})
    return champions, version


# === 팀 확인 헬퍼 ===
##
# @brief 멤버가 어느 팀 소속인지 확인한다(game_core.GameCore.member_team).
# @param member 확인할 멤버 객체.
# @return "team1" 또는 "team2", 없으면 None.
def get_member_team(member):
    return game.member_team(member)


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
        max(get_display_width(member.display_name) for member in game.pick_order)
        if game.pick_order
        else 0
    )

    for i, member in enumerate(game.pick_order):
        team = get_member_team(member)
        check_emoji = "🔵" if team == "team1" else "🔴"

        # 승수 가져오기
        uid_str = str(member.id)
        user_data = game.wins_data.get(uid_str)
        wins = user_data.get("wins", 0) if isinstance(user_data, dict) else 0

        # 이름 폭 기준 패딩 계산 ("--완료" 열 정렬용)
        current_width = get_display_width(member.display_name)
        padding_width = max_name_width - current_width
        padding_count = (padding_width + 1) // 2  # 전각 공백 개수 (전각 1개 = 폭 2)
        name_padding = "　" * padding_count

        if member.id in game.selected_users:
            # 이미 선택 완료 (승수를 3자리로 고정, "--완료"만 간격 조정)
            done = "--완료(자동 배정)" if member.id in game.auto_assigned_users else "--완료"
            status += f"{check_emoji} {member.mention}({wins:3d}승){name_padding}　　　{done}\n"
        else:
            # 선택 대기 중 (승수를 3자리로 고정)
            status += f"{check_emoji} {member.mention}({wins:3d}승)\n"
    return status


##
# @brief 현재 차례 안내 문구를 만든다(남은 칸은 봇이 센 숫자를 텍스트로 박는다).
# @details 디스코드 상대 시각 `<t:...:R>`을 쓰지 않는다. 그건 보는 사람의 PC 시계로
#          렌더링되어 시계가 틀어진 사람은 60초부터 시작하거나 3초 남았는데 초과되는 식으로
#          사람마다 다른 값을 봤다(2026-08-29 실전, docs/COUNTDOWN_ANALYSIS.md).
#          봇이 그리면 전원이 같은 값을 본다. 숫자는 pick_timeout_handler가 한 칸씩 센다.
# @param picker 현재 차례인 멤버.
# @param remaining 표시할 남은 칸(초).
# @return embed description 문자열.
def turn_description(picker, remaining):
    return (
        f"## 현재 차례 - {picker.mention} 님의 차례입니다!\n\n"
        f"## ⏰ 남은 시간: **{remaining}초**"
    )


##
# @brief 자동 시작까지 남은 칸을 안내하는 문구를 만든다.
# @details /게임시작이 처음 그릴 때와 이후 auto_start_handler의 갱신이 같은 함수를 쓰므로
#          첫 화면과 카운트다운이 어긋나지 않는다.
# @param remaining 표시할 남은 칸(초).
# @return embed description 문자열.
def start_countdown_description(remaining):
    return (
        f"## 🚀 준비 완료!\n"
        f"**{game.pick_order[0].mention} 님부터 시작합니다.**\n\n"
        f"## ⏰ {remaining}초 후 자동 시작"
    )


##
# @brief activity 모드 현황판의 안내 문구를 만든다. 남은 시간은 넣지 않는다(매초 편집하지 않는다).
# @return embed description 문자열.
def activity_board_description():
    guide = "아래 **픽 화면 열기** 버튼으로 액티비티에서 챔피언을 고르세요."
    phase = game.visible_phase()
    if phase == "starting":
        return (
            f"## 🚀 준비 완료!\n"
            f"**{game.pick_order[0].mention} 님부터 시작합니다.**\n\n{guide}"
        )
    if phase == "picking":
        picker = game.pick_order[game.current_pick_index]
        return f"## 현재 차례 - {picker.mention} 님의 차례입니다!\n\n{guide}"
    return "## ✅ 모든 선택 완료!"


##
# @brief activity 모드 채널 현황판 embed를 만든다. 제목에 ROUND N, 선택 현황·픽순, TEAM 1·TEAM 2 명단을 담는다.
# @details field 0은 선택 현황이어야 한다. push_channel_embed가 field 0과 description만 바꿔 다시 그린다.
# @return discord.Embed.
def build_activity_board():
    embed = Embed(title=f"🔀 ROUND {game.game_round}: 팀 구성", color=0xFFD700)
    embed.description = activity_board_description()
    embed.add_field(name="선택 현황 및 픽순", value=get_selection_status(), inline=False)
    for key in ["team1", "team2"]:
        team_emoji = "🔵" if key == "team1" else "🔴"
        embed.add_field(
            name=f"{team_emoji} {key.upper()}",
            value="\n".join([m.mention for m in game.current_teams[key]]),
            inline=True,
        )
    return embed


##
# @brief 모든 채널의 챔피언 선택 embed 갱신을 채널별 편집 태스크에 맡긴다.
# @details 편집이 끝나기를 기다리지 않고 바로 돌아온다. 예전엔 3채널 편집을 모두 기다려서,
#          한 채널 응답이 2초씩 걸리면 나머지 채널 카운트다운까지 같이 멈췄다(실측).
#          pick_lock을 잡지 않은 상태에서 호출한다.
# @param selection_status field 0(선택 현황 및 픽순)에 넣을 문자열.
# @param description None이 아니면 embed description도 교체한다.
# @return 없음.
async def broadcast_embed_update(selection_status, description=None):
    for channel_id, message in champion_messages.items():
        channel_update_latest[channel_id] = (message, selection_status, description)
        task = channel_update_tasks.get(channel_id)
        if task is None or task.done():
            channel_update_tasks[channel_id] = asyncio.create_task(
                push_channel_embed(channel_id)
            )


##
# @brief 한 채널의 최신 embed 갱신을 보낸다. 보내는 동안 더 새 갱신이 오면 그것만 이어서 보낸다.
# @details 직전 편집 시작으로부터 CHANNEL_EDIT_MIN_GAP_SECONDS가 지나야 보낸다. 응답이 느린
#          채널은 밀린 중간 상태를 건너뛰고 최신 상태만 보낸다. 직전에 보낸 것과 내용이 같으면
#          아예 보내지 않는다 - 차례가 넘어갈 때 픽 갱신과 새 타이머 첫 칸이 같은 화면을 두 번
#          그리던 것을 막는다.
# @param channel_id 갱신할 채널 ID.
# @return 없음.
async def push_channel_embed(channel_id):
    while channel_id in channel_update_latest:
        wait = (
            channel_update_last_at.get(channel_id, 0)
            + CHANNEL_EDIT_MIN_GAP_SECONDS
            - time.time()
        )
        if wait > 0:
            await asyncio.sleep(wait)
        latest = channel_update_latest.pop(channel_id)
        message, selection_status, description = latest
        if champion_messages.get(channel_id) is not message:
            continue  # 그 사이 새 게임이 시작됐다 - 낡은 갱신을 새 메시지에 쓰지 않는다
        if channel_update_last_sent.get(channel_id) == latest:
            continue  # 화면에 이미 같은 내용이 떠 있다 - 편집을 낭비하지 않는다
        channel_update_last_at[channel_id] = time.time()
        try:
            embed = message.embeds[0].copy()
            if description is not None:
                embed.description = description
            embed.set_field_at(
                0, name="선택 현황 및 픽순", value=selection_status, inline=False
            )
            await message.edit(embed=embed, view=champion_views.get(channel_id))
            channel_update_last_sent[channel_id] = latest  # 실패한 편집은 기록하지 않는다 - 다음에 다시 보낸다
        except Exception:
            pass  # 메시지 삭제됨 등의 에러 무시


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
# @details 전송 간격은 채널별 편집 태스크(push_channel_embed)와 카운트다운 박자(show_countdown_step)가
#          맡는다. 여기서는 현재 상태로 내용을 만들어 넘기기만 한다.
# @return 없음.
async def flush_embed_updates():
    global embed_update_pending

    while embed_update_pending:
        embed_update_pending = False

        if game.mode == "activity":
            # activity 모드 현황판. 카운트다운 숫자는 액티비티가 그리므로 넣지 않는다
            description = activity_board_description()
        elif not game.game_started and start_remaining:
            # 아직 시작 전. 이 분기가 없으면 current_pick_deadline이 0이라 아래 마감 검사에
            # 걸려서 "시간 종료"로 잘못 그려진다
            description = start_countdown_description(start_remaining)
        elif not game.pick_order or game.current_pick_index >= len(game.pick_order):
            description = "## ✅ 모든 선택 완료!"
        elif time.time() >= current_pick_deadline:
            # 0 도달, 유예 중. 이 사이 들어온 클릭도 인정되므로 자동 배정이라고 단정하지 않는다
            # (단정하면 빠른 채널에서는 "자동 배정 중"을 보다가 정상 선택으로 끝나 헷갈린다)
            description = "## ⏰ 시간 종료 - 마지막 선택 확인 중..."
        else:
            description = turn_description(
                game.pick_order[game.current_pick_index], current_pick_remaining
            )

        await broadcast_embed_update(get_selection_status(), description)


##
# @brief 전원 픽 완료 메시지와 승리 팀 선택 View를 모든 게임 채널에 보낸다.
# @details 띄운 드롭다운은 victory_messages에 담아 승리 처리 후 일괄 비활성화할 수 있게 한다.
# @return 없음.
async def send_pick_complete():
    msg = f"{MAX_PLAYERS}명 모두 선택 완료!\n"
    for member in game.pick_order:
        msg += f"- {member.mention}: **{game.selected_users.get(member.id, '❓')}**\n"

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


# === 카운트다운 ===
##
# @brief 카운트다운 한 칸을 그리고, 편집 응답을 기다린 뒤, 박자가 찰 때까지 쉰다.
# @details 평소(왕복 0.3초)에는 한 칸이 정확히 박자(countdown_step_seconds)가 된다. 서버가 편집을
#          붙잡아 응답이 늦으면 그 칸만 늘어나되, 응답 뒤 최소 휴식(COUNTDOWN_MIN_REST_SECONDS)은
#          지켜서 어느 숫자도 화면에 너무 짧게 떠 있지 않게 한다. 응답 대기는 최대
#          COUNTDOWN_EDIT_WAIT_SECONDS까지만 - 한 채널이 2초 넘게 걸려도 전체가 끝없이 멈추지 않는다.
# @return 없음.
async def show_countdown_step():
    step_started = time.time()
    request_embed_update()
    # await task가 아니라 wait로 기다린다 - 픽으로 타이머가 취소될 때 화면 갱신 태스크까지 취소되면 안 된다
    await asyncio.wait([embed_update_task])
    editing = [task for task in channel_update_tasks.values() if not task.done()]
    if editing:
        await asyncio.wait(editing, timeout=COUNTDOWN_EDIT_WAIT_SECONDS)
    await asyncio.sleep(
        max(step_started + countdown_step_seconds() - time.time(), COUNTDOWN_MIN_REST_SECONDS)
    )


##
# @brief 카운트다운 한 칸의 길이(초)를 config에서 읽는다.
# @return countdown_step_seconds 값. 없으면 DEFAULT_COUNTDOWN_STEP_SECONDS.
def countdown_step_seconds():
    return game.config.get("countdown_step_seconds", DEFAULT_COUNTDOWN_STEP_SECONDS)


##
# @brief 한 차례의 선택 타이머를 시작한다. pick_lock 안에서 호출한다.
# @details 마감(inf)과 남은 칸을 태스크보다 먼저 동기적으로 설정한다. 태스크가 돌기 전에 화면 갱신이
#          나가도 이전 차례 값이나 0으로 그려지지 않게 하기 위해서다(시작 직후 시간 초과 오표시, 7567c64).
# @param picker_index 선택할 플레이어의 인덱스.
# @param game_id 현재 게임의 세대 번호.
# @return 없음.
def start_pick_timer(picker_index, game_id):
    global current_pick_deadline, current_pick_remaining, current_timer_task

    current_pick_deadline = float("inf")  # 카운트가 0에 닿기 전에는 시간 때문에 거절하지 않는다
    current_pick_remaining = game.config.get("pick_timeout", DEFAULT_PICK_TIMEOUT)
    current_timer_task = asyncio.create_task(pick_timeout_handler(picker_index, game_id))


# === 개인별 선택 타이머 ===
##
# @brief 개인별 챔피언 선택 타이머를 관리한다.
# @details pick_timeout부터 한 칸씩 세어 내려가고, 0에 닿은 순간을 마감으로 확정한다. 유예 뒤에도
#          선택이 없으면 현재 게임 챔피언 중 랜덤으로 자동 배정한다. 다른 플레이어가 선택을 끝내면
#          취소되거나 index 검증으로 종료된다.
# @param picker_index 현재 선택할 플레이어의 인덱스.
# @param game_id 이 타이머를 건 게임의 세대 번호. 현재 세대와 달라지면(=새 게임 시작) 종료한다.
async def pick_timeout_handler(picker_index, game_id):
    global current_pick_deadline, current_pick_remaining

    try:
        # 1단계: 한 칸씩 세어 내려간다. 칸마다 차례·세대를 확인해, 끝난 차례의 타이머가 다음 차례 숫자를 덮지 않게 한다
        for remaining in range(
            game.config.get("pick_timeout", DEFAULT_PICK_TIMEOUT), 0, -1
        ):
            if picker_index != game.current_pick_index or game_id != game.current_game_id:
                return
            current_pick_remaining = remaining
            await show_countdown_step()
        if picker_index != game.current_pick_index or game_id != game.current_game_id:
            return
        # 0에 닿은 순간이 마감이다. flush가 "시간 종료 - 마지막 선택 확인 중..."으로 바꿔 그린다
        current_pick_deadline = time.time()
        request_embed_update()
        # 2단계: 유예. 늦게 반영된 화면을 보고 누른 클릭과 배달이 늦은 클릭을 기다린다
        await asyncio.sleep(
            game.config.get("pick_grace_seconds", DEFAULT_PICK_GRACE_SECONDS)
        )
    except asyncio.CancelledError:
        # 타이머 취소됨 (정상 선택)
        return

    # 타임아웃 후에도 선택 안했으면 자동 배정.
    # 픽 버튼과 같은 락으로 상태 변경만 직렬화하고, 통신은 락 밖에서 한다.
    assigned = False  # 자동 배정이 실제로 일어났는지
    all_picked = False

    async with game.lock:
        # 락을 기다리는 사이 사람이 이미 골랐을 수 있으므로 재확인한다
        if picker_index != game.current_pick_index or game_id != game.current_game_id:
            return

        # 현재 게임의 챔피언 중 남은 챔피언에서 랜덤 선택 (game_core 공통 함수).
        # 선택 현황에 "(자동 배정)"으로 남는다
        current_picker = game.pick_order[picker_index]
        champ_name = game.auto_assign(picker_index)
        if champ_name is not None:
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

            assigned = True
            all_picked = len(game.selected_users) >= MAX_PLAYERS

            if not all_picked:
                start_pick_timer(game.current_pick_index, game_id)  # 다음 차례 시작

    if not assigned:
        return

    # === 락 밖: 화면 갱신 ===
    # 자동 배정 알림을 채널 메시지로 따로 보내지 않는다 - 메시지가 쌓이면 챔피언 UI가 위로 밀려난다.
    # 선택 현황의 "--완료(자동 배정)" 표시가 게임 끝까지 남는다
    request_embed_update()

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
            if getattr(self, "game_id", game.current_game_id) != game.current_game_id:
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
# @brief 이전 게임의 챔피언 선택 메시지를 종료 상태로 바꾼다(버튼 비활성화 + 종료 표시).
# @details 새 게임이 시작되면 이전 메시지의 버튼과 카운트다운은 의미가 없다. 그런데
#          그냥 두면 이전 판이 아직 진행 중인 것처럼 보인다. 버튼은 제거하지 않고
#          비활성화만 한다 - 색과 라벨(고른 6개는 팀 색, 안 고른 챔피언은 회색)이
#          판 결과 요약으로 남는다.
# @param items 정리할 (메시지, 뷰) 쌍 리스트. 뷰가 None이면 버튼 없이 편집한다.
# @return 없음.
async def close_champion_messages(items):
    # @brief 단일 메시지를 종료 표시로 바꾸고 버튼을 비활성화한다.
    async def close_one(message, view):
        try:
            embed = message.embeds[0].copy()
            embed.description = "## ⏹️ 종료된 게임입니다"
            if view is not None:
                view.disable_all_items()
                view.stop()
            await message.edit(embed=embed, view=view)
        except Exception:
            pass  # 메시지가 지워졌거나 편집 실패해도 무해

    await asyncio.gather(
        *[close_one(message, view) for message, view in items], return_exceptions=True
    )


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


# === 챔피언 선택 자동 시작 ===
##
# @brief 챔피언 선택을 시작한다(알림 방송 + 첫 플레이어 타이머).
# @details 예전엔 시작 버튼 콜백이 하던 일이다. 버튼은 아무나 누를 수 있어서 팀·챔프 카드를
#          보기도 전에 픽이 시작되는 일이 있었고, 지금은 카운트다운이 끝나면 여기로 들어온다.
#          래치와 세대 검증을 락 안에서 함께 해, 카운트다운 중 /게임시작이 다시 실행됐으면
#          낡은 카운트다운이 새 게임을 시작시키지 못한다.
# @param game_id 이 시작을 예약한 게임의 세대 번호.
# @return 없음.
async def begin_champion_select(game_id):
    global start_remaining

    # 임계 구역: 시작 여부·세대 확인과 설정만 (두 번 시작되는 것을 막는다)
    async with game.lock:
        if game.game_started or game_id != game.current_game_id:
            return
        game.game_started = True
        start_remaining = 0
        # 첫 번째 유저 타이머 시작. 시작 플래그와 함께 설정해야 한다 - 아래 알림 전송을 기다리는
        # 사이 화면 갱신이 나가면 마감이 0이라 "시간 종료" 문구로 잘못 그려진다
        start_pick_timer(0, game_id)

    await asyncio.gather(
        *[ch.send("🚀 **챔피언 선택을 시작합니다!**") for ch in current_game_channels],
        return_exceptions=True,
    )
    request_embed_update()


##
# @brief 자동 시작까지 남은 칸을 한 칸씩 세다가, 끝나면 챔피언 선택을 시작한다.
# @details pick_timeout_handler와 같은 박자(show_countdown_step)로 센다. 첫 숫자는 /게임시작 메시지에
#          이미 그려져 있으므로 쉬는 것부터 시작한다.
# @param game_id 이 카운트다운을 건 게임의 세대 번호.
# @param seconds 카운트다운 칸 수. /게임시작 메시지에 처음 그린 숫자와 같다.
# @return 없음.
async def auto_start_handler(game_id, seconds):
    global start_remaining

    try:
        await asyncio.sleep(countdown_step_seconds())
        for remaining in range(seconds - 1, 0, -1):
            if game_id != game.current_game_id:
                return
            start_remaining = remaining
            await show_countdown_step()
    except asyncio.CancelledError:
        return  # 새 게임이 시작돼 취소됨

    await begin_champion_select(game_id)


# === 챔피언 선택 View 클래스 ===
##
# @brief 챔피언 선택 메시지 전용 View. 버튼 상태는 봇이 가진 값을 원본으로 유지한다.
# @details py-cord 2.8은 메시지 편집 응답이 오면 버튼 상태를 응답값(편집을 보낸 시점의 상태)으로
#          덮어쓴다. 카운트다운 편집이 진행 중일 때 픽이 버튼 색을 바꾸면 회색으로 되돌려지므로 막는다.
#          챔피언 버튼의 라벨·색은 봇만 바꾸기 때문에 디스코드 응답으로 덮어쓸 이유가 없다.
class ChampionView(View):

    ##
    # @brief 편집 응답으로 버튼 상태를 덮어쓰지 않는다.
    # @param components 디스코드가 돌려준 컴포넌트 목록 (사용하지 않음).
    # @return 없음.
    def _refresh(self, components):
        pass


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
        self.game_id = game.current_game_id

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
        global current_timer_task

        result = None  # None=거절 / "cancel"=선택 취소 / "pick"=선택 확정
        all_picked = False

        # 마감 전에 누른 클릭인지는 "디스코드가 인터랙션을 접수한 시각"으로 판단한다.
        # 봇이 처리한 시각으로 보면 게이트웨이 배달 지연과 락 대기가 전부 유저 탓이 된다.
        # (인터랙션 ID는 스노플레이크라 접수 시각이 들어 있고, 클라이언트가 못 위조한다)
        clicked_at = discord.utils.snowflake_time(interaction.id).timestamp()

        # === 임계 구역: 상태 판단과 변경만 (디스코드 통신 없음) ===
        async with game.lock:
            current_picker = (
                game.pick_order[game.current_pick_index]
                if 0 <= game.current_pick_index < len(game.pick_order)
                else None
            )
            team = get_member_team(current_picker) if current_picker else None
            team_emoji = "🔵" if team == "team1" else "🔴"
            picker_mention = current_picker.mention if current_picker else ""

            pick_res = process_pick(
                game_started=game.game_started,
                pick_order=game.pick_order,
                current_pick_index=game.current_pick_index,
                selected_users=game.selected_users,
                excluded=game.excluded,
                auto_assigned_users=game.auto_assigned_users,
                user_id=interaction.user.id,
                champ_name=self.champ_name,
                clicked_at=clicked_at,
                current_pick_deadline=current_pick_deadline,
                pick_grace_seconds=game.config.get(
                    "pick_grace_seconds", DEFAULT_PICK_GRACE_SECONDS
                ),
                dev_mode=DEV_MODE,
                max_players=MAX_PLAYERS,
                team_emoji=team_emoji,
                picker_mention=picker_mention,
            )

            game.current_pick_index = pick_res.current_pick_index
            all_picked = pick_res.all_picked
            reply = pick_res.message

            if pick_res.kind == "cancel":
                result = "cancel"
                self.restyle_everywhere(
                    self.champ_name, discord.ButtonStyle.secondary
                )
            elif pick_res.kind == "pick":
                result = "pick"
                if current_timer_task and not current_timer_task.done():
                    current_timer_task.cancel()

                self.restyle_everywhere(
                    f"{team_emoji} {self.champ_name}",
                    (
                        discord.ButtonStyle.primary
                        if team == "team1"
                        else discord.ButtonStyle.danger
                    ),
                )

                if not all_picked:
                    # 다음 차례 시작 (이전 타이머는 위에서 취소했고, index 체크로도 스스로 종료)
                    start_pick_timer(game.current_pick_index, self.game_id)
            elif pick_res.reason == "not_turn" and current_picker:
                reply = f"⚠️ 지금은 **{current_picker.mention}** 님의 차례입니다!"

        # === 락 밖: 응답과 화면 갱신 (클릭끼리 서로 기다리지 않는다) ===
        await interaction.response.send_message(reply, ephemeral=True)

        if result is None:
            return

        request_embed_update()

        if all_picked:
            await send_pick_complete()


# === activity 모드: 현황판과 픽 화면 열기 ===
LAUNCH_ACTIVITY = 12  # 인터랙션 응답 type: 액티비티 실행. py-cord 2.8.1에는 이 응답이 없다


##
# @brief 인터랙션에 LAUNCH_ACTIVITY(type 12)로 응답해 누른 사람의 디스코드에서 액티비티를 연다.
# @details py-cord 2.8.1에 이 응답이 없어 인터랙션 콜백 API를 직접 부른다. 응답은 한 번만 할 수 있으므로
#          py-cord가 이 인터랙션을 응답 완료로 알게 표시한다(이중 응답 방지).
# @param interaction 버튼 인터랙션.
# @return 없음.
async def launch_activity(interaction):
    route = Route(
        "POST",
        "/interactions/{interaction_id}/{interaction_token}/callback",
        interaction_id=interaction.id,
        interaction_token=interaction.token,
    )
    await bot.http.request(route, json={"type": LAUNCH_ACTIVITY})
    interaction.response._responded = True


##
# @brief activity 모드 현황판에 다는 "픽 화면 열기" 버튼 View.
class ActivityLaunchView(View):

    ##
    # @brief 버튼 하나짜리 View를 만든다(시간 제한 없음).
    def __init__(self):
        super().__init__(timeout=None)

    ##
    # @brief 누른 사람에게 액티비티를 연다. 실패하면 이유를 본인에게만 알린다.
    # @param button 눌린 버튼 객체.
    # @param interaction 버튼 클릭 상호작용 객체.
    @button(label="픽 화면 열기", style=discord.ButtonStyle.primary, emoji="🎮")
    async def open_activity(self, button, interaction: Interaction):
        try:
            await launch_activity(interaction)
        except Exception as e:
            print(f"[ERROR] 액티비티 실행 응답 실패: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ 픽 화면을 열지 못했습니다. 채팅 입력창의 앱 버튼으로 열어주세요.",
                    ephemeral=True,
                )


##
# @brief 현황판을 채널들에 보내고 champion_messages에 등록한다(이후 push_channel_embed가 고친다).
# @param channels 보낼 채널 리스트.
# @param ctx /게임시작 컨텍스트. 있으면 첫 채널(명령 채널)은 명령 응답으로 보낸다.
# @return 없음.
async def send_activity_board(channels, ctx=None):
    embed = build_activity_board()

    # @brief 현황판 하나를 보낸다. 실패하면 채널·판·에러 종류를 남긴다.
    async def send_one(channel, respond):
        view = ActivityLaunchView()
        try:
            if respond:
                await ctx.respond(embed=embed, view=view)
                message = await ctx.interaction.original_response()
            else:
                message = await channel.send(embed=embed, view=view)
            champion_messages[channel.id] = message
            champion_views[channel.id] = view
        except Exception as e:
            print(
                f"[ERROR] 현황판 전송 실패 (channel={channel.id}, game={game.game_uid}): "
                f"{type(e).__name__}: {e}"
            )

    await asyncio.gather(
        *[send_one(ch, ctx is not None and i == 0) for i, ch in enumerate(channels)],
        return_exceptions=True,
    )
    if not champion_messages:
        print(f"[WARN] 현황판을 어느 채널에도 보내지 못했습니다 (game={game.game_uid})")


##
# @brief 액티비티에서 온 요청 뒤의 디스코드 작업과 길드 멤버 조회. game.effects에 넣는다.
# @details game_core는 락 밖에서 이 메서드들을 백그라운드 작업으로 부른다(resolve_members만 락 안에서
#          동기로 부른다). 채널 메시지 문구는 디스코드 명령 경로와 같은 함수를 쓴다.
class ActivityEffects:

    ##
    # @brief 액티비티 start의 길드에서 새 판 후보 멤버를 구한다. DEV_MODE면 wins 파일의 가상 유저를 쓴다.
    # @param guild_id SDK가 준 길드 ID 문자열.
    # @return 멤버 리스트. 봇이 들어가 있지 않은 길드면 None.
    def resolve_members(self, guild_id):
        try:
            guild = bot.get_guild(int(guild_id))
        except ValueError:
            return None
        if guild is None:
            return None
        return dev_members() if DEV_MODE else online_members(guild)

    ##
    # @brief 액티비티에서 새 판이 만들어졌을 때 이전 판을 정리하고 팀짜기(config channels)에 현황판을 보낸다.
    # @param guild_id 판을 시작한 길드 ID.
    # @param result game.new_game()의 결과.
    async def game_started(self, guild_id, result):
        global current_game_channels
        await reset_discord_game()
        guild = bot.get_guild(int(guild_id))
        # 명령 채널이 없으므로 config channels로만 보낸다
        current_game_channels = get_game_channels(guild, None) if guild else []
        if result.pool_reset:
            print("[INFO] 챔피언 풀이 소진되어 제외 목록을 초기화했습니다.")
        await send_activity_board(current_game_channels)

    ##
    # @brief 픽·자동 배정·픽 시작 뒤 현황판을 고친다.
    async def board_changed(self):
        request_embed_update()

    ##
    # @brief 액티비티에서 결과를 기록한 뒤 /승리와 같은 결과·오늘의 결과·누적 전적을 보낸다.
    # @param outcome game.record_result_locked()의 성공 결과.
    async def result_recorded(self, outcome):
        await announce_result(outcome)

    ##
    # @brief 액티비티에서 번복한 뒤 /번복과 같은 정정 공지를 보낸다.
    # @param record 번복 전 판 기록 스냅샷.
    async def result_reversed(self, record):
        print(f"[REVERSE] 액티비티 R{record['round']}: {record['winner']} 번복")
        await announce_reverse(record, current_game_channels)


game.effects = ActivityEffects()


# === 새 판 준비 헬퍼 ===
##
# @brief DEV_MODE의 가상 유저 목록을 wins 파일 항목으로 만든다.
# @return MockUser 리스트(total_rounds 제외).
def dev_members():
    # total_rounds 제외하고 유저만 생성
    return [
        MockUser(int(uid), data["name"])
        for uid, data in game.wins_data.items()
        if uid != "total_rounds" and isinstance(data, dict)
    ]


##
# @brief 길드에서 온라인인 일반 사용자(봇 제외) 목록을 만든다.
# @param guild 디스코드 길드 객체.
# @return 멤버 리스트.
def online_members(guild):
    return [
        member
        for member in guild.members
        if not member.bot and member.status != discord.Status.offline
    ]


##
# @brief 새 판이 만들어진 직후 이전 판의 디스코드 쪽 흔적을 정리한다.
# @details 살아있는 embed 타이머를 끊고(취소하지 않으면 이전 게임 타이머가 새 게임에 자동 배정을 쏠 수
#          있다), 승리 드롭다운을 비활성화하고, 이전 챔피언 선택 메시지(activity 모드는 현황판)를 종료
#          표시로 바꾼다. 메시지 정리는 백그라운드로 한다(새 게임 시작을 지연시키지 않는다).
# @return 없음.
async def reset_discord_game():
    global current_timer_task, auto_start_task, start_remaining

    if current_timer_task and not current_timer_task.done():
        current_timer_task.cancel()
    current_timer_task = None
    if auto_start_task and not auto_start_task.done():
        auto_start_task.cancel()
    auto_start_task = None
    start_remaining = 0
    await disable_victory_views()

    old_items = [
        (msg, champion_views.get(cid)) for cid, msg in champion_messages.items()
    ]
    champion_messages.clear()
    champion_views.clear()
    if old_items:
        asyncio.create_task(close_champion_messages(old_items))


# === /게임시작 (기존 팀짜기) ===
##
# @brief /게임시작 슬래시 커맨드. 팀을 나누고 랜덤 챔피언 픽을 준비한다.
# @details 온라인 유저(또는 DEV_MODE의 가상 유저) 중 6명을 뽑아 두 팀으로 나누고, 승수 기반
#          픽 순서를 계산한 뒤 각 채널에 팀 구성 embed과 챔피언 선택 View를 전송한다.
#          픽은 auto_start_seconds 카운트다운이 끝나면 자동으로 시작된다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
@bot.slash_command(name="게임시작", description="팀을 나누고 랜덤 챔피언을 보여줍니다.")
async def 게임시작(ctx):
    global current_game_channels, start_remaining, auto_start_task

    # 봇 시계 진단: 디스코드가 이 커맨드를 접수한 시각과 봇 시계의 차이. 카운트다운과
    # 마감 판정이 봇 시계 기준이므로, 시계가 틀어지면 여기서 먼저 드러난다.
    clock_skew = (
        time.time() - discord.utils.snowflake_time(ctx.interaction.id).timestamp()
    )
    print(f"[CLOCK] 봇 시계 - 디스코드 접수 시각 = {clock_skew:+.2f}s")
    if abs(clock_skew) > 2:
        print(
            "[WARN] 봇 시계가 디스코드와 2초 이상 어긋남 - 호스트 시간 동기화 확인 필요"
        )

    if DEV_MODE:
        # DEV_MODE: wins.json에서 가상 유저 생성
        if not game.wins_data:
            await ctx.respond("⚠️ wins.json 파일이 비어있습니다!", ephemeral=True)
            return

        members = dev_members()
        if len(members) < MAX_PLAYERS:
            await ctx.respond(
                f"⚠️ wins.json에 {MAX_PLAYERS}명 필요 (현재: {len(members)}명)",
                ephemeral=True,
            )
            return
    else:
        # 실제 모드: 온라인 유저 확인
        members = online_members(ctx.guild)

        if len(members) < MAX_PLAYERS:
            await ctx.respond(
                f"⚠️ 온라인 일반 유저가 {MAX_PLAYERS}명 필요", ephemeral=True
            )
            return

    # 게임 상태 초기화와 새 판 만들기 (game_core 공통 함수: 6명 선정, 픽 순서, 팀 분할, 후보 챔피언).
    # 세대를 올려 이전 게임의 버튼·드롭다운·타이머를 무효화한다. 픽 방식은 판을 시작할 때 고정한다
    pick_mode = game.pick_mode()
    async with game.lock:
        new_game = game.new_game(members, pick_mode)
    await reset_discord_game()

    # 게임에 사용할 채널들 먼저 확보 (명령 실행 채널 + config 채널들)
    current_game_channels = get_game_channels(ctx.guild, ctx.channel)
    if not current_game_channels:
        await ctx.channel.send(
            "⚠️ 설정된 채널을 찾을 수 없습니다. config.json을 확인해주세요!"
        )
        return

    if pick_mode == "activity":
        # 채널에는 현황판 하나와 "픽 화면 열기" 버튼만 둔다. 자동 시작과 마감은 game_core 타이머가 맡는다
        if not new_game.ok:
            await ctx.respond(
                f"⚠️ 챔피언 데이터가 부족합니다 (필요 {new_game.champ_count}명). "
                "봇을 재시작하거나 config.json의 champion_count를 확인해주세요!"
            )
            return
        if new_game.pool_reset:
            print("[INFO] 챔피언 풀이 소진되어 제외 목록을 초기화했습니다.")
        await send_activity_board(current_game_channels, ctx)
        return

    embed = Embed(title=f"🔀 ROUND {game.round_counter}: 팀 구성", color=0xFFD700)
    for key in ["team1", "team2"]:
        team_emoji = "🔵" if key == "team1" else "🔴"
        embed.add_field(
            name=f"{team_emoji} {key.upper()}",
            value="\n".join([m.mention for m in game.current_teams[key]]),
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

    # 챔피언 추천은 new_game()이 이미 했다. 풀 소진 안내와 실패 안내만 여기서 보낸다
    champ_count = new_game.champ_count
    if new_game.pool_reset:
        await asyncio.gather(
            *[
                ch.send("♻️ 챔피언 풀이 소진되어 제외 목록을 초기화했습니다.")
                for ch in current_game_channels
            ],
            return_exceptions=True,
        )

    if not new_game.ok:
        # 챔피언 목록 자체가 부족(Data Dragon 로드 실패 등) - 버튼 0개로 진행하지 않는다
        await ctx.channel.send(
            f"⚠️ 챔피언 데이터가 부족합니다 (필요 {champ_count}명). "
            "봇을 재시작하거나 config.json의 champion_count를 확인해주세요!"
        )
        return

    champ_names = [champ["name"] for champ in game.current_game_champions]

    # Embed 생성 - description에 자동 시작 카운트다운
    start_remaining = game.config.get("auto_start_seconds", DEFAULT_AUTO_START_SECONDS)
    embed2 = Embed(title=f"무작위 챔피언 {champ_count}명", color=0x00CCFF)
    embed2.description = start_countdown_description(start_remaining)

    # Field 0: 선택 현황 및 픽순
    embed2.add_field(
        name="선택 현황 및 픽순",
        value=get_selection_status(),
        inline=False,
    )

    # 각 채널에 챔피언 선택 메시지 전송
    for channel in current_game_channels:
        try:
            # View 생성 - 챔피언 버튼들 (각 채널마다 독립적인 View 필요)
            view = ChampionView(timeout=None)
            for champ in champ_names:
                view.add_item(ChampionButton(champ))

            # 메시지 전송
            message = await channel.send(embed=embed2, view=view)

            # 저장
            champion_messages[channel.id] = message
            champion_views[channel.id] = view
        except Exception as e:
            print(f"[ERROR] Failed to send message to channel {channel.name}: {e}")

    if not champion_messages:
        # 버튼이 한 채널에도 안 떴다(권한 없음 등). 자동 시작을 걸면 아무도 못 보는 게임이
        # 혼자 진행되므로 여기서 멈춘다.
        start_remaining = 0
        await ctx.channel.send(
            "⚠️ 챔피언 선택 메시지를 어느 채널에도 보내지 못했습니다. "
            "봇의 채널 권한을 확인해주세요!"
        )
        return

    # 카운트다운이 끝나면 자동으로 챔피언 선택 시작
    auto_start_task = asyncio.create_task(
        auto_start_handler(game.current_game_id, start_remaining)
    )


# === 결과 알림 ===
##
# @brief 기록된 승리 결과를 게임 채널에 알린다(/승리 드롭다운과 액티비티 result 공통).
# @details 시즌 불일치 경고 → (드롭다운이면 누른 사람에게 완료 응답) → 승리 드롭다운 비활성화 → 결과 embed →
#          오늘의 결과 → 누적 전적 순서로 보낸다. 순서와 문구는 예전 /승리와 같다.
# @param outcome game.record_result_locked()의 성공 결과.
# @param followup 드롭다운 상호작용의 followup. 액티비티 요청이면 None.
# @return 없음.
async def announce_result(outcome, followup=None):
    if outcome.season_warning:
        # 잘못된 시즌으로 기록하느니 멈추고 알린다 (승수 저장은 이미 끝났다)
        await asyncio.gather(
            *[ch.send(outcome.season_warning) for ch in current_game_channels],
            return_exceptions=True,
        )

    # @brief 팀 멤버와 픽한 챔피언을 embed용 문자열로 만든다(기록 시점 사본 기준).
    def format_team(key):
        return "\n".join(
            f"{m.mention}: **{outcome.selections.get(m.id, '챔피언 없음')}**"
            for m in outcome.teams[key]
        )

    embed = Embed(title=f"🏆 ROUND {outcome.round} 결과", color=0x44DD88)
    embed.add_field(name="TEAM 1", value=format_team("team1"), inline=True)
    embed.add_field(name="TEAM 2", value=format_team("team2"), inline=True)
    embed.add_field(name="승리 팀", value=f"**{outcome.team_key.upper()}**", inline=False)
    if followup is not None:
        await followup.send(outcome.message, ephemeral=True)

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

    # 전체 전적 출력
    if game.overall_results:
        # 오늘의 결과 섹션
        today_msg = "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        today_msg += "📊 **오늘의 결과**\n"
        today_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for uid, record in game.overall_results.items():
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

        for uid, record in game.overall_results.items():
            # 누적 전적 (wins_data에서)
            uid_str = str(uid)
            user_data = game.wins_data.get(uid_str)
            if isinstance(user_data, dict):
                total_wins = user_data.get("wins", 0)
                total_games = game.wins_data.get("total_rounds", 0)
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
            members = game.current_teams.get(team_key, [])
            champ_list = [game.selected_users.get(m.id, "❓") for m in members]
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
        self.game_id = game.current_game_id

    ##
    # @brief 승리 팀 선택 처리. 전적·wins_data·판 기록을 갱신하고 결과를 방송한다.
    # @details 검증·저장·기록은 game_core 공통 함수(record_result_locked)가 락 안에서 한다. 검증을 전부
    #          통과하고 승수 저장까지 성공해야 victory_processed가 선다. 그 전에 세우면 픽 미완료
    #          상태의 클릭 한 번으로 그 판이 영구 기록불능이 된다.
    # @param interaction 셀렉트 상호작용 객체.
    @interaction_guard(defer=True)
    async def callback(self, interaction: Interaction):
        async with game.lock:
            outcome = game.record_result_locked(self.values[0])

        if outcome.code != "ok":
            # 이미 처리됨·팀 없음·미선택·저장 실패. 저장 실패면 다시 선택해 복구할 수 있다
            await interaction.followup.send(outcome.message, ephemeral=True)
            return

        await announce_result(outcome, interaction.followup)


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
    if not game.current_teams or game.victory_processed:
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
    if not game.wins_data or len(game.wins_data) <= 1:
        await ctx.respond("⚠️ 전적 데이터가 없습니다!", ephemeral=True)
        return

    total_games = game.wins_data.get("total_rounds", 0)

    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📈 **누적 전적**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"총 **{total_games}** 라운드 진행\n\n"

    # 승수 내림차순 정렬
    players = [
        (uid, data)
        for uid, data in game.wins_data.items()
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

        if self.done:
            await interaction.response.send_message(
                "⚠️ 이미 처리 중입니다.", ephemeral=True
            )
            return
        self.done = True

        # 확인을 기다리는 사이 게임이 시작됐을 수 있다
        if game.current_teams:
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
            for uid, data in game.wins_data.items():
                if uid == "total_rounds" or not isinstance(data, dict):
                    continue
                new_wins[uid] = {"name": data.get("name", "???"), "wins": 0}
            save_wins(new_wins)
            game.wins_data = new_wins

            # 3) 시즌 번호 +1. 기존 판 기록은 그대로라 이전 시즌 조회가 계속 가능하다
            new_season = start_new_season(DEV_MODE)

            # 4) 라운드 1부터 재시작
            game.round_counter = 1
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
    name="시즌시작",
    description="현재 시즌을 마감하고 새 시즌을 시작합니다 (전적 초기화).",
)
async def 시즌시작(ctx):
    if game.current_teams:
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


# === 결과 번복 ===
##
# @brief history 판 기록의 한 팀을 embed용 문자열로 만든다(멘션 + 챔피언).
# @param game history_data의 판 dict.
# @param team_key "team1" 또는 "team2".
# @return 줄바꿈으로 이어진 문자열.
def format_recorded_team(game, team_key):
    return "\n".join(
        f"<@{p['id']}>: **{p.get('champ') or '챔피언 없음'}**" for p in game[team_key]
    )


##
# @brief 번복 정정 공지를 채널에 보낸다(/번복 확인 버튼과 액티비티 reverse 공통).
# @param game_record 번복 전 판 기록 스냅샷(winner가 이전 승자).
# @param channels 보낼 채널 리스트.
# @return 없음.
async def announce_reverse(game_record, channels):
    round_num = game_record["round"]
    old_winner = game_record["winner"]
    new_winner = "team2" if old_winner == "team1" else "team1"
    embed = Embed(title=f"🔁 ROUND {round_num} 결과 번복", color=0xFFA500)
    embed.add_field(
        name="TEAM 1", value=format_recorded_team(game_record, "team1"), inline=True
    )
    embed.add_field(
        name="TEAM 2", value=format_recorded_team(game_record, "team2"), inline=True
    )
    embed.add_field(
        name="승리 팀",
        value=f"~~{old_winner.upper()}~~ → **{new_winner.upper()}**",
        inline=False,
    )
    await asyncio.gather(
        *[ch.send(embed=embed) for ch in channels], return_exceptions=True
    )


##
# @brief /번복 확인 UI. 지정 판의 승자를 뒤집고 wins·세션 전적·대시보드를 함께 정정한다.
# @details 원본은 history 판 기록이다(승리 처리 뒤엔 메모리에 지난 판이 없다). 3:3이라 결과는
#          둘 중 하나이므로 번복 = 승자 뒤집기. ephemeral + done 래치로 오클릭·연타를 막는다.
class ReverseConfirmView(View):

    ##
    # @brief 확인 View를 초기화한다(30초 후 자동 만료).
    # @param game 미리보기 시점의 판 기록 스냅샷.
    def __init__(self, game):
        super().__init__(timeout=30)
        self.done = False
        self.game = game

    ##
    # @brief 번복 확정. history → wins 순으로 바꾸고, wins 저장이 실패하면 history를 원복한다.
    # @details 락 안은 동기 파일 쓰기만이라(await 없음) 락을 I/O 위로 잡는 문제가 없다.
    # @param button 눌린 버튼 객체.
    # @param interaction 버튼 클릭 상호작용 객체.
    @button(label="✅ 번복", style=discord.ButtonStyle.danger)
    async def confirm(self, button, interaction: Interaction):
        if self.done:
            await interaction.response.send_message(
                "⚠️ 이미 처리 중입니다.", ephemeral=True
            )
            return
        self.done = True

        self.disable_all_items()
        await interaction.response.edit_message(content="⏳ 번복 처리 중...", view=self)

        round_num = self.game["round"]
        old_winner = self.game["winner"]
        new_winner = "team2" if old_winner == "team1" else "team1"

        try:
            # 판 기록 → 승수 순서로 바꾸고 실패하면 원복한다 (game_core 공통 함수)
            async with game.lock:
                game.reverse_locked(self.game)
        except Exception as e:
            print(f"[ERROR] 번복 실패 R{round_num}: {e}")
            self.stop()
            await interaction.followup.send(
                f"❌ 번복에 실패했습니다: {e}", ephemeral=True
            )
            return

        self.stop()
        print(f"[REVERSE] R{round_num}: {old_winner} -> {new_winner}")
        await interaction.edit_original_response(
            content=f"✅ ROUND {round_num} 결과 번복 완료: **{new_winner.upper()}** 승리",
            view=None,
        )

        # 모든 게임 채널에 정정 공지 (결과 embed과 같은 3채널)
        channels = get_game_channels(interaction.guild, interaction.channel)
        await announce_reverse(self.game, channels)

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
# @brief /번복 슬래시 커맨드. 현재 시즌의 판 하나를 골라 승자 뒤집기 확인 UI를 띄운다.
# @details 현재 시즌만 허용한다. wins.json이 현재 시즌 승수라 지난 시즌은 승수를 못 맞춘다.
#          진행 중인 게임이 있어도 된다 - 지난 판 기록만 건드리고 현재 판 상태와 무관하다.
# @param ctx 슬래시 커맨드 상호작용 컨텍스트.
# @param 라운드 번복할 라운드 번호. 생략하면 현재 시즌의 마지막 판.
@bot.slash_command(
    name="번복", description="기록된 승리 결과를 뒤집습니다 (현재 시즌만)."
)
async def 번복(
    ctx,
    라운드: discord.Option(
        int, "번복할 라운드 번호 (생략하면 마지막 판)", required=False
    ) = None,
):
    game = find_game(라운드, DEV_MODE)
    if game is None:
        season = get_current_season(DEV_MODE)
        if 라운드 is None:
            msg = f"⚠️ 시즌 {season}에 기록된 판이 없습니다."
        else:
            msg = (
                f"⚠️ 시즌 {season}에 R{라운드} 기록이 없습니다.\n"
                f"지난 시즌 판은 승수를 되돌릴 수 없어 번복 대상이 아닙니다."
            )
        await ctx.respond(msg, ephemeral=True)
        return

    old_winner = game["winner"]
    new_winner = "team2" if old_winner == "team1" else "team1"
    await ctx.respond(
        f"🔁 **ROUND {game['round']} 결과 번복**\n\n"
        f"**TEAM 1**\n{format_recorded_team(game, 'team1')}\n\n"
        f"**TEAM 2**\n{format_recorded_team(game, 'team2')}\n\n"
        f"승리 팀: {old_winner.upper()} → **{new_winner.upper()}**\n\n"
        f"정말 바꿀까요?",
        view=ReverseConfirmView(game),
        ephemeral=True,
    )


##
# @brief 슬래시 커맨드를 전역 등록하되 액티비티 Entry Point 명령(Launch)은 유지한다.
# @details py-cord 2.8.1은 Entry Point 명령(type 4)을 몰라 일괄 덮어쓰기 목록에서 빼고, Discord는
#          Entry Point가 빠진 일괄 덮어쓰기를 50240 오류로 거절한다. 그래서 Discord에 등록된 Entry Point를
#          그대로 목록에 포함해 덮어쓴다. 명령 ID를 캐시하지 않아도 py-cord가 이름으로 찾아 실행한다.
async def sync_commands_keeping_entry_point():
    app_id = bot.user.id
    existing = await bot.http.get_global_commands(app_id)
    entry_points = [
        {k: v for k, v in c.items() if k not in ("application_id", "version")}
        for c in existing
        if c["type"] == 4
    ]
    commands = [
        cmd.to_dict()
        for cmd in bot.pending_application_commands
        if cmd.guild_ids is None
    ]
    await bot.http.bulk_upsert_global_commands(app_id, commands + entry_points)


# === 봇 시작 시 챔피언 로드 ===
##
# @brief 봇 준비 완료 이벤트. 챔피언·전적·설정을 로드하고 커맨드를 동기화한다.
# @details round_counter를 total_rounds+1로 초기화한 뒤 슬래시 커맨드를 등록한다.
@bot.event
async def on_ready():
    game.champion_list, game.ddragon_version = fetch_champion_data()
    game.wins_data = load_wins()
    game.config = load_config()

    # round_counter 초기화 (total_rounds + 1)
    game.round_counter = game.wins_data.get("total_rounds", 0) + 1

    await sync_commands_keeping_entry_point()
    print(f"[OK] Bot logged in: {bot.user}")
    print(f"[DEV_MODE] {DEV_MODE}")
    print(f"[WINS] Loaded {len(game.wins_data) - 1} players")  # total_rounds 제외
    print(f"[ROUNDS] Starting from Round {game.round_counter}")
    print(
        f"[CONFIG] pick_timeout={game.config.get('pick_timeout')}s, champion_count={game.config.get('champion_count')}"
        f", pick_mode={game.pick_mode()}"
    )


# === 봇 실행 ===
logging.basicConfig(level=logging.INFO)

# 개발 모드가 운영 봇 계정으로 로그인하지 않도록 운영 토큰으로 대체하지 않는다.
token_key = "DISCORD_TOKEN_DEV" if DEV_MODE else "DISCORD_TOKEN"
token = os.getenv(token_key)
if not token:
    print(f"❌ {token_key}이 .env 파일에 없습니다!")
    exit(1)


##
# @brief 액티비티 서버를 띄운 뒤 봇을 실행하고, 종료(Ctrl+C 포함) 때 봇·액티비티 서버·게임 타이머를 정리한다.
# @details 액티비티 OAuth2 값(DEV_MODE 규칙은 봇 토큰과 같다)이 없거나 포트를 못 열면 경고만 출력하고
#          봇은 그대로 실행한다. on_ready는 재연결 때 다시 불리므로 서버는 여기서 한 번만 띄운다.
async def main():
    suffix = "_DEV" if DEV_MODE else ""
    client_id = os.getenv(f"DISCORD_CLIENT_ID{suffix}")
    client_secret = os.getenv(f"DISCORD_CLIENT_SECRET{suffix}")
    activity = None
    if client_id and client_secret:
        activity = ActivityServer(
            game=game,
            client_id=client_id,
            client_secret=client_secret,
            port=int(os.getenv("ACTIVITY_PORT", DEFAULT_ACTIVITY_PORT)),
        )
        try:
            await activity.start()
        except OSError as e:
            print(f"[WARN] 액티비티 서버를 시작하지 못했습니다: {e}")
            activity = None
    else:
        print(
            f"[WARN] DISCORD_CLIENT_ID{suffix}/DISCORD_CLIENT_SECRET{suffix}가 없어 액티비티 서버를 시작하지 않습니다."
        )
    try:
        # async with는 봇을 이 이벤트 루프에 붙이고, 빠져나갈 때 bot.close()를 부른다
        async with bot:
            await bot.start(token)
    finally:
        if activity is not None:
            await activity.close()
        await game.close()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
