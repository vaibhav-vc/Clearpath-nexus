#!/usr/bin/env python3
"""Smoke test the live feeds against the real providers.

    python scripts/smoke_live_feeds.py            # both feeds
    python scripts/smoke_live_feeds.py --rail     # RailRadar only
    python scripts/smoke_live_feeds.py --ais      # aisstream only
    python scripts/smoke_live_feeds.py --ais-wait 120

Reads keys from .env / the environment. Costs a handful of RailRadar requests
(one per corridor station, ~5 of your 1,000/month) so it is not something to
run in a loop.

Exit codes: 0 all checks passed, 1 a configured feed failed, 2 nothing was
configured to test.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.services.congestion import resolve_congestion  # noqa: E402
from app.services.live_port import ais_collector  # noqa: E402
from app.services.live_rail import CORRIDOR_STATIONS, rail_client  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
OK, FAIL, WARN = f"{GREEN}PASS{RESET}", f"{RED}FAIL{RESET}", f"{YELLOW}WARN{RESET}"


def header(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


async def check_rail() -> bool:
    header("RailRadar - live corridor congestion")

    if not settings.RAILRADAR_API_KEY:
        print(f"  {WARN}  RAILRADAR_API_KEY not set - skipping")
        print(f"  {DIM}Get a free key at https://railradar.in/developers{RESET}")
        return True

    print(f"  {DIM}Stations: {', '.join(CORRIDOR_STATIONS)}{RESET}")
    print(f"  {DIM}Budget remaining before call: {rail_client.budget.remaining}{RESET}")

    started = datetime.now(timezone.utc)
    result = await rail_client.fetch_corridor()
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    print(f"\n  {'STATION':<8} {'SOURCE':<12} {'TRAINS':>7} {'MEAN DLY':>9} {'MAX DLY':>8}")
    for s in result.stations:
        note = f"  {DIM}{s.detail}{RESET}" if s.detail else ""
        print(
            f"  {s.station_code:<8} {s.source.value:<12} {s.train_count:>7} "
            f"{s.mean_delay_minutes:>8.1f}m {s.max_delay_minutes:>7}m{note}"
        )

    live = sum(1 for s in result.stations if s.available)
    print(f"\n  Corridor score : {result.score}  (100 = clear)")
    print(f"  Source         : {result.source.value}")
    print(f"  Stations live  : {live}/{len(result.stations)}")
    print(f"  Round trip     : {elapsed:.2f}s")
    print(f"  Budget left    : {rail_client.budget.remaining}")

    if not result.available:
        print(f"\n  {FAIL}  No usable corridor data: {result.detail}")
        return False
    if not 0 <= (result.score or -1) <= 100:
        print(f"\n  {FAIL}  Score out of range: {result.score}")
        return False

    print(f"\n  {OK}  Corridor congestion resolved from live data")
    return True


async def check_ais(wait_seconds: int) -> bool:
    header("aisstream.io - JNPT vessel activity")

    if not settings.AISSTREAM_API_KEY:
        print(f"  {WARN}  AISSTREAM_API_KEY not set - skipping")
        print(f"  {DIM}Get a free key at https://aisstream.io/apikeys{RESET}")
        return True

    print(f"  {DIM}Connecting to the stream; AIS position reports are sparse,{RESET}")
    print(f"  {DIM}so allowing up to {wait_seconds}s for the first vessel.{RESET}\n")

    await ais_collector.start()
    deadline = asyncio.get_event_loop().time() + wait_seconds
    last_count = -1

    try:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            snap = ais_collector.snapshot()
            if snap.vessels_tracked != last_count:
                last_count = snap.vessels_tracked
                remaining = int(deadline - asyncio.get_event_loop().time())
                print(f"  {DIM}[{remaining:>3}s left]{RESET} vessels tracked: {last_count}")
            if snap.vessels_tracked >= 3:
                break

        snap = ais_collector.snapshot()
        print(f"\n  Source          : {snap.source.value}")
        print(f"  Vessels tracked : {snap.vessels_tracked}")
        print(f"  At anchor       : {snap.at_anchor}")
        print(f"  Moored at berth : {snap.moored_at_berth}")
        print(f"  Underway        : {snap.underway}")
        print(f"  Congestion      : {snap.congestion_pct}%")
        if snap.detail:
            print(f"  Detail          : {snap.detail}")

        if not snap.available:
            print(f"\n  {WARN}  No vessels seen in {wait_seconds}s.")
            print(f"  {DIM}Not necessarily a failure - JNPT traffic is intermittent and{RESET}")
            print(f"  {DIM}aisstream is BETA. Retry with --ais-wait 180 before concluding.{RESET}")
            return True

        print(f"\n  {OK}  Live AIS data flowing")
        return True
    finally:
        await ais_collector.stop()


async def check_blend() -> bool:
    """Confirm live readings actually reach the score."""
    header("End-to-end - does live data reach the reliability score?")

    class Seg:
        congestion_factor = 1.4
        historical_delay_hours = 0.5

    segments = [Seg(), Seg()]

    static_only = await resolve_congestion(segments, dest_code="JNPT", use_live=False)
    blended = await resolve_congestion(segments, dest_code="JNPT", use_live=True)

    print(f"  Static baseline : {static_only.score}")
    print(f"  With live data  : {blended.score}   [{blended.source.value}]")
    if blended.live_rail_score is not None:
        print(f"  Live rail score : {blended.live_rail_score}  (weight {blended.live_weight})")
    if blended.port_congestion_pct is not None:
        print(f"  Port congestion : {blended.port_congestion_pct}%  "
              f"(penalty -{blended.port_penalty})")
    for alert in blended.alerts:
        print(f"  {YELLOW}alert{RESET}         : {alert}")

    if not blended.uses_live_data:
        print(f"\n  {WARN}  Score is static-only: {blended.detail.get('reason')}")
        print(f"  {DIM}Expected when no keys are set. Set them to exercise the blend.{RESET}")
        return True

    if blended.score == static_only.score:
        print(f"\n  {WARN}  Live data reached the resolver but did not move the score.")
        print(f"  {DIM}Possible if live conditions happen to match the baseline.{RESET}")
    else:
        delta = blended.score - static_only.score
        print(f"\n  {OK}  Live data moved congestion by {delta:+.1f} points")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rail", action="store_true", help="RailRadar only")
    parser.add_argument("--ais", action="store_true", help="aisstream only")
    parser.add_argument("--ais-wait", type=int, default=90, help="seconds to wait for AIS")
    args = parser.parse_args()

    run_rail = args.rail or not args.ais
    run_ais = args.ais or not args.rail

    print("ClearPath Nexus - live feed smoke test")
    print(f"{DIM}{datetime.now(timezone.utc).isoformat()}{RESET}")

    if not settings.RAILRADAR_API_KEY and not settings.AISSTREAM_API_KEY:
        print(f"\n  {WARN}  Neither key is configured - nothing to test.")
        print(f"  {DIM}Set RAILRADAR_API_KEY and/or AISSTREAM_API_KEY in .env{RESET}")
        return 2

    results = []
    if run_rail:
        results.append(await check_rail())
    if run_ais:
        results.append(await check_ais(args.ais_wait))
    if run_rail and run_ais:
        results.append(await check_blend())

    header("Summary")
    if all(results):
        print(f"  {OK}  All configured feeds behaved correctly\n")
        return 0
    print(f"  {FAIL}  One or more feeds failed - see above\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
