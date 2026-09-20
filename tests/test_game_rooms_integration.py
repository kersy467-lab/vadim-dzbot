import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app


def test_game_rooms_all():
    client = TestClient(app)
    
    print("=== [1/3] Testing TicTacToe and Chess invite link generation ===")
    # 1. TicTacToe invite
    res = client.post(
        "/api/games/invite",
        json={
            "opponent_tg_id": 999002,
            "host_name": "Player 1",
            "game_type": "tictactoe"
        },
        params={"user_id": 999001}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    ttt_room_id = res.json()["room_id"]
    assert ttt_room_id, "Room id should be generated"
    assert res.json()["game_type"] == "tictactoe"
    
    # 2. Chess invite
    res_chess = client.post(
        "/api/games/invite",
        json={
            "opponent_tg_id": 999002,
            "host_name": "Player 1",
            "game_type": "chess",
            "host_color": "white"
        },
        params={"user_id": 999001}
    )
    assert res_chess.status_code == 200, f"Expected 200, got {res_chess.status_code}: {res_chess.text}"
    chess_room_id = res_chess.json()["room_id"]
    assert chess_room_id, "Chess room id should be generated"
    assert res_chess.json()["game_type"] == "chess"
    print("[OK] TicTacToe and Chess invites generated successfully.")

    print("=== [2/3] Testing Room Joining & Moving ===")
    # Join TicTacToe
    join_ttt = client.post(
        f"/api/games/room/{ttt_room_id}/join",
        json={"user_name": "Opponent"},
        params={"user_id": 999002}
    )
    assert join_ttt.status_code == 200
    assert join_ttt.json()["status"] == "playing"

    # Move in TicTacToe
    move_ttt = client.post(
        f"/api/games/room/{ttt_room_id}/move",
        json={"cell": 0},
        params={"user_id": 999001}
    )
    assert move_ttt.status_code == 200
    assert move_ttt.json()["board"][0] == "X"

    # Join Chess
    join_chess = client.post(
        f"/api/games/room/{chess_room_id}/join",
        json={"user_name": "Opponent"},
        params={"user_id": 999002}
    )
    assert join_chess.status_code == 200
    assert join_chess.json()["status"] == "playing"

    # Move in Chess (e2e4)
    move_chess = client.post(
        f"/api/games/room/{chess_room_id}/move",
        json={"move": "e2e4"},
        params={"user_id": 999001}
    )
    assert move_chess.status_code == 200
    assert "e2e4" in move_chess.json()["last_move"]
    print("[OK] Online moves in TicTacToe and Chess executed correctly.")

    print("=== [3/3] Testing Durak Online Room & State API ===")
    # Create Durak online room
    res_durak = client.post(
        "/api/durak/new",
        json={
            "mode": "online",
            "players_count": 2,
            "stake": 0
        },
        params={"user_id": 999001}
    )
    assert res_durak.status_code == 200, f"Durak new failed: {res_durak.text}"
    durak_room_id = res_durak.json()["room_id"]
    assert durak_room_id, "Durak room id should be generated"

    # Check Durak state endpoint for auto-detecting room
    state_durak = client.get(f"/api/durak/state/{durak_room_id}", params={"user_id": 999001})
    assert state_durak.status_code == 200
    assert state_durak.json()["status"] == "waiting"

    # Join Durak room
    join_durak = client.post(
        "/api/durak/join",
        json={"room_id": durak_room_id},
        params={"user_id": 999002}
    )
    assert join_durak.status_code == 200
    assert join_durak.json()["status"] == "started"
    assert "state" in join_durak.json()
    print("[OK] Durak online room created, inspected and joined successfully.")

    print("\nALL ONLINE MULTIPLAYER ROOM TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    test_game_rooms_all()
