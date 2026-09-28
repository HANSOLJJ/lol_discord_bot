# 챔피언 픽 판정 로직의 단위 테스트 및 분기 검증 모듈
##
# @file test_pick_logic.py
# @brief 챔피언 픽 판정 로직(pick_logic.py) 회귀 및 분기 테스트.
# @details ChampionButton.callback의 분기 판정 순서 및 상태 변화를 검증한다.
#
# ==============================================================================
# 판정 분기 검사 순서 표 (ChampionButton.callback 기준)
# ==============================================================================
# | 순서 | 분기 이름 | 조건식 (원본 기준) | 결과 종류 | reason | 응답 문구 (원문) | 상태 변화 |
# |---|---|---|---|---|---|---|
# | 1 | 게임 시작 전 | not game_started | reject | not_started | ⏳ 아직 시작 전입니다. 카운트다운이 끝날 때까지 기다려주세요! | 없음 |
# | 2 | 픽 순서 없음 | not pick_order | reject | no_pick_order | ⚠️ 먼저 `/게임시작`으로 게임을 시작해주세요! | 없음 |
# | 3 | 모든 선택 완료 | current_pick_index >= len(pick_order) | reject | already_finished | ⚠️ 모든 선택이 완료되었습니다! | 없음 |
# | 4 | 차례 아님 | not dev_mode and user_id != current_picker.id | reject | not_turn | ⚠️ 지금은 **{picker_mention}** 님의 차례입니다! | 없음 |
# | 5 | 마감 초과 | clicked_at > current_pick_deadline + pick_grace_seconds | reject | timeout | ⏰ 선택 시간이 지났습니다! | 없음 |
# | 6 | 본인이 고른 챔피언 재클릭(선택 취소) | current_picker.id in selected_users and selected_users[current_picker.id] == champ_name | cancel | cancel | ↩️ **{champ_name}** 선택 취소 | selected_users 제거, excluded 제거, auto_assigned_users 제거 |
# | 7 | 이미 다른 사람이 고른 챔피언 | champ_name in selected_users.values() | reject | already_picked_champ | ⚠️ 이미 선택된 챔피언입니다! | 없음 |
# | 8 | 현재 차례 사람이 이미 선택함 | current_picker.id in selected_users | reject | already_picked_user | ⚠️ 이미 챔피언을 선택하셨습니다! | 없음 |
# | 9 | 그 외 선택 확정 | (위 분기 모두 통과) | pick | pick | {team_emoji} **{champ_name}** 선택 완료! | selected_users 추가, excluded 추가, current_pick_index 증가, all_picked 계산 |
#
# [검사 순서가 결과를 바꾸는 이유]
# 1. game_started 및 pick_order 존재 여부가 확인되지 않으면 게임이 준비되지 않은 상태이므로 인덱스 및 턴 검사를 수행할 수 없다.
# 2. current_pick_index >= len(pick_order)를 먼저 확인해야 유효 범위를 벗어난 인덱스로 pick_order에 접근하는 IndexError를 방지한다.
# 3. 차례 아님 검사를 마감 초과 검사보다 먼저 수행해야, 자기 차례가 아닌 유저가 클릭했을 때 시간 초과 메시지가 아니라 차례 안내 메시지를 받는다.
# 4. 마감 초과 검사를 취소/확정보다 먼저 수행해야, 마감 시간 및 유예 시간이 지난 후의 클릭으로 게임 상태가 변경되지 않는다.
# 5. 본인이 고른 챔피언 재클릭(선택 취소)을 7번(이미 선택된 챔피언), 8번(이미 챔피언을 선택하셨습니다)보다 먼저 검사해야 취소 처리가 가능하다. (취소 대상 챔피언은 이미 selected_users에 등록되어 있으므로 7, 8번 조건에도 해당함)
# 6. 이미 다른 사람이 고른 챔피언(7번)을 현재 차례 사람이 이미 선택함(8번)보다 먼저 검사하여, 남이 고른 챔피언을 눌렀을 때 이미 고른 챔피언임을 안내한다.
# 7. 위의 모든 검사를 통과한 경우에만 최종적으로 선택 확정(9번)이 수행된다.
# ==============================================================================

import unittest
from pick_logic import process_pick, PickResult


class DummyUser:
    """테스트용 가상 유저 객체 (id, name, mention 속성 지원)"""

    def __init__(self, user_id: int, name: str):
        self.id = user_id
        self.name = name
        self.mention = f"@{name}"


