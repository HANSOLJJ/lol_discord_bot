// validation.ts 모듈의 JSON 유효성 검증 및 거부 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { isValidHistoryData, validateHistoryData } from './validation.ts'

const validSample = {
  players: {
    '1': '플레이어1',
    '2': '플레이어2',
    '3': '플레이어3',
    '4': '플레이어4',
    '5': '플레이어5',
    '6': '플레이어6',
  },
  games: [
    {
      round: 1,
      season: 2,
      time: '2026-09-26T18:31:00Z',
      winner: 'team1',
      team1: [
        { id: '1', champ: '아리' },
        { id: '2', champ: '가렌' },
        { id: '3', champ: '럭스' },
      ],
      team2: [
        { id: '4', champ: '야스오' },
        { id: '5', champ: '리신' },
        { id: '6', champ: '징크스' },
      ],
    },
  ],
}

describe('isValidHistoryData', () => {
  it('유효한 정상 데이터를 통과시킨다', () => {
    assert.equal(isValidHistoryData(validSample), true)
  })

  it('null이나 원시 타입을 거부한다', () => {
    assert.equal(isValidHistoryData(null), false)
    assert.equal(isValidHistoryData('string'), false)
    assert.equal(isValidHistoryData(123), false)
    assert.equal(isValidHistoryData([]), false)
  })

  it('players 필드가 누락되었거나 객체가 아니면 거부한다', () => {
    assert.equal(isValidHistoryData({ ...validSample, players: null }), false)
    assert.equal(isValidHistoryData({ ...validSample, players: [1, 2] }), false)
  })

  it('games 필드가 배열이 아니면 거부한다', () => {
    assert.equal(isValidHistoryData({ ...validSample, games: null }), false)
    assert.equal(isValidHistoryData({ ...validSample, games: 'games' }), false)
  })

  it('게임 내 필수 필드(round, time, winner, team1/2)가 누락되거나 잘못되면 거부한다', () => {
    // winner가 team1/team2가 아닌 경우
    assert.equal(
      isValidHistoryData({
        ...validSample,
        games: [{ ...validSample.games[0], winner: 'draw' }],
      }),
      false,
    )

    // team1의 인원수가 3명이 아닌 경우
    assert.equal(
      isValidHistoryData({
        ...validSample,
        games: [{ ...validSample.games[0], team1: [] }],
      }),
      false,
    )

    // 잘못된 시간 문자열인 경우
    assert.equal(
      isValidHistoryData({
        ...validSample,
        games: [{ ...validSample.games[0], time: 'not-a-date' }],
      }),
      false,
    )
  })

  it('corrected 필드가 있는 경우 올바른 형식이면 통과하고 잘못되면 거부한다', () => {
    const validWithCorrected = {
      ...validSample,
      games: [
        {
          ...validSample.games[0],
          corrected: { from: 'team2', at: '2026-09-26T19:00:00Z' },
        },
      ],
    }
    assert.equal(isValidHistoryData(validWithCorrected), true)

    const invalidCorrected = {
      ...validSample,
      games: [
        {
          ...validSample.games[0],
          corrected: { from: 'invalidTeam', at: 123 },
        },
      ],
    }
    assert.equal(isValidHistoryData(invalidCorrected), false)
  })
})

describe('validateHistoryData', () => {
  it('유효하지 않은 데이터인 경우 예외를 발생시킨다', () => {
    assert.throws(() => validateHistoryData({}), /유효하지 않은/)
  })

  it('정상 데이터인 경우 season 보정과 함께 데이터를 반환한다', () => {
    const result = validateHistoryData(validSample)
    assert.equal(result.games.length, 1)
    assert.equal(result.games[0].season, 2)
  })
})
