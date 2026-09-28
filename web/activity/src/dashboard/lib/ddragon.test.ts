// ddragon.ts 모듈의 초상화 URL 생성 및 첫 글자 폴백 단위 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DEFAULT_DDRAGON_BASE_URL,
  fetchChampionPortraitMap,
  getChampionFallbackInitial,
} from './ddragon.ts'

describe('fetchChampionPortraitMap', () => {
  it('모의 fetch를 통해 버전 조회 후 챔피언 매핑 URL을 올바르게 생성한다', async () => {
    const mockVersions = ['14.1.1', '14.1.0']
    const mockChampionJson = {
      data: {
        Ahr: { id: 'Ahri', name: '아리' },
        Garen: { id: 'Garen', name: '가렌' },
      },
    }

    const mockFetch = async (input: string | URL | Request) => {
      const url = String(input)
      if (url.includes('api/versions.json')) {
        return new Response(JSON.stringify(mockVersions), { status: 200 })
      }
      if (url.includes('cdn/14.1.1/data/ko_KR/champion.json')) {
        return new Response(JSON.stringify(mockChampionJson), { status: 200 })
      }
      return new Response('Not found', { status: 404 })
    }

    const map = await fetchChampionPortraitMap(
      DEFAULT_DDRAGON_BASE_URL,
      mockFetch as typeof fetch,
    )
    assert.equal(
      map['아리'],
      'https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/Ahri.png',
    )
    assert.equal(
      map['가렌'],
      'https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/Garen.png',
    )
  })

  it('커스텀 베이스 URL 인자를 정상적으로 지원한다', async () => {
    const mockVersions = ['14.1.1']
    const mockChampionJson = {
      data: {
        Ahri: { id: 'Ahri', name: '아리' },
      },
    }

    const customFetch = async (input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('versions.json')) {
        return new Response(JSON.stringify(mockVersions))
      }
      return new Response(JSON.stringify(mockChampionJson))
    }

    const map = await fetchChampionPortraitMap(
      '/ddragon',
      customFetch as typeof fetch,
    )
    assert.equal(map['아리'], '/ddragon/cdn/14.1.1/img/champion/Ahri.png')
  })
})

describe('getChampionFallbackInitial', () => {
  it('챔피언 이름의 첫 글자를 반환한다', () => {
    assert.equal(getChampionFallbackInitial('갈리오'), '갈')
    assert.equal(getChampionFallbackInitial('문도 박사'), '문')
    assert.equal(getChampionFallbackInitial('Ahri'), 'A')
  })

  it('빈 문자열이나 공백 처리 시 ?를 반환한다', () => {
    assert.equal(getChampionFallbackInitial(''), '?')
    assert.equal(getChampionFallbackInitial('   '), '?')
  })
})
