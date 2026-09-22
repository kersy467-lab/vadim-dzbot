import os
import subprocess
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def test_frontend_modules_with_node():
    script_path = os.path.join(os.path.dirname(__file__), "test_frontend_modules.js")
    res = subprocess.run(["node", script_path], capture_output=True, text=True, encoding="utf-8")
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    assert res.returncode == 0, f"Node test failed with returncode {res.returncode}"


def test_duel_frontend_sends_answers_not_a_client_side_verdict():
    root = os.path.dirname(__file__)
    with open(os.path.join(root, "../frontend/js/ege/ege_duel.js"), encoding="utf-8") as source_file:
        source = source_file.read()
    assert "room.question" in source
    assert "sendGameMove(room.room_id, { answer" in source
    assert "{ correct }" not in source

if __name__ == "__main__":
    test_frontend_modules_with_node()
    print("Python test runner: SUCCESS!")
