# 챔피언 픽 규칙 판정 및 상태 변경을 수행하는 순수 로직 모듈
##
# @file pick_logic.py
# @brief 챔피언 선택 규칙 판정 및 상태 갱신 순수 로직.
# @details Discord API나 봇 전역 상태와 독립적으로 동작하며, 입력된 게임 상태와 클릭 정보를 바탕으로
#          선택 가능 여부(reject, cancel, pick)를 판정하고 상태 컬렉션을 갱신한다.

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


##
# @brief 챔피언 픽 판정 결과를 담는 불변 데이터 클래스.
@dataclass(frozen=True)
class PickResult:
    kind: str  # "reject" | "cancel" | "pick"
    reason: str  # "not_started" | "no_pick_order" | "already_finished" | "not_turn" | "timeout" | "cancel" | "already_picked_champ" | "already_picked_user" | "pick"
    message: str
    current_pick_index: int
    all_picked: bool
    current_picker_id: Optional[Any] = None


##
# @brief 챔피언 버튼 클릭에 대한 픽 가능 여부를 판정하고 상태를 갱신한다.
# @details 판정 분기 검사 순서:
#          1. game_started가 False -> reject (not_started)
#          2. pick_order가 비어있음 -> reject (no_pick_order)
#          3. current_pick_index >= len(pick_order) -> reject (already_finished)
#          4. dev_mode가 아니고 누른 사람 id != current_picker.id -> reject (not_turn)
#          5. clicked_at > current_pick_deadline + pick_grace_seconds -> reject (timeout)
#          6. 본인이 고른 챔피언 재클릭 -> cancel (cancel)
#          7. 이미 다른 사람이 고른 챔피언 -> reject (already_picked_champ)
#          8. 현재 차례 사람이 이미 선택함 -> reject (already_picked_user)
#          9. 그 외 선택 확정 -> pick (pick)
# @param game_started 게임 시작 여부(bool).
# @param pick_order 픽 순서 리스트 (유저 객체 또는 유저 ID 목록).
# @param current_pick_index 현재 픽 인덱스(int).
# @param selected_users 선택된 유저 맵 {user_id: champ_name} (in-place 갱신).
# @param excluded 제외된 챔피언 셋 {champ_name} (in-place 갱신).
# @param auto_assigned_users 자동 배정된 유저 셋 {user_id} (in-place 갱신).
# @param user_id 클릭한 유저 ID(int 또는 id 속성을 가진 객체).
# @param champ_name 선택 시도한 챔피언 이름(str).
# @param clicked_at 클릭 접수 시각(float, 유닉스 초).
# @param current_pick_deadline 현재 턴 마감 시각(float, 유닉스 초).
# @param pick_grace_seconds 마감 후 유예 시간(float, 기본값 2.0).
# @param dev_mode DEV_MODE 여부(bool, 기본값 False).
# @param max_players 게임 전체 플레이어 수(int, 기본값 6).
# @param team_emoji 선택 확정 시 표시할 팀 이모지(str, 기본값 "🔵").
# @param picker_mention 차례 안내 시 표시할 멘션 문자열(str, 기본값 None).
# @return PickResult 판정 결과 객체.
def process_pick(
    game_started: bool,
    pick_order: List[Any],
    current_pick_index: int,
    selected_users: Dict[Any, str],
    excluded: Set[str],
    auto_assigned_users: Set[Any],
    user_id: Any,
    champ_name: str,
    clicked_at: float,
    current_pick_deadline: float,
    pick_grace_seconds: float = 2.0,
    dev_mode: bool = False,
    max_players: int = 6,
    team_emoji: str = "🔵",
    picker_mention: Optional[str] = None,
) -> PickResult:
    uid = getattr(user_id, "id", user_id)

    # 1. 게임 시작 전
    if not game_started:
        return PickResult(
            kind="reject",
            reason="not_started",
            message="⏳ 아직 시작 전입니다. 카운트다운이 끝날 때까지 기다려주세요!",
            current_pick_index=current_pick_index,
            all_picked=False,
        )

    # 2. 픽 순서 없음
    if not pick_order:
        return PickResult(
            kind="reject",
            reason="no_pick_order",
            message="⚠️ 먼저 `/게임시작`으로 게임을 시작해주세요!",
            current_pick_index=current_pick_index,
            all_picked=False,
        )

    # 3. 모든 선택 완료
    if current_pick_index >= len(pick_order):
        return PickResult(
            kind="reject",
            reason="already_finished",
            message="⚠️ 모든 선택이 완료되었습니다!",
            current_pick_index=current_pick_index,
            all_picked=False,
        )

    current_picker = pick_order[current_pick_index]
    current_picker_id = getattr(current_picker, "id", current_picker)

    if picker_mention is not None:
        mention = picker_mention
    else:
        mention = getattr(current_picker, "mention", f"<@{current_picker_id}>")

    # 4. 차례 아님 (DEV_MODE가 아닐 때만)
    if not dev_mode and uid != current_picker_id:
        return PickResult(
            kind="reject",
            reason="not_turn",
            message=f"⚠️ 지금은 **{mention}** 님의 차례입니다!",
            current_pick_index=current_pick_index,
            all_picked=False,
            current_picker_id=current_picker_id,
        )

    # 5. 마감 초과
    if clicked_at > current_pick_deadline + pick_grace_seconds:
        return PickResult(
            kind="reject",
            reason="timeout",
            message="⏰ 선택 시간이 지났습니다!",
            current_pick_index=current_pick_index,
            all_picked=False,
            current_picker_id=current_picker_id,
        )

    # 6. 본인이 고른 챔피언 재클릭 = 선택 취소
    if (
        current_picker_id in selected_users
        and selected_users[current_picker_id] == champ_name
    ):
        del selected_users[current_picker_id]
        excluded.discard(champ_name)
        auto_assigned_users.discard(current_picker_id)
        return PickResult(
            kind="cancel",
            reason="cancel",
            message=f"↩️ **{champ_name}** 선택 취소",
            current_pick_index=current_pick_index,
            all_picked=False,
            current_picker_id=current_picker_id,
        )

    # 7. 이미 다른 사람이 고른 챔피언
    if champ_name in selected_users.values():
        return PickResult(
            kind="reject",
            reason="already_picked_champ",
            message="⚠️ 이미 선택된 챔피언입니다!",
            current_pick_index=current_pick_index,
            all_picked=False,
            current_picker_id=current_picker_id,
        )

    # 8. 현재 차례 사람이 이미 선택함
    if current_picker_id in selected_users:
        return PickResult(
            kind="reject",
            reason="already_picked_user",
            message="⚠️ 이미 챔피언을 선택하셨습니다!",
            current_pick_index=current_pick_index,
            all_picked=False,
            current_picker_id=current_picker_id,
        )

    # 9. 그 외 선택 확정
    selected_users[current_picker_id] = champ_name
    excluded.add(champ_name)
    new_index = current_pick_index + 1
    all_picked = len(selected_users) >= max_players

    return PickResult(
        kind="pick",
        reason="pick",
        message=f"{team_emoji} **{champ_name}** 선택 완료!",
        current_pick_index=new_index,
        all_picked=all_picked,
        current_picker_id=current_picker_id,
    )
