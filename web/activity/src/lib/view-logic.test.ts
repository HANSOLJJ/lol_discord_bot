// 픽 화면 뷰 계산 순수 함수의 정확성을 검증하는 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  awaitingResultState,
  completedState,
  noneState,
  pickingMyTurnState,
  pickingOtherTurnState,
} from '../test/fixtures.ts'
import {
  canClickChampion,
  canReportWinner,
  canReverseGame,
  canStartGame,
  COLOR_WARNING_RED,
  COLOR_YELLOW,
  getChampionPicker,
  getChampionPortraitUrl,
  getCountAndBarColor,
  getCurrentPicker,
  isChampionLocked,
  isMyTurn,
  isWarningSeconds,
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
})
