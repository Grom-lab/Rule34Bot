import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from Source.Bot import Rule34Bot


def load_settings() -> dict:
    try:
        with open("Settings.json", "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit("Не найден Settings.json")
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"Settings.json содержит ошибку в строке {e.lineno}, "
            f"позиции {e.colno}: {e.msg}\n"
            "Проверьте кавычки в JSON."
        )


if __name__ == "__main__":
    settings = load_settings()

    if not str(settings.get("token", "")).strip():
        raise SystemExit("Укажите token в Settings.json")

    if not str(settings.get("channel_id", "")).strip():
        raise SystemExit("Укажите channel_id в Settings.json")

    proxy = (settings.get("proxy") or "").strip()

    if proxy:
        from telebot import apihelper

        apihelper.proxy = {
            "http": proxy,
            "https": proxy
        }

    os.makedirs("Temp", exist_ok=True)
    os.makedirs("Data", exist_ok=True)

    Rule34Bot(settings).run()