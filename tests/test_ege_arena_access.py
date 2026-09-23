import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.public_access import is_public_arena_path
from backend.db.crud.ege_users import has_full_access
from backend.ege.ranking import LEADERBOARD_TTL_SECONDS, normalize_nickname, validate_nickname, medal_for_rating


def test_leaderboard_refresh_is_ten_minutes():
    assert LEADERBOARD_TTL_SECONDS == 600


def test_nickname_normalization_is_case_insensitive():
    assert normalize_nickname("  NotariusPiva ") == normalize_nickname("notariuspiva")
    assert normalize_nickname("ЁЖИК") == normalize_nickname("ёжик")


def test_nickname_validation_accepts_safe_game_nicks_and_rejects_markup():
    assert validate_nickname("notariuspiva")[0] is True
    assert validate_nickname("ЕГЭ_Арена-7")[0] is True
    assert validate_nickname("<b>hack</b>")[0] is False
    assert validate_nickname("a")[0] is False


def test_classmate_privilege_controls_full_access():
    public = SimpleNamespace(role="public", is_classmate=False)
    classmate = SimpleNamespace(role="public", is_classmate=True)
    legacy_student = SimpleNamespace(role="student", is_classmate=False)
    admin = SimpleNamespace(role="admin", is_classmate=False)
    assert has_full_access(public) is False
    assert has_full_access(classmate) is True
    assert has_full_access(legacy_student) is True
    assert has_full_access(admin) is True
    assert has_full_access(None) is False


def test_only_arena_api_surface_is_public():
    assert is_public_arena_path("/api/ege/profile")
    assert is_public_arena_path("/api/ege/profile/notariuspiva")
    assert is_public_arena_path("/api/ege/leaderboard")
    assert is_public_arena_path("/api/ege/players")
    assert is_public_arena_path("/api/ege/matchmaking/search")
    assert is_public_arena_path("/api/games/room/abc123")
    assert not is_public_arena_path("/api/homework")
    assert not is_public_arena_path("/api/games/classmates")
    assert not is_public_arena_path("/api/games/local")
    assert not is_public_arena_path("/api/natbirzha/companies")


def test_all_rank_images_exist_and_special_titans_are_distinct():
    keys = ["recruit", "guardian", "knight", "hero", "legend", "lord", "divine", "titan"]
    paths = []
    for rating, key in zip((0, 100, 200, 300, 400, 500, 600, 800), keys):
        medal = medal_for_rating(rating)
        assert medal["image_key"] == key
        path = Path(medal["image_path"])
        assert path.exists() and path.stat().st_size > 10_000
        thumb = Path("frontend") / medal["image_url"].removeprefix("/static/")
        assert thumb.exists() and thumb.stat().st_size > 5_000
        paths.append(path)
    for place in range(1, 6):
        medal = medal_for_rating(900, place)
        assert medal["display_name"] == f"Титан ({place})"
        assert medal["image_key"] == f"titan_top_{place}"
        path = Path(medal["image_path"])
        assert path.exists() and path.stat().st_size > 10_000
        thumb = Path("frontend") / medal["image_url"].removeprefix("/static/")
        assert thumb.exists() and thumb.stat().st_size > 5_000
        paths.append(path)
    assert len({p.name for p in paths}) == 13
