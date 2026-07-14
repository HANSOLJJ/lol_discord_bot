# TEAM1/TEAM2/팀짜기 3채널을 전부 풀스캔해 결과 embed 를 합집합으로 복구(유실 보정)하는 파서
import discord
import os
import json
import re
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

GUILD_ID = 391527401475014658
CHANNELS = ["TEAM2", "TEAM1", "팀짜기"]
CH_LABEL = {"TEAM2": "T2", "TEAM1": "T1", "팀짜기": "CMD"}

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

with open("wins.json", "r", encoding="utf-8") as f:
    wins_data = json.load(f)
NAME_MAP = {
    uid: v["name"] for uid, v in wins_data.items()
    if isinstance(v, dict) and "name" in v
}

LINE_RE = re.compile(r"<@!?(\d+)>:\s*\*\*(.+?)\*\*")


def parse_team(field_value):
    return [{"id": m.group(1), "champ": m.group(2).strip()} for m in LINE_RE.finditer(field_value)]


def parse_result_embed(embed):
    if not embed.title or "ROUND" not in embed.title or "결과" not in embed.title:
        return None
    m = re.search(r"ROUND\s+(\d+)", embed.title)
    if not m:
        return None
    round_num = int(m.group(1))
    team1, team2, winner = [], [], None
    for field in embed.fields:
        if "TEAM 1" in field.name or "TEAM1" in field.name:
            team1 = parse_team(field.value)
        elif "TEAM 2" in field.name or "TEAM2" in field.name:
            team2 = parse_team(field.value)
        elif "승리" in field.name:
            val = field.value.replace("*", "")
            if "TEAM1" in val or "TEAM 1" in val:
                winner = "team1"
            elif "TEAM2" in val or "TEAM 2" in val:
                winner = "team2"
    if not team1 or not team2 or not winner:
        return None
    return {"round": round_num, "team1": team1, "team2": team2, "winner": winner}


def content_key(g):
    # 채널 무관하게 같은 판이면 동일한 키 (내용 기반)
    t1 = tuple(sorted((p["id"], p["champ"]) for p in g["team1"]))
    t2 = tuple(sorted((p["id"], p["champ"]) for p in g["team2"]))
    return (g["round"], g["winner"], t1, t2)


@client.event
async def on_ready():
    print(f"[OK] Logged in as {client.user}")
    guild = discord.utils.get(client.guilds, id=GUILD_ID)
    if not guild:
        print("[ERROR] Guild not found")
        await client.close()
        return

    merged = {}  # content_key -> game record (+ sources, time)
    for name in CHANNELS:
        ch = discord.utils.get(guild.channels, name=name)
        if not ch:
            print(f"[SKIP] #{name} not found")
            continue
        cnt = 0
        async for message in ch.history(limit=None):
            if message.author != client.user:
                continue
            for embed in message.embeds:
                g = parse_result_embed(embed)
                if g is None:
                    continue
                cnt += 1
                key = content_key(g)
                ts = message.created_at
                if key not in merged:
                    g["time"] = ts.isoformat()
                    g["_ts"] = ts
                    g["sources"] = [CH_LABEL[name]]
                    merged[key] = g
                else:
                    e = merged[key]
                    if CH_LABEL[name] not in e["sources"]:
                        e["sources"].append(CH_LABEL[name])
                    if ts < e["_ts"]:  # 가장 이른 시각 유지
                        e["_ts"] = ts
                        e["time"] = ts.isoformat()
        print(f"[SCAN] #{name}: {cnt} result embeds")

    games = sorted(merged.values(), key=lambda x: x["_ts"])

    # 세션 구분(6시간 이상 공백이면 새 세션) + 라운드 갭 분석
    sessions = []
    for g in games:
        if not sessions or (g["_ts"] - sessions[-1][-1]["_ts"]) > timedelta(hours=6):
            sessions.append([])
        sessions[-1].append(g)

    # 플레이어 이름
    players = {}
    for g in games:
        for tk in ("team1", "team2"):
            for p in g[tk]:
                uid = p["id"]
                if uid not in players:
                    m = guild.get_member(int(uid))
                    players[uid] = NAME_MAP.get(uid) or (m.display_name if m else uid)

    for g in games:
        del g["_ts"]

    # 세션 요약(ASCII 위주, 콘솔 깨짐 방지)
    print("\n" + "=" * 64)
    print(f"[TOTAL] {len(games)} unique games recovered from {len(CHANNELS)} channels")
    print("=" * 64)
    report = []
    for i, sess in enumerate(sessions, 1):
        rounds = [g["round"] for g in sess]
        date = sess[0]["time"][:10]
        rmin, rmax = min(rounds), max(rounds)
        expected = set(range(rmin, rmax + 1))
        missing = sorted(expected - set(rounds))
        dups = sorted(set(r for r in rounds if rounds.count(r) > 1))
        # 채널별 커버리지
        only = {"T1": 0, "T2": 0, "CMD": 0}
        full = 0
        for g in sess:
            if len(g["sources"]) == 3:
                full += 1
            for s in g["sources"]:
                only[s] += 1
        line = (f"S{i:02d} {date} | rounds {rmin}-{rmax} | {len(sess)} games | "
                f"missing={missing if missing else '-'} dup={dups if dups else '-'} | "
                f"cover T1={only['T1']} T2={only['T2']} CMD={only['CMD']} all3={full}")
        print(line)
        report.append({
            "session": i, "date": date, "round_min": rmin, "round_max": rmax,
            "games": len(sess), "missing_rounds": missing, "dup_rounds": dups,
            "coverage": only, "all3": full,
        })

    out = {
        "generated_at": games[-1]["time"] if games else None,
        "channels": CHANNELS,
        "total_games": len(games),
        "players": players,
        "sessions_summary": report,
        "games": games,
    }
    with open("history_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n[SAVED] history_data.json")

    await client.close()


client.run(token)
