"""The standalone game entry must never point Telegram at the school Mini App."""

from backend.config import get_natbirzha_webapp_url


def run() -> None:
    assert get_natbirzha_webapp_url("https://dzbot.example") == "https://dzbot.example/app/natbirzha"
    assert get_natbirzha_webapp_url("https://dzbot.example/") == "https://dzbot.example/app/natbirzha"
    assert get_natbirzha_webapp_url("https://dzbot.example/app") == "https://dzbot.example/app/natbirzha"
    assert get_natbirzha_webapp_url("https://dzbot.example/app/") == "https://dzbot.example/app/natbirzha"
    assert get_natbirzha_webapp_url("https://dzbot.example/app/natbirzha") == "https://dzbot.example/app/natbirzha"
    print("NATBIRZHA standalone WebApp URL checks: PASS")


if __name__ == "__main__":
    run()
