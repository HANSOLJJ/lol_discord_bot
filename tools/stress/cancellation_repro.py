# 연결 종료 중 요청 취소가 입장 집계와 태스크 정리에 미치는 영향을 비교한다.
import asyncio
import json
import time
from pathlib import Path

from presence_stress import OUT, pending_presence_case, run_case


async def main():
    started = time.perf_counter()
    results = []
    for testserver in (False, True):
        for repeat in range(10):
            result = await run_case("pending_presence", pending_presence_case, testserver=testserver)
            result.update(server="TestServer" if testserver else "ActivityServer.start", repeat=repeat)
            results.append(result)
    OUT.mkdir(exist_ok=True)
    root = OUT
    (root / "cancellation-comparison.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    summary = {"seconds": round(time.perf_counter() - started, 3),
               "native_passed": sum(r["status"] == "passed" and r["server"] == "ActivityServer.start" for r in results),
               "testserver_passed": sum(r["status"] == "passed" and r["server"] == "TestServer" for r in results)}
    (root / "cancellation-comparison.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
