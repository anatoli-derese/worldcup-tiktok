#!/usr/bin/env python3
"""Run pipeline for Mexico vs South Africa opener."""
from src.match_data import MatchInfo
from src.pipeline import _process_match

match = MatchInfo(
    id='mex_rsa_opener',
    home_team='Mexico', away_team='South Africa',
    home_score=2, away_score=0, status='FINISHED',
    events=[],
)
result = _process_match(match)
print(f"FORMAL: {result['formal_video']}")
print(f"CASUAL: {result['casual_video']}")
