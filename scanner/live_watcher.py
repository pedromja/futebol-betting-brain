"""Loop de vigilância live — alertas de golo e novas oportunidades."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from scanner.live_ranker import LiveScanRanker, LiveScanResult


@dataclass
class _MatchSnapshot:
    score: str
    minute: int
    should_bet: bool = False
    best_market: str = ""


@dataclass
class LiveWatchState:
    snapshots: dict[str, _MatchSnapshot] = field(default_factory=dict)
    last_best_key: str = ""


class LiveWatcher:
    def __init__(
        self,
        *,
        interval: int = 45,
        league_filter: str | None = None,
        min_score: float = 0.55,
        bankroll: float | None = None,
        max_games: int = 15,
        prefer_live_odds: bool = True,
        api_football_key: str | None = None,
        football_data_key: str | None = None,
        weather_api_key: str | None = None,
        xai_api_key: str | None = None,
    ):
        self.interval = max(15, interval)
        self.ranker = LiveScanRanker(
            api_football_key=api_football_key,
            football_data_key=football_data_key,
            weather_api_key=weather_api_key,
            xai_api_key=xai_api_key,
            min_score=min_score,
            bankroll=bankroll,
            max_games=max_games,
            league_filter=league_filter,
            prefer_live_odds=prefer_live_odds,
        )
        self.state = LiveWatchState()

    @staticmethod
    def _match_key(home: str, away: str) -> str:
        return f"{home}|{away}"

    def _alert(self, message: str) -> None:
        print(f"\n  🔔 {message}")
        if sys.platform == "win32":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                print("\a", end="", flush=True)
        else:
            print("\a", end="", flush=True)

    def _process_alerts(self, result: LiveScanResult) -> list[str]:
        alerts: list[str] = []
        seen: set[str] = set()

        for row in result.ranked:
            fx = row.fixture
            key = self._match_key(fx.home, fx.away)
            seen.add(key)
            score = fx.score_label
            prev = self.state.snapshots.get(key)

            if prev and prev.score != score:
                msg = (
                    f"GOLO! {fx.home} {score} {fx.away} ({fx.minute}') "
                    f"— era {prev.score}"
                )
                self._alert(msg)
                alerts.append(msg)

            if row.should_bet and (not prev or not prev.should_bet):
                msg = (
                    f"OPORTUNIDADE: {fx.home} vs {fx.away} "
                    f"{score} ({fx.minute}') → {row.best_market} "
                    f"EV {row.best_ev*100:+.0f}%"
                )
                self._alert(msg)
                alerts.append(msg)

            self.state.snapshots[key] = _MatchSnapshot(
                score=score,
                minute=fx.minute,
                should_bet=row.should_bet,
                best_market=row.best_market,
            )

        for key in list(self.state.snapshots):
            if key not in seen:
                del self.state.snapshots[key]

        if result.best and result.best.should_bet:
            fx = result.best.fixture
            best_key = self._match_key(fx.home, fx.away)
            if best_key != self.state.last_best_key:
                self.state.last_best_key = best_key

        return alerts

    def run_once(self) -> LiveScanResult:
        return self.ranker.scan_and_rank()

    def run_loop(self) -> None:
        print("\n  LIVE WATCH — vigilância automática")
        print(f"  Intervalo: {self.interval}s | Ctrl+C para parar")
        print("  Dicas guardadas em data/predictions.jsonl")
        print("")

        try:
            while True:
                result = self.run_once()
                alerts = self._process_alerts(result)

                live_n = result.total_live
                bet_n = sum(1 for r in result.ranked if r.should_bet)
                ts = result.scanned_at.split("T")[-1][:8]
                print(
                    f"  [{ts}] {live_n} ao vivo · {result.total_analyzed} analisados · "
                    f"{bet_n} apostáveis"
                    + (f" · {len(alerts)} alertas" if alerts else "")
                )

                if result.best and result.best.should_bet:
                    b = result.best
                    fx = b.fixture
                    stake = (
                        f" · {b.stake_plan.display}"
                        if b.stake_plan
                        else ""
                    )
                    print(
                        f"    ★ {fx.score_label} {fx.home} vs {fx.away} "
                        f"({fx.minute}') — {b.best_market} "
                        f"EV {b.best_ev*100:+.0f}%{stake}"
                    )

                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n  Live watch terminado.\n")