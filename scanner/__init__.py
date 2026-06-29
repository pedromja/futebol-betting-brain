"""Scanner automático de jogos e ranking."""

__all__ = ["ScanRanker", "ScanResult", "RankedMatch"]


def __getattr__(name: str):
    if name in __all__:
        from .ranker import ScanRanker, ScanResult, RankedMatch
        return {"ScanRanker": ScanRanker, "ScanResult": ScanResult, "RankedMatch": RankedMatch}[name]
    raise AttributeError(name)