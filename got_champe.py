import discord
import requests
import random
import os
import logging
import asyncio
from discord.ui import View, Button, button
from discord import Interaction, Embed, SelectOption
from discord.ui import Select
from dotenv import load_dotenv
import json
import unicodedata

intents = discord.Intents.default()
intents.presences = True
intents.members = True
bot = discord.Bot(intents=intents)

#  === 환경변수 로드 ===
load_dotenv()
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"


# === Mock User for DEV_MODE ===
class MockUser:
    """DEV_MODE용 가상 유저"""

    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.mention = f"@{name}"
        self.bot = False

    def __str__(self):
        return self.name


# === 전역 상태 ===
champion_list = []
excluded = set()
selected_users = {}  # user_id: champ_name
MAX_PLAYERS = 6
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


# === 설정 로드 ===
def load_config():
    """
    config.json에서 게임 설정 로드

    Returns:
        dict: pick_timeout(초 단위), champion_count, channels 설정값
              파일이 없으면 기본값 반환
    """
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("[WARNING] config.json not found, using defaults")
        return {
            "pick_timeout": 60,
            "champion_count": 8,
            "channels": {"team1": "team1", "team2": "team2"},
        }


def get_game_channels(guild, command_channel):
    """
    명령 실행 채널 + config에 설정된 team 채널들을 반환

    Args:
        guild: Discord 길드(서버) 객체
        command_channel: 명령이 실행된 채널

    Returns:
        list: [command_channel, team1_channel, team2_channel] 채널 객체 리스트
              중복 제거됨
    """
    channel_config = config.get("channels", {})
    channels = [command_channel]  # 명령 실행 채널 무조건 포함

    for key in ["team1", "team2"]:
        channel_name = channel_config.get(key)
        if channel_name:
            # 채널 이름으로 검색
            channel = discord.utils.get(guild.channels, name=channel_name)
            if channel:
                # 중복 체크 (명령 채널과 같으면 추가 안 함)
                if channel.id not in [ch.id for ch in channels]:
                    channels.append(channel)
            else:
                print(f"[WARNING] 채널 '{channel_name}' ({key})을 찾을 수 없습니다!")
        else:
            print(f"[WARNING] config.json에 '{key}' 채널 설정이 없습니다!")

    return channels


# === 전적 데이터 로드/저장 ===
def get_wins_file():
    """
    DEV_MODE에 따라 적절한 전적 파일명 반환

    Returns:
        str: "wins_dev.json" (DEV_MODE=true) 또는 "wins.json" (DEV_MODE=false)
    """
    return "wins_dev.json" if DEV_MODE else "wins.json"


def load_wins():
    """
    전적 데이터 로드 (DEV_MODE에 따라 파일 선택)

    구조:
        {
            "total_rounds": int,  # 총 게임 판수
            "user_id": {
                "name": str,      # 유저 닉네임
                "wins": int       # 승리 횟수
            }
        }

    Returns:
        dict: 전적 데이터. total_rounds가 없으면 자동 계산하여 추가
    """
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


def save_wins(data):
    """
    전적 데이터 저장 (DEV_MODE에 따라 파일 선택)

    Args:
        data (dict): 저장할 전적 데이터 (load_wins와 동일한 구조)
    """
    filename = get_wins_file()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] Wins data saved to {filename}")


# === 챔피언 데이터 불러오기 ===
def fetch_champion_data():
    """
    Riot Games Data Dragon API에서 챔피언 데이터를 가져옴

    Returns:
        list: [{"name": 챔피언 이름, "image": 이미지 URL}, ...]
    """
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
def pick_random_champions(champion_list, excluded_champs, count=8):
    """
    이미 선택된 챔피언을 제외하고 랜덤으로 챔피언 선택

    Args:
        champion_list (list): 전체 챔피언 리스트
        excluded_champs (set): 제외할 챔피언 이름 집합
        count (int): 선택할 챔피언 수 (기본값: 8)

    Returns:
        list: 선택된 챔피언 리스트 (부족하면 빈 리스트)
    """
    available = [
        champ for champ in champion_list if champ["name"] not in excluded_champs
    ]
    if len(available) < count:
        return []
    return random.sample(available, count)


# === 픽 순서 계산 (승수 낮은 순, 동률 시 랜덤) ===
def calculate_pick_order(members):
    """
    승리 수 기준 픽 순서 계산
    - 승수 낮은 순서대로 정렬 (승수가 낮을수록 먼저 선택)
    - 동률일 경우 랜덤하게 섞음

    Args:
        members (list): 픽 순서를 정할 멤버 리스트

    Returns:
        list: 픽 순서대로 정렬된 멤버 리스트
    """
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
def get_member_team(member):
    """
    멤버가 어느 팀인지 확인

    Args:
        member: 확인할 멤버 객체

    Returns:
        str: "team1" 또는 "team2", 없으면 None
    """
    if not current_teams:
        return None
    if member in current_teams.get("team1", []):
        return "team1"
    elif member in current_teams.get("team2", []):
        return "team2"
    return None


# === 문자 폭 계산 (한글/영어 고려) ===
def get_display_width(text):
    """
    텍스트의 실제 화면 폭 계산
    - 한글, 한자, 전각 문자: 폭 2
    - 영어, 숫자, 반각 문자: 폭 1
    """
    width = 0
    for char in text:
        ea_width = unicodedata.east_asian_width(char)
        if ea_width in ("F", "W"):  # Fullwidth, Wide (전각)
            width += 2
        else:  # Halfwidth, Narrow, Ambiguous, Neutral (반각)
            width += 1
    return width


# === 선택 현황 업데이트 ===
def get_selection_status():
    """
    현재 선택 현황 문자열 생성
    - 팀별 이모지 표시 (🔵 team1, 🔴 team2)
    - 각 플레이어의 승수 표시
    - 선택 완료/진행 중/대기 중 상태 표시

    Returns:
        str: Discord 메시지로 표시할 선택 현황 문자열
    """
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


async def update_champion_message():
    """
    모든 채널의 챔피언 선택 메시지 embed를 업데이트 (병렬 처리)
    - Description: 현재 차례 플레이어 + 남은 시간 (큰 폰트 강조)
    - Field 1: 선택 현황 및 픽순 (get_selection_status)

    Note:
        Discord embed의 description은 일반 field보다 폰트가 크게 표시됨
        asyncio.gather()로 모든 채널을 동시에 업데이트하여 지연 최소화
    """
    if not champion_messages or not pick_order:
        return

    # Description 및 필드 값 미리 계산 (모든 채널에 동일하게 적용)
    if current_pick_index < len(pick_order):
        current_picker = pick_order[current_pick_index]
        timeout_val = config.get("pick_timeout", 15)
        description = (
            f"## 현재 차례 - {current_picker.mention} 님의 차례입니다!\n\n"
            f"## ⏰ 남은 시간: **{timeout_val}초**"
        )
    else:
        description = "## ✅ 모든 선택 완료!"

    selection_status = get_selection_status()

    # 각 채널 업데이트 태스크 생성
    async def update_single_channel(channel_id, message):
        try:
            embed = message.embeds[0].copy()  # embed 복사하여 독립적으로 수정
            embed.description = description
            embed.set_field_at(
                0,  # 선택 현황 필드
                name="선택 현황 및 픽순",
                value=selection_status,
                inline=False,
            )
            view = champion_views.get(channel_id)
            await message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"[ERROR] Failed to update message in channel {channel_id}: {e}")

    # 모든 채널 동시 업데이트 (병렬 처리)
    tasks = [update_single_channel(cid, msg) for cid, msg in champion_messages.items()]
    await asyncio.gather(*tasks, return_exceptions=True)


