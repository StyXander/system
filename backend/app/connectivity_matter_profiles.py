"""Explicit demonstration profiles; none supplies an amount or business conclusion."""
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=1)
def profiles():
    return json.loads(Path(__file__).with_name('connectivity_candidate_profiles.json').read_text())['profiles']

def candidate_profile(company_id,period):
    return next((p for p in profiles() if p['company_id']==company_id and p['report_period']==period),{})
