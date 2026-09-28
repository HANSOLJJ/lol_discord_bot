// 전적 대시보드 6개 탭(대전 기록 및 통계 5개 탭) 총괄 최상위 애플리케이션 컴포넌트
import { useEffect, useMemo, useState } from 'react'
import { ChampStatsView } from './components/ChampStatsView.tsx'
import { ComboStatsView } from './components/ComboStatsView.tsx'
import { DashboardFilters } from './components/DashboardFilters.tsx'
import { DashboardHeader } from './components/DashboardHeader.tsx'
import { DashboardTabs } from './components/DashboardTabs.tsx'
import { GameList } from './components/GameList.tsx'
import { MatchupStatsView } from './components/MatchupStatsView.tsx'
import { PlayerStatsView } from './components/PlayerStatsView.tsx'
import { StatsFilters } from './components/StatsFilters.tsx'
import './dashboard.css'
import styles from './DashboardApp.module.css'
import { useChampionPortraits } from './hooks/useChampionPortraits.ts'
import { useHistoryData } from './hooks/useHistoryData.ts'
import { calculateTeamRecord, filterByPeriod, filterGames } from './lib/filter.ts'
import { buildPeriodOptions, getDefaultPeriod, splitSessions } from './lib/session.ts'
import type { SortOrder } from './lib/types.ts'

const SEL_MAX: Record<string, number> = {
  history: 3,
  player: 1,
  pair: 2,
  trio: 3,
  champ: 0,
  matchup: 1,
}

function getTabFromHash(): string {
  if (typeof window === 'undefined') return 'history'
  const hash = window.location.hash.replace(/^#/, '').toLowerCase()
  if (hash === 'personal' || hash === 'player') return 'player'
  if (hash === 'pair') return 'pair'
  if (hash === 'trio') return 'trio'
  if (hash === 'champ') return 'champ'
  if (hash === 'matchup') return 'matchup'
  return 'history'
}

export function DashboardApp() {
  const { data, loading, error, lastUpdated, refresh } = useHistoryData()
  const championPortraits = useChampionPortraits()

  // 탭 및 최소 판수 상태
  const [activeTab, setActiveTab] = useState<string>(getTabFromHash)
  const [minGames, setMinGames] = useState<number>(1)

  // 공통 및 대전 기록 전용 필터 상태
  const [period, setPeriod] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [selectedPlayerIds, setSelectedPlayerIds] = useState<string[]>([])
  const [championQuery, setChampionQuery] = useState<string>('')

  // 브라우저 해시 변경 감지 (뒤로가기/앞으로가기 및 직접 입력 대응)
  useEffect(() => {
    const handleHashChange = () => {
      const tab = getTabFromHash()
      setActiveTab(tab)
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const handleTabChange = (key: string) => {
    setActiveTab(key)
    if (key === 'history') {
      if (window.location.hash && window.location.hash !== '#history') {
        window.history.pushState(
          null,
          '',
          window.location.pathname + window.location.search,
        )
      }
    } else {
      window.location.hash = key
    }

    // 탭 전환 시 인원 선택 최대치를 초과하면 초기화 (옛 index.html 동작 준수)
    const max = SEL_MAX[key] ?? 6
    if (selectedPlayerIds.length > max) {
      setSelectedPlayerIds([])
    }
  }

  const allGames = useMemo(() => data?.games ?? [], [data])
  const players = useMemo(() => data?.players ?? {}, [data])

  const sessions = useMemo(() => splitSessions(allGames), [allGames])
  const periodOptions = useMemo(
    () => buildPeriodOptions(allGames, sessions),
    [allGames, sessions],
  )

  const defaultPeriod = useMemo(() => getDefaultPeriod(allGames), [allGames])
  const activePeriod = period ?? defaultPeriod

  // 대전 기록용 필터링된 게임 목록
  const filteredHistoryGames = useMemo(() => {
    return filterGames(
      allGames,
      {
        period: activePeriod,
        selectedPlayerIds,
        championQuery,
        sortOrder,
      },
      sessions,
    )
  }, [allGames, activePeriod, selectedPlayerIds, championQuery, sortOrder, sessions])

  // 통계 탭용 기간 필터링된 게임 목록 (탭을 바꿔도 기간 선택 유지)
  const periodGames = useMemo(() => {
    return filterByPeriod(allGames, activePeriod, sessions)
  }, [allGames, activePeriod, sessions])

  const statsSummary = useMemo(() => {
    const selectedOpt = periodOptions.find((o) => o.value === activePeriod)
    let label = '전체'
    if (activePeriod.startsWith('season')) {
      label = selectedOpt ? selectedOpt.label.split(' (')[0] : '시즌'
    } else if (activePeriod.startsWith('s')) {
      label = selectedOpt ? selectedOpt.label.split(' ')[0] + ' 세션' : '세션'
    }
    const d0 = periodGames.length ? periodGames[0].time.slice(0, 10) : '-'
    const d1 = periodGames.length
      ? periodGames[periodGames.length - 1].time.slice(0, 10)
      : '-'
    const dateRange = d0 === d1 ? d0 : `${d0} ~ ${d1}`
    return { label, dateRange }
  }, [activePeriod, periodOptions, periodGames])

  const recordSummary = useMemo(() => {
    return calculateTeamRecord(filteredHistoryGames, selectedPlayerIds)
  }, [filteredHistoryGames, selectedPlayerIds])

  const handleTogglePlayer = (id: string) => {
    const max = SEL_MAX[activeTab] ?? 6
    if (max === 0) return

    setSelectedPlayerIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((p) => p !== id)
      }
      if (max === 1) {
        return [id]
      }
      if (prev.length >= max) {
        return prev
      }
      return [...prev, id]
    })
  }

  const handleResetHistoryFilters = () => {
    setSelectedPlayerIds([])
    setChampionQuery('')
    setSortOrder('desc')
  }

  const filterKey = `${activePeriod}-${sortOrder}-${selectedPlayerIds.join(',')}-${championQuery}`

  return (
    <div className={styles.wrap}>
      <DashboardHeader
        lastUpdated={lastUpdated}
        loading={loading}
        onRefresh={refresh}
      />

      <DashboardTabs activeTab={activeTab} onTabChange={handleTabChange} />

      {error ? (
        <div className={styles.errorContainer} role="alert">
          <div className={styles.errorTitle}>데이터를 불러오지 못했습니다.</div>
          <div>{error}</div>
          <button
            type="button"
            className={styles.retryButton}
            onClick={() => refresh()}
          >
            다시 시도
          </button>
        </div>
      ) : !data && loading ? (
        <div className={styles.loadingContainer} role="status">
          <div>전적 데이터를 불러오는 중입니다...</div>
        </div>
      ) : (
        <>
          {/* [탭 1] 대전 기록 */}
          {activeTab === 'history' && (
            <>
              <DashboardFilters
                period={activePeriod}
                defaultPeriod={defaultPeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                sortOrder={sortOrder}
                onSortOrderChange={setSortOrder}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                championQuery={championQuery}
                onChampionQueryChange={setChampionQuery}
                totalCount={allGames.length}
                filteredCount={filteredHistoryGames.length}
                recordSummary={recordSummary}
                onResetFilters={handleResetHistoryFilters}
              />

              <GameList
                key={filterKey}
                games={filteredHistoryGames}
                players={players}
                championPortraits={championPortraits}
                selectedPlayerIds={selectedPlayerIds}
                championQuery={championQuery}
              />
            </>
          )}

          {/* [탭 2] 개인 */}
          {activeTab === 'player' && (
            <>
              <StatsFilters
                period={activePeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                summaryLabel={statsSummary.label}
                gamesCount={periodGames.length}
                dateRange={statsSummary.dateRange}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                onClearPlayer={() => setSelectedPlayerIds([])}
                maxSelection={1}
                minGames={minGames}
                onMinGamesChange={setMinGames}
              />
              <PlayerStatsView
                games={periodGames}
                players={players}
                championPortraits={championPortraits}
                selectedPlayerId={selectedPlayerIds[0] ?? null}
                onSelectPlayer={(id) => setSelectedPlayerIds(id ? [id] : [])}
                minGames={minGames}
              />
            </>
          )}

          {/* [탭 3] 2인 시너지 */}
          {activeTab === 'pair' && (
            <>
              <StatsFilters
                period={activePeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                summaryLabel={statsSummary.label}
                gamesCount={periodGames.length}
                dateRange={statsSummary.dateRange}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                onClearPlayer={() => setSelectedPlayerIds([])}
                maxSelection={2}
                minGames={minGames}
                onMinGamesChange={setMinGames}
              />
              <ComboStatsView
                games={periodGames}
                players={players}
                k={2}
                selectedPlayerIds={selectedPlayerIds}
                minGames={minGames}
              />
            </>
          )}

          {/* [탭 4] 3인 시너지 */}
          {activeTab === 'trio' && (
            <>
              <StatsFilters
                period={activePeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                summaryLabel={statsSummary.label}
                gamesCount={periodGames.length}
                dateRange={statsSummary.dateRange}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                onClearPlayer={() => setSelectedPlayerIds([])}
                maxSelection={3}
                minGames={minGames}
                onMinGamesChange={setMinGames}
              />
              <ComboStatsView
                games={periodGames}
                players={players}
                k={3}
                selectedPlayerIds={selectedPlayerIds}
                minGames={minGames}
              />
            </>
          )}

          {/* [탭 5] 챔피언 */}
          {activeTab === 'champ' && (
            <>
              <StatsFilters
                period={activePeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                summaryLabel={statsSummary.label}
                gamesCount={periodGames.length}
                dateRange={statsSummary.dateRange}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                onClearPlayer={() => setSelectedPlayerIds([])}
                maxSelection={0}
                minGames={minGames}
                onMinGamesChange={setMinGames}
              />
              <ChampStatsView
                games={periodGames}
                championPortraits={championPortraits}
                minGames={minGames}
              />
            </>
          )}

          {/* [탭 6] 3:3 매치업 */}
          {activeTab === 'matchup' && (
            <>
              <StatsFilters
                period={activePeriod}
                onPeriodChange={setPeriod}
                periodOptions={periodOptions}
                sessions={sessions}
                summaryLabel={statsSummary.label}
                gamesCount={periodGames.length}
                dateRange={statsSummary.dateRange}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                onTogglePlayer={handleTogglePlayer}
                onClearPlayer={() => setSelectedPlayerIds([])}
                maxSelection={1}
                minGames={minGames}
                onMinGamesChange={setMinGames}
              />
              <MatchupStatsView
                games={periodGames}
                players={players}
                selectedPlayerIds={selectedPlayerIds}
                minGames={minGames}
              />
            </>
          )}
        </>
      )}
    </div>
  )
}
