import json
import os
from typing import Optional, Tuple
from geopy.geocoders import Nominatim

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "cache", "geocode_cache.json")


def ensure_cache():
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    if not os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "w", encoding="utf-8") as fp:
            json.dump({}, fp)


def load_cache():
    ensure_cache()
    with open(CACHE_PATH, "r", encoding="utf-8") as fp:
        return json.load(fp)


def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as fp:
        json.dump(cache, fp, ensure_ascii=False, indent=2)


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    cache = load_cache()
    if address in cache:
        return cache[address]["lat"], cache[address]["lon"]
    locator = Nominatim(user_agent="cvrptw-alns-app")
    location = locator.geocode(address)
    if location:
        cache[address] = {"lat": location.latitude, "lon": location.longitude}
        save_cache(cache)
        return location.latitude, location.longitude
    return None