class TestPickLogic(unittest.TestCase):
    def setUp(self):
        self.users = [DummyUser(i, f"user{i}") for i in range(1, 7)]
        self.default_order = self.users
        self.default_deadline = 100.0
        self.default_grace = 2.0
        self.default_click_time = 50.0  # 마감 전

    # 1. 게임 시작 전 (game_started is False)
    def test_branch_1_game_not_started(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        res = process_pick(
            game_started=False,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "not_started")
        self.assertEqual(
            res.message,
            "⏳ 아직 시작 전입니다. 카운트다운이 끝날 때까지 기다려주세요!",
        )
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {})
        self.assertEqual(excluded, set())
        self.assertEqual(auto_assigned, set())

    # 2. 픽 순서 없음 (pick_order is empty)
    def test_branch_2_empty_pick_order(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        res = process_pick(
            game_started=True,
            pick_order=[],
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "no_pick_order")
        self.assertEqual(
            res.message, "⚠️ 먼저 `/게임시작`으로 게임을 시작해주세요!"
        )
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {})
        self.assertEqual(excluded, set())
        self.assertEqual(auto_assigned, set())

    # 3. 모든 선택 완료 (current_pick_index >= len(pick_order))
    def test_branch_3_all_picks_completed(self):
        selected_users = {i: f"champ{i}" for i in range(1, 7)}
        excluded = {f"champ{i}" for i in range(1, 7)}
        auto_assigned = set()
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=len(self.default_order),
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "already_finished")
        self.assertEqual(res.message, "⚠️ 모든 선택이 완료되었습니다!")
        self.assertEqual(res.current_pick_index, 6)
        self.assertFalse(res.all_picked)
        self.assertEqual(len(selected_users), 6)

    # 4. 차례 아님 (DEV_MODE 아님, 누른 사람 != current_picker)
    def test_branch_4_not_my_turn(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        # current_picker is user1 (id=1), but user2 clicks
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=2,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "not_turn")
        self.assertEqual(
            res.message, f"⚠️ 지금은 **{self.users[0].mention}** 님의 차례입니다!"
        )
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {})

    # 4-1. DEV_MODE에서는 차례 검사를 건너뛰어 누른 사람 id와 상관없이 진행됨
    def test_branch_4_dev_mode_bypasses_turn_check(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        # current_picker is user1 (id=1), user2 clicks, but dev_mode is True
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=2,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=True,
            team_emoji="🔵",
        )

        self.assertEqual(res.kind, "pick")
        self.assertEqual(res.reason, "pick")
        self.assertEqual(res.message, "🔵 **가렌** 선택 완료!")
        self.assertEqual(res.current_pick_index, 1)
        self.assertEqual(selected_users[1], "가렌")  # current_picker는 여전히 user1

    # 5. 마감 초과 (clicked_at > current_pick_deadline + pick_grace_seconds)
    def test_branch_5_timeout_strictly_greater_than_deadline_plus_grace(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        # deadline 100.0, grace 2.0 -> limit is 102.0. click at 102.001
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=102.001,
            current_pick_deadline=100.0,
            pick_grace_seconds=2.0,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "timeout")
        self.assertEqual(res.message, "⏰ 선택 시간이 지났습니다!")
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {})

    # 5-1. 경계값: 정확히 마감+유예 시각에 클릭 (clicked_at == deadline + grace -> 인정됨)
    def test_branch_5_boundary_exact_deadline_plus_grace_is_accepted(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=102.0,  # 100.0 + 2.0 정확히 일치
            current_pick_deadline=100.0,
            pick_grace_seconds=2.0,
            dev_mode=False,
            team_emoji="🔵",
        )

        self.assertEqual(res.kind, "pick")
        self.assertEqual(res.reason, "pick")
        self.assertEqual(res.message, "🔵 **가렌** 선택 완료!")
        self.assertEqual(res.current_pick_index, 1)
        self.assertEqual(selected_users[1], "가렌")

    # 5-2. 경계값: 마감+유예 직전 클릭 (clicked_at < deadline + grace -> 인정됨)
    def test_branch_5_boundary_just_within_deadline_plus_grace_is_accepted(
        self,
    ):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=101.999,
            current_pick_deadline=100.0,
            pick_grace_seconds=2.0,
            dev_mode=False,
            team_emoji="🔵",
        )

        self.assertEqual(res.kind, "pick")
        self.assertEqual(res.reason, "pick")
        self.assertEqual(res.message, "🔵 **가렌** 선택 완료!")
        self.assertEqual(res.current_pick_index, 1)

    # 6. 본인이 고른 챔피언 재클릭 (선택 취소)
    def test_branch_6_cancel_own_pick(self):
        # current_picker is user1 (id=1), already has "가렌"
        selected_users = {1: "가렌"}
        excluded = {"가렌"}
        auto_assigned = {1}
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "cancel")
        self.assertEqual(res.reason, "cancel")
        self.assertEqual(res.message, "↩️ **가렌** 선택 취소")
        # 상태 변화 검증: selected_users에서 제거, excluded에서 제거, auto_assigned_users에서 제거
        self.assertNotIn(1, selected_users)
        self.assertNotIn("가렌", excluded)
        self.assertNotIn(1, auto_assigned)
        # current_pick_index는 증가하지 않음
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)

    # 7. 이미 다른 사람이 고른 챔피언
    def test_branch_7_already_picked_by_other(self):
        selected_users = {2: "가렌"}  # user2가 이미 가렌을 고름
        excluded = {"가렌"}
        auto_assigned = set()
        # current_picker is user1 (id=1)
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "already_picked_champ")
        self.assertEqual(res.message, "⚠️ 이미 선택된 챔피언입니다!")
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {2: "가렌"})
        self.assertEqual(excluded, {"가렌"})

    # 8. 현재 차례 사람이 이미 선택함 (다른 챔피언을 이미 선택한 상태)
    def test_branch_8_current_picker_already_picked_different_champ(self):
        selected_users = {1: "가렌"}  # user1이 이미 가렌을 고름
        excluded = {"가렌"}
        auto_assigned = set()
        # user1이 다리우스를 클릭
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="다리우스",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )

        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "already_picked_user")
        self.assertEqual(res.message, "⚠️ 이미 챔피언을 선택하셨습니다!")
        self.assertEqual(res.current_pick_index, 0)
        self.assertFalse(res.all_picked)
        self.assertEqual(selected_users, {1: "가렌"})

    # 9. 그 외 선택 확정 (중간 플레이어)
    def test_branch_9_pick_confirm_intermediate(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
            max_players=6,
            team_emoji="🔵",
        )

        self.assertEqual(res.kind, "pick")
        self.assertEqual(res.reason, "pick")
        self.assertEqual(res.message, "🔵 **가렌** 선택 완료!")
        # 상태 변화
        self.assertEqual(selected_users[1], "가렌")
        self.assertIn("가렌", excluded)
        self.assertEqual(res.current_pick_index, 1)
        self.assertFalse(res.all_picked)

    # 9-1. 선택 확정 (마지막 플레이어 -> all_picked is True)
    def test_branch_9_pick_confirm_last_player_all_picked(self):
        selected_users = {i: f"champ{i}" for i in range(1, 6)}
        excluded = {f"champ{i}" for i in range(1, 6)}
        auto_assigned = set()
        # current_picker is user6 (id=6, index=5)
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=5,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=6,
            champ_name="아리",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
            max_players=6,
            team_emoji="🔴",
        )

        self.assertEqual(res.kind, "pick")
        self.assertEqual(res.reason, "pick")
        self.assertEqual(res.message, "🔴 **아리** 선택 완료!")
        self.assertEqual(selected_users[6], "아리")
        self.assertIn("아리", excluded)
        self.assertEqual(res.current_pick_index, 6)
        self.assertTrue(res.all_picked)

    # 검사 우선순위 테스트: 취소(6번)가 이미 선택된 챔피언(7번), 이미 선택함(8번)보다 우선
    def test_priority_cancel_over_already_picked(self):
        selected_users = {1: "가렌"}
        excluded = {"가렌"}
        auto_assigned = {1}
        # 1번이 이미 가렌을 골랐고 가렌은 selected_users.values()에 있지만
        # 취소가 7번, 8번보다 앞서므로 "이미 선택된 챔피언"이 아니라 취소 처리가 되어야 함
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )
        self.assertEqual(res.kind, "cancel")
        self.assertEqual(res.message, "↩️ **가렌** 선택 취소")

    # 검사 우선순위 테스트: 차례 아님(4번)이 마감 초과(5번)보다 우선
    def test_priority_not_turn_over_timeout(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        # user1의 차례인데 user2가 마감 초과 시점에 클릭한 경우
        # 시간 초과가 아닌 차례 아님 메시지가 나와야 함
        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=2,
            champ_name="가렌",
            clicked_at=999.0,  # 극단적 초과 시점
            current_pick_deadline=100.0,
            pick_grace_seconds=2.0,
            dev_mode=False,
        )
        self.assertEqual(res.kind, "reject")
        self.assertEqual(res.reason, "not_turn")
        self.assertEqual(
            res.message, f"⚠️ 지금은 **{self.users[0].mention}** 님의 차례입니다!"
        )

    # 상태 컬렉션이 함수 내부에서 직접(in-place) 변경되는지 검증
    def test_state_mutation_in_place(self):
        selected_users = {}
        excluded = set()
        auto_assigned = set()
        ref_selected = selected_users
        ref_excluded = excluded
        ref_auto = auto_assigned

        res = process_pick(
            game_started=True,
            pick_order=self.default_order,
            current_pick_index=0,
            selected_users=selected_users,
            excluded=excluded,
            auto_assigned_users=auto_assigned,
            user_id=1,
            champ_name="가렌",
            clicked_at=self.default_click_time,
            current_pick_deadline=self.default_deadline,
            pick_grace_seconds=self.default_grace,
            dev_mode=False,
        )
        self.assertEqual(res.kind, "pick")
        # 인자로 넘긴 객체 자체(동일 참조)가 변경되었는지 확인
        self.assertIs(selected_users, ref_selected)
        self.assertEqual(ref_selected[1], "가렌")
        self.assertIs(excluded, ref_excluded)
        self.assertIn("가렌", ref_excluded)


if __name__ == "__main__":
    unittest.main()
