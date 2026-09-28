// corrected.ts 모듈의 번복 데이터 정리 및 표기 단위 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { formatCorrectedInfo } from './corrected.ts'

describe('formatCorrectedInfo', () => {
  it('team1로부터의 번복 정보를 올바르게 포맷팅한다', () => {
    const result = formatCorrectedInfo({
      from: 'team1',
      at: '2026-09-26T19:00:00Z',
    })
    assert.equal(result.previousWinnerLabel, 'TEAM 1')
    assert.equal(result.formattedAt, '9월 27일 (일) 04:00')
    assert.equal(result.summary, '이전 승자: TEAM 1, 9월 27일 (일) 04:00 정정')
  })

  it('team2로부터의 번복 정보를 올바르게 포맷팅한다', () => {
    const result = formatCorrectedInfo({
      from: 'team2',
      at: '2026-09-26T19:30:00Z',
    })
    assert.equal(result.previousWinnerLabel, 'TEAM 2')
    assert.equal(result.formattedAt, '9월 27일 (일) 04:30')
    assert.equal(result.summary, '이전 승자: TEAM 2, 9월 27일 (일) 04:30 정정')
  })
})
