// 픽 화면 뷰 계산 순수 함수의 정확성을 검증하는 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  advantageBanPendingState,
  advantageWaitingState,
  awaitingResultState,
  completedState,
  noneState,
  pickingBannedState,
  pickingForcedLastState,
  pickingForcedState,
  pickingMyTurnState,
  pickingOtherTurnState,
  SAMPLE_CHAMPIONS,
} from '../test/fixtures.ts'
import {
  canClickChampion,
  canReportWinner,
  canReverseGame,
  canStartGame,
  COLOR_WARNING_RED,
  COLOR_YELLOW,
  getAdvantageHeaderInfo,
  getAdvantageSummary,
  getChampionPicker,
  getChampionPortraitUrl,
  getCountAndBarColor,
  getCurrentPicker,
  isChampionBanned,
  isChampionForced,
  isChampionLocked,
  isLastTurnOfOpponent,
  isMyTurn,
  isWarningSeconds,
  mustPickForced,
} from './view-logic.ts'

describe('화면 계산 함수 (view-logic)', () => {
  it('지금 고르는 사람(getCurrentPicker)을 올바르게 구한다', () => {
    const none = noneState()
    assert.equal(getCurrentPicker(none), null)

    const other = pickingOtherTurnState() // current_index = 0 ('333333333333333333' 청명사냥꾼)
    const pickerOther = getCurrentPicker(other)
    assert.ok(pickerOther)
    assert.equal(pickerOther.name, '청명사냥꾼')
    assert.equal(pickerOther.team, 'team2')

    const my = pickingMyTurnState() // current_index = 4 ('365414320332472332' 정한솔)
    const pickerMy = getCurrentPicker(my)
    assert.ok(pickerMy)
    assert.equal(pickerMy.name, '정한솔')
    assert.equal(pickerMy.team, 'team1')
  })

  it('내 차례(isMyTurn)를 정확히 판별한다', () => {
    assert.equal(isMyTurn(noneState()), false)
    assert.equal(isMyTurn(pickingOtherTurnState()), false)
    assert.equal(isMyTurn(pickingMyTurnState()), true)
  })

  it('뽑힌 챔피언 잠금(isChampionLocked) 및 선택자(getChampionPicker)를 올바르게 판별한다', () => {
    const state = pickingMyTurnState()
    // selections: Zed(3333...), Sona(1111...), Ahri(5555...), Leona(4444...)
    assert.equal(isChampionLocked('Zed', state.selections), true)
    assert.equal(isChampionLocked('Sona', state.selections), true)
    assert.equal(isChampionLocked('MonkeyKing', state.selections), false)
    assert.equal(isChampionLocked('Annie', state.selections), false)

    const zedPicker = getChampionPicker('Zed', state.selections, state.players, state.auto_assigned)
    assert.ok(zedPicker)
    assert.equal(zedPicker.picker.name, '청명사냥꾼')
    assert.equal(zedPicker.auto, false)

    const sonaPicker = getChampionPicker('Sona', state.selections, state.players, state.auto_assigned)
    assert.ok(sonaPicker)
    assert.equal(sonaPicker.picker.name, '사무엘')
    assert.equal(sonaPicker.auto, true) // auto_assigned에 포함됨

    const unpicked = getChampionPicker('Annie', state.selections, state.players, state.auto_assigned)
    assert.equal(unpicked, null)
  })

  it('5초 이하 경고 판정 및 색상(isWarningSeconds, getCountAndBarColor)을 올바르게 계산한다', () => {
    assert.equal(isWarningSeconds(10), false)
    assert.equal(isWarningSeconds(6), false)
    assert.equal(isWarningSeconds(5), true)
    assert.equal(isWarningSeconds(4), true)
    assert.equal(isWarningSeconds(0), true)
    assert.equal(isWarningSeconds(null), false)

    assert.equal(getCountAndBarColor(10), COLOR_YELLOW)
    assert.equal(getCountAndBarColor(6), COLOR_YELLOW)
    assert.equal(getCountAndBarColor(5), COLOR_WARNING_RED)
    assert.equal(getCountAndBarColor(2), COLOR_WARNING_RED)
    assert.equal(getCountAndBarColor(0), COLOR_WARNING_RED)
    assert.equal(getCountAndBarColor(null), COLOR_YELLOW)
  })

  it('챔피언 클릭 가능 여부(canClickChampion)를 권한 및 잠금에 따라 판별한다', () => {
    const myTurn = pickingMyTurnState()
    // 내 차례이고 잠기지 않은 MonkeyKing 클릭 가능
    assert.equal(canClickChampion('MonkeyKing', myTurn, false), true)
    // 요청 전송 중(isPending = true)에는 클릭 불가
    assert.equal(canClickChampion('MonkeyKing', myTurn, true), false)
    // 이미 뽑힌 Zed는 클릭 불가
    assert.equal(canClickChampion('Zed', myTurn, false), false)

    // 남의 차례에는 안 뽑힌 챔피언도 클릭 불가
    const otherTurn = pickingOtherTurnState()
    assert.equal(canClickChampion('MonkeyKing', otherTurn, false), false)
  })

  it('버튼 활성화 조건(canStartGame, canReportWinner, canReverseGame)을 올바르게 판정한다', () => {
    // canStartGame
    assert.equal(canStartGame(noneState(), false, true), true)
    assert.equal(canStartGame(noneState(), true, true), false) // pending
    assert.equal(canStartGame(noneState(), false, false), false) // disconnected
    assert.equal(canStartGame(pickingMyTurnState(), false, true), false) // picking 중에는 can_start false
    assert.equal(canStartGame(awaitingResultState(), false, true), true) // awaiting_result에서 can_start true

    // canReportWinner
    const awaiting = awaitingResultState()
    assert.equal(canReportWinner(awaiting, false, true), true)
    assert.equal(canReportWinner(awaiting, true, true), false) // pending
    assert.equal(canReportWinner(awaiting, false, false), false) // disconnected
    assert.equal(canReportWinner(pickingMyTurnState(), false, true), false) // picking 중 불가

    // canReverseGame
    const completed = completedState()
    assert.equal(canReverseGame(completed, false, true), true)
    assert.equal(canReverseGame(completed, true, true), false) // pending
    assert.equal(canReverseGame(completed, false, false), false) // disconnected
    assert.equal(canReverseGame(awaiting, false, true), false) // completed 아님
  })

  it('초상화 URL(getChampionPortraitUrl)을 Data Dragon 버전에 맞게 생성한다', () => {
    assert.equal(
      getChampionPortraitUrl('Ahri', '15.19.1'),
      '/ddragon/cdn/15.19.1/img/champion/Ahri.png',
    )
    assert.equal(getChampionPortraitUrl('Ahri', null), null)
  })

  it('advantage 단계의 누름 가능 여부를 판정한다 (me.can_advantage)', () => {
    const advMyTurn = advantageBanPendingState() // me.can_advantage: true
    assert.equal(canClickChampion('Zed', advMyTurn, false), true)
    assert.equal(canClickChampion('Ahri', advMyTurn, false), true)
    // isPending 중에는 누를 수 없음
    assert.equal(canClickChampion('Zed', advMyTurn, true), false)

    // 내가 이점 팀이 아닌 경우(대기 중)
    const advWaiting = advantageWaitingState() // me.can_advantage: false
    assert.equal(canClickChampion('Zed', advWaiting, false), false)
  })

  it('밴된 카드는 아무도 누를 수 없다', () => {
    // Zed가 밴된 상태
    const bannedState = pickingBannedState()
    assert.equal(isChampionBanned('Zed', bannedState.advantage), true)
    assert.equal(isChampionBanned('Ahri', bannedState.advantage), false)

    // 내 차례(can_pick: true)여도 밴된 Zed는 누를 수 없음
    assert.equal(canClickChampion('Zed', bannedState, false), false)
    // 밴되지 않고 선택 안 된 MonkeyKing은 누를 수 있음
    assert.equal(canClickChampion('MonkeyKing', bannedState, false), true)
  })

  it('강제픽 카드는 이점 팀 차례에는 누를 수 없고 상대 팀 차례에는 누를 수 있다', () => {
    // advantage.team = team2, forced champ = Garen
    // 정한솔은 team1 (상대 팀), current_index = 4 (정한솔 차례)
    const forcedForTeam1 = pickingForcedState()
    assert.equal(isChampionForced('Garen', forcedForTeam1.advantage), true)
    assert.equal(isChampionForced('Zed', forcedForTeam1.advantage), false)

    // team1 선수는 강제픽 Garen을 누를 수 있음
    assert.equal(canClickChampion('Garen', forcedForTeam1, false), true)
    // team1 선수는 다른 안 뽑힌 챔피언(MonkeyKing)도 누를 수 있음 (아직 마지막 차례 아님)
    assert.equal(canClickChampion('MonkeyKing', forcedForTeam1, false), true)

    // 이점 팀(team2) 선수 차례인 경우:
    // current_index = 3 ('444444444444444444' 보링, 강제픽 예시 배치에서 team2)
    const forcedForTeam2 = pickingForcedState({
      current_index: 3,
      me: {
        id: '444444444444444444',
        role: 'player',
        team: 'team2',
        can_start: false,
        can_pick: true,
        can_report: false,
        can_reverse: false,
        can_advantage: false,
      },
    })
    // 이점 팀 선수는 강제픽 카드(Garen)를 누를 수 없음!
    assert.equal(canClickChampion('Garen', forcedForTeam2, false), false)
    // 이점 팀 선수는 다른 일반 미선택 카드(MonkeyKing)는 누를 수 있음
    assert.equal(canClickChampion('MonkeyKing', forcedForTeam2, false), true)
  })

  it('상대 팀의 마지막 차례에 강제픽이 남아 있으면 오직 강제픽 카드만 누를 수 있다', () => {
    const forcedLast = pickingForcedLastState()
    // 유성호(team1)의 차례, team1의 마지막 차례, 강제픽은 Garen
    assert.equal(isLastTurnOfOpponent(forcedLast), true)
    assert.equal(mustPickForced(forcedLast), true)

    // 강제픽 Garen만 누를 수 있음
    assert.equal(canClickChampion('Garen', forcedLast, false), true)
    // 아직 안 뽑힌 다른 카드(TwistedFate 등)는 누를 수 없음!
    assert.equal(canClickChampion('TwistedFate', forcedLast, false), false)

    // 만약 이미 강제픽 Garen이 뽑힌 상태라면 mustPickForced는 false이고 일반 카드 누를 수 있음
    const alreadyPickedState = pickingForcedLastState({
      selections: {
        ...forcedLast.selections,
        '365414320332472332': 'Garen', // 이전 차례에서 Garen을 이미 뽑음
      },
    })
    assert.equal(mustPickForced(alreadyPickedState), false)
    assert.equal(canClickChampion('TwistedFate', alreadyPickedState, false), true)
  })

  it('이점 요약 문구(getAdvantageSummary)를 정상적으로 생성한다', () => {
    // 이점 없음
    assert.equal(getAdvantageSummary(null, SAMPLE_CHAMPIONS), null)

    // 밴 확정
    const banChosen = { kind: 'ban' as const, team: 'team2' as const, status: 'chosen' as const, champion_id: 'Zed' }
    assert.equal(getAdvantageSummary(banChosen, SAMPLE_CHAMPIONS), 'TEAM 2 어드밴티지 · 밴: 제드')

    // 강제픽 확정
    const forceChosen = { kind: 'force' as const, team: 'team1' as const, status: 'chosen' as const, champion_id: 'Ahri' }
    assert.equal(getAdvantageSummary(forceChosen, SAMPLE_CHAMPIONS), 'TEAM 1 어드밴티지 · 강제픽: 아리')

    // 시간 초과
    const skipped = { kind: 'ban' as const, team: 'team2' as const, status: 'skipped' as const, champion_id: null }
    assert.equal(getAdvantageSummary(skipped, SAMPLE_CHAMPIONS), '시간 초과로 어드밴티지 없음')

    // starting 단계 pending
    const startingPending = { kind: 'ban' as const, team: 'team2' as const, status: 'pending' as const, champion_id: null }
    assert.equal(getAdvantageSummary(startingPending, SAMPLE_CHAMPIONS, 'starting'), 'TEAM 2 어드밴티지 예정 · 밴')
  })

  it('advantage 헤더 정보(getAdvantageHeaderInfo)를 정상 계산한다', () => {
    const advMyTurn = advantageBanPendingState()
    const infoMy = getAdvantageHeaderInfo(advMyTurn)
    assert.ok(infoMy)
    assert.equal(infoMy.title, 'TEAM 2 어드밴티지 · 밴할 챔피언 1개')
    assert.equal(infoMy.hint, '챔피언을 누르면 바로 확정됩니다')
    assert.equal(infoMy.teamColor, '#ff6b5e')

    const advWaiting = advantageWaitingState()
    const infoOther = getAdvantageHeaderInfo(advWaiting)
    assert.ok(infoOther)
    assert.equal(infoOther.hint, 'TEAM 2가 고르는 중')
  })
})