# === 개인별 선택 타이머 ===
async def pick_timeout_handler(picker_index):
    """
    개인별 챔피언 선택 타이머 관리
    - 매 1초마다 남은 시간을 모든 채널의 embed에 업데이트
    - 시간 초과 시 현재 게임 챔피언에서 랜덤 자동 배정
    - 다른 플레이어가 선택 완료하면 타이머 자동 종료 (index 검증)

    Args:
        picker_index (int): 현재 선택할 플레이어의 인덱스
    """
    global selected_users, excluded, current_pick_index, current_timer_task

    timeout = config.get("pick_timeout", 15)
    update_interval = 1
    elapsed = 0

    try:
        while elapsed < timeout:
            remaining = timeout - elapsed

            # 이 타이머가 여전히 현재 차례인지 확인
            if picker_index != current_pick_index:
                # 이미 다음 차례로 넘어갔으면 타이머 종료
                return

            # 모든 채널의 메시지 업데이트 (남은 시간 표시) - 병렬 처리
            if champion_messages and pick_order and picker_index < len(pick_order):
                current_picker = pick_order[picker_index]
                description = (
                    f"## 현재 차례 - {current_picker.mention} 님의 차례입니다!\n\n"
                    f"## ⏰ 남은 시간: **{remaining}초**"
                )

                async def update_timer(channel_id, message):
                    try:
                        embed = message.embeds[0].copy()
                        embed.description = description
                        # 선택 현황도 함께 업데이트 (선택 완료 상태 반영)
                        embed.set_field_at(
                            0,
                            name="선택 현황 및 픽순",
                            value=get_selection_status(),
                            inline=False,
                        )
                        view = champion_views.get(channel_id)
                        await message.edit(embed=embed, view=view)
                    except:
                        pass  # 메시지 삭제됨 등의 에러 무시

                tasks = [
                    update_timer(cid, msg) for cid, msg in champion_messages.items()
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(update_interval)
            elapsed += update_interval

    except asyncio.CancelledError:
        # 타이머 취소됨 (정상 선택)
        return

    # 타임아웃 후에도 선택 안했으면 자동 배정
    # 이 타이머가 여전히 현재 차례인지 재확인
    if picker_index != current_pick_index:
        return

    current_picker = pick_order[picker_index]
    if current_picker.id not in selected_users:
        # 현재 게임의 챔피언 중 남은 챔피언에서 랜덤 선택
        available_champs = [
            champ for champ in current_game_champions if champ["name"] not in excluded
        ]

        if available_champs:
            random_champ = random.choice(available_champs)
            selected_users[current_picker.id] = random_champ["name"]
            excluded.add(random_champ["name"])

            # 팀별 버튼 스타일 및 이모지
            team = get_member_team(current_picker)
            team_emoji = "🔵" if team == "team1" else "🔴"
            button_style = (
                discord.ButtonStyle.primary
                if team == "team1"
                else discord.ButtonStyle.danger
            )

            # 모든 채널의 챔피언 버튼 스타일 변경
            for channel_id, view in champion_views.items():
                for item in view.children:
                    if (
                        isinstance(item, ChampionButton)
                        and item.champ_name == random_champ["name"]
                    ):
                        item.label = f"{team_emoji} {random_champ['name']}"
                        item.style = button_style
                        break

            # current_pick_index 증가 (embed 업데이트 전에 먼저 증가)
            current_pick_index += 1

            # 버튼 변경사항을 즉시 Discord에 반영 (타임아웃 메시지 전에 먼저 업데이트)
            await update_champion_message()

            # 모든 채널에 타임아웃 메시지 전송 (병렬 처리)
            async def send_timeout_msg(channel):
                try:
                    await channel.send(
                        f"⏰ **{current_picker.mention}** 님 시간 초과! "
                        f"{team_emoji} **{random_champ['name']}** 자동 배정되었습니다."
                    )
                except:
                    pass

            await asyncio.gather(
                *[send_timeout_msg(ch) for ch in current_game_channels],
                return_exceptions=True,
            )

            # 모두 선택 완료
            if len(selected_users) >= MAX_PLAYERS:
                msg = f"{MAX_PLAYERS}명 모두 선택 완료!\n"
                for member in pick_order:
                    champ = selected_users.get(member.id, "❓")
                    msg += f"- {member.mention}: **{champ}**\n"

                # 모든 채널에 완료 메시지 전송 (병렬 처리)
                async def send_complete_msg(channel):
                    try:
                        await channel.send(msg)
                        await channel.send(
                            "🎯 승리한 팀을 선택해주세요:", view=VictoryView()
                        )
                    except:
                        pass

                await asyncio.gather(
                    *[send_complete_msg(ch) for ch in current_game_channels],
                    return_exceptions=True,
                )
            else:
                # 다음 유저 타이머 시작
                current_timer_task = asyncio.create_task(
                    pick_timeout_handler(current_pick_index)
                )


# === 시작 버튼 클래스 ===
class StartButton(Button):
    """
    게임 시작 버튼
    - /게임시작 명령 후 수동으로 챔피언 선택 시작
    - 클릭 시 타이머 시작 및 버튼 자동 제거
    """

    def __init__(self):
        super().__init__(
            label="🚀 챔피언 선택 시작",
            style=discord.ButtonStyle.success,
            custom_id="start_button",
        )

    async def callback(self, interaction: Interaction):
        global game_started, current_timer_task

        if game_started:
            await interaction.response.send_message(
                "⚠️ 이미 게임이 시작되었습니다!", ephemeral=True
            )
            return

        # 게임 시작
        game_started = True

        await interaction.response.send_message(
            "🚀 **챔피언 선택을 시작합니다!**", ephemeral=False
        )

        # 모든 채널의 View에서 시작 버튼 제거
        for channel_id, view in champion_views.items():
            for item in view.children[:]:
                if isinstance(item, StartButton):
                    view.remove_item(item)

        # Embed description 업데이트 (첫 번째 플레이어 차례)
        timeout_val = config.get("pick_timeout", 15)
        description = (
            f"## 현재 차례 - {pick_order[0].mention} 님의 차례입니다!\n\n"
            f"## ⏰ 남은 시간: **{timeout_val}초**"
        )

        # 모든 채널의 메시지 업데이트 (병렬 처리)
        async def update_start(channel_id, message):
            try:
                embed = message.embeds[0].copy()
                embed.description = description
                view = champion_views.get(channel_id)
                await message.edit(embed=embed, view=view)
            except:
                pass

        tasks = [update_start(cid, msg) for cid, msg in champion_messages.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 첫 번째 유저 타이머 시작
        current_timer_task = asyncio.create_task(pick_timeout_handler(0))


# === 챔피언 선택 버튼 클래스 ===
class ChampionButton(Button):
    """
    챔피언 선택 버튼
    - 각 챔피언마다 버튼 생성
    - 턴제 검증: 자기 차례에만 선택 가능 (DEV_MODE 제외)
    - 선택 시 팀별 색상 적용 (🔵 team1 파란색, 🔴 team2 빨간색)
    - 선택 취소 가능 (본인이 선택한 챔피언 재클릭)
    """

    def __init__(self, champ_name):
        super().__init__(label=champ_name, style=discord.ButtonStyle.secondary)
        self.champ_name = champ_name

    async def callback(self, interaction: Interaction):
        global selected_users, excluded, current_pick_index, current_timer_task

        # 게임 시작 확인
        if not game_started:
            await interaction.response.send_message(
                "⚠️ 먼저 '🚀 챔피언 선택 시작' 버튼을 눌러주세요!",
                ephemeral=True,
            )
            return

        # 픽 순서 확인
        if not pick_order:
            await interaction.response.send_message(
                "⚠️ 먼저 `/게임시작`으로 게임을 시작해주세요!", ephemeral=True
            )
            return

        if current_pick_index >= len(pick_order):
            await interaction.response.send_message(
                "⚠️ 모든 선택이 완료되었습니다!", ephemeral=True
            )
            return

        current_picker = pick_order[current_pick_index]

        # 턴제 확인 (DEV_MODE가 아닐 때만)
        if not DEV_MODE:
            if interaction.user.id != current_picker.id:
                await interaction.response.send_message(
                    f"⚠️ 지금은 **{current_picker.mention}** 님의 차례입니다!",
                    ephemeral=True,
                )
                return

        # 선택 취소 로직 (현재 차례인 사람만 가능)
        if (
            current_picker.id in selected_users
            and selected_users[current_picker.id] == self.champ_name
        ):
            del selected_users[current_picker.id]
            excluded.discard(self.champ_name)

            # 모든 채널의 버튼 스타일 초기화
            for channel_id, view in champion_views.items():
                for item in view.children:
                    if (
                        isinstance(item, ChampionButton)
                        and item.champ_name == self.champ_name
                    ):
                        item.label = self.champ_name
                        item.style = discord.ButtonStyle.secondary
                        break

            # 먼저 interaction에 응답
            await interaction.response.send_message(
                f"↩️ **{self.champ_name}** 선택 취소",
                ephemeral=True,
            )

            # 모든 채널의 embed 업데이트 (병렬 처리)
            selection_status = get_selection_status()

            async def update_cancel(channel_id, message):
                try:
                    embed = message.embeds[0].copy()
                    embed.set_field_at(
                        0,
                        name="선택 현황 및 픽순",
                        value=selection_status,
                        inline=False,
                    )
                    view = champion_views.get(channel_id)
                    await message.edit(embed=embed, view=view)
                except:
                    pass

            tasks = [update_cancel(cid, msg) for cid, msg in champion_messages.items()]
            await asyncio.gather(*tasks, return_exceptions=True)
            return

        # 이미 선택된 챔피언
        if self.champ_name in selected_users.values():
            await interaction.response.send_message(
                "⚠️ 이미 선택된 챔피언입니다!", ephemeral=True
            )
            return

        # 현재 차례 유저가 이미 선택했는지 확인
        if current_picker.id in selected_users:
            await interaction.response.send_message(
                "⚠️ 이미 챔피언을 선택하셨습니다!", ephemeral=True
            )
            return

        # 현재 타이머 취소
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()

        # 챔피언 선택
        selected_users[current_picker.id] = self.champ_name
        excluded.add(self.champ_name)

        # 팀별 버튼 색상 및 이모지
        team = get_member_team(current_picker)
        team_emoji = "🔵" if team == "team1" else "🔴"
        button_style = (
            discord.ButtonStyle.primary
            if team == "team1"
            else discord.ButtonStyle.danger
        )

        # 모든 채널의 버튼 스타일 변경
        for channel_id, view in champion_views.items():
            for item in view.children:
                if (
                    isinstance(item, ChampionButton)
                    and item.champ_name == self.champ_name
                ):
                    item.label = f"{team_emoji} {self.champ_name}"
                    item.style = button_style
                    break

        # 먼저 interaction에 응답 (3초 내) - 본인에게만 보임
        await interaction.response.send_message(
            f"{team_emoji} **{self.champ_name}** 선택 완료!",
            ephemeral=True,
        )

        # 다음 차례로 이동
        current_pick_index += 1

        # Description 및 선택 현황 미리 계산
        if current_pick_index < len(pick_order):
            next_picker = pick_order[current_pick_index]
            timeout_val = config.get("pick_timeout", 15)
            description = (
                f"## 현재 차례 - {next_picker.mention} 님의 차례입니다!\n\n"
                f"## ⏰ 남은 시간: **{timeout_val}초**"
            )
        else:
            description = "## ✅ 모든 선택 완료!"

        selection_status = get_selection_status()

        # 모든 채널의 embed 업데이트 (병렬 처리)
        async def update_pick(channel_id, message):
            try:
                embed = message.embeds[0].copy()
                embed.description = description
                embed.set_field_at(
                    0,
                    name="선택 현황 및 픽순",
                    value=selection_status,
                    inline=False,
                )
                view = champion_views.get(channel_id)
                await message.edit(embed=embed, view=view)
            except:
                pass

        tasks = [update_pick(cid, msg) for cid, msg in champion_messages.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 모두 선택 완료
        if len(selected_users) >= MAX_PLAYERS:
            msg = f"{MAX_PLAYERS}명 모두 선택 완료!\n"
            for member in pick_order:
                champ = selected_users.get(member.id, "❓")
                msg += f"- {member.mention}: **{champ}**\n"

            # 모든 채널에 완료 메시지 전송 (병렬 처리)
            async def send_final_msg(channel):
                try:
                    await channel.send(msg)
                    await channel.send(
                        "🎯 승리한 팀을 선택해주세요:", view=VictoryView()
                    )
                except:
                    pass

            await asyncio.gather(
                *[send_final_msg(ch) for ch in current_game_channels],
                return_exceptions=True,
            )
        else:
            # 다음 유저 타이머 시작 (이전 타이머는 자동으로 index 체크로 종료됨)
            current_timer_task = asyncio.create_task(
                pick_timeout_handler(current_pick_index)
            )


# === /게임시작 (기존 팀짜기) ===
@bot.slash_command(name="게임시작", description="팀을 나누고 랜덤 챔피언을 보여줍니다.")
async def 게임시작(ctx):
    global current_teams, selected_users, pick_order, current_pick_index, current_timer_task
    global champion_messages, champion_views, current_game_champions, game_started, current_game_channels

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
    selected_users.clear()
    game_started = False
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

    embed = Embed(title=f"🔀 ROUND {round_counter}: 팀 구성", color=0xFFD700)
    for key in ["team1", "team2"]:
        team_emoji = "🔵" if key == "team1" else "🔴"
        embed.add_field(
            name=f"{team_emoji} {key.upper()}",
            value="\n".join([m.mention for m in current_teams[key]]),
            inline=True,
        )
    await ctx.respond(embed=embed)

    # 자동으로 챔피언 추천도 실행
    champ_count = config.get("champion_count", 8)
    picked_champ = pick_random_champions(champion_list, excluded, champ_count)
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

    # 게임에 사용할 채널들 가져오기 (명령 실행 채널 + team1 + team2)
    current_game_channels = get_game_channels(ctx.guild, ctx.channel)
    if not current_game_channels:
        await ctx.channel.send(
            "⚠️ 설정된 채널을 찾을 수 없습니다. config.json을 확인해주세요!"
        )
        return

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
class VictorySelect(Select):
    def __init__(self):
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

    async def callback(self, interaction: Interaction):
        global round_counter, current_teams, wins_data

        if not current_teams:
            await interaction.response.send_message(
                "⚠️ 먼저 `/게임시작`으로 팀을 구성해주세요!", ephemeral=True
            )
            return

        for key in current_teams:
            for member in current_teams[key]:
                if member.id not in selected_users:
                    await interaction.response.send_message(
                        f"❌ {member.mention} 님이 챔피언을 선택하지 않았습니다!",
                        ephemeral=True,
                    )
                    return

        team_key = self.values[0]

        # 전적 업데이트 (overall_results + wins_data)
        for key in current_teams:
            for member in current_teams[key]:
                uid = member.id
                uid_str = str(uid)

                # overall_results 업데이트 (세션 전적)
                if uid not in overall_results:
                    overall_results[uid] = {"mention": member.mention, "results": []}
                overall_results[uid]["results"].append("O" if key == team_key else "X")

                # wins_data 업데이트 (영구 전적)
                if key == team_key:  # 승리 팀만
                    if uid_str in wins_data:
                        wins_data[uid_str]["wins"] += 1
                    else:
                        # 새 유저 추가
                        wins_data[uid_str] = {"name": member.display_name, "wins": 1}

        # total_rounds 증가
        wins_data["total_rounds"] = wins_data.get("total_rounds", 0) + 1

        # wins 데이터 파일에 저장
        save_wins(wins_data)

        def format_team(key):
            return "\n".join(
                f"{m.mention}: **{selected_users.get(m.id, '챔피언 없음')}**"
                for m in current_teams[key]
            )

        embed = Embed(title=f"🏆 ROUND {round_counter} 결과", color=0x44DD88)
        embed.add_field(name="TEAM 1", value=format_team("team1"), inline=True)
        embed.add_field(name="TEAM 2", value=format_team("team2"), inline=True)
        embed.add_field(name="승리 팀", value=f"**{team_key.upper()}**", inline=False)
        await interaction.response.send_message(
            f"✅ **{team_key.upper()}** 승리 기록 완료!", ephemeral=True
        )

        # 모든 게임 채널에 결과 embed 전송
        async def send_result(channel):
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[ERROR] 결과 embed 전송 실패 ({channel.name}): {e}")

        await asyncio.gather(
            *[send_result(ch) for ch in current_game_channels],
            return_exceptions=True,
        )

        round_counter += 1
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


class VictoryView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VictorySelect())


@bot.slash_command(name="승리", description="해당 라운드의 승리 팀을 선택합니다.")
async def 승리(ctx):
    await ctx.respond("승리한 팀을 선택", view=VictoryView())


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
        msg += f"**{rank}.** {name}: **{wins}승 {losses}패** (승률 **{winrate:.1f}%**)\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━"

    await ctx.respond(msg)


# === 봇 시작 시 챔피언 로드 ===
@bot.event
async def on_ready():
    global champion_list, wins_data, config, round_counter
    champion_list = fetch_champion_data()
    wins_data = load_wins()
    config = load_config()

    # round_counter 초기화 (total_rounds + 1)
    round_counter = wins_data.get("total_rounds", 0) + 1

    await bot.sync_commands()
    # 등록된 커맨드 확인
    commands = bot.pending_application_commands
    print(f"[COMMANDS] Registered: {[cmd.name for cmd in commands]}")
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
