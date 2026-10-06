import json
import os
import re
import threading
import time
from html import escape

import telebot
from telebot import types

from Source.Parser import Rule34Parser, is_blocked


MAX_FILE = 49 * 1024 * 1024
MAX_PHOTO = 10 * 1024 * 1024
MAX_PAGES = 5
CAPTION_LIMIT = 1024

SEPARATOR = "✧ ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ ✧"
FOOTER = "MLM | YAOI"


def hashtag(tag: str) -> str:
    clean = re.sub(r"\W+", "_", tag, flags=re.UNICODE)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return f"#{clean}" if clean else ""


class Rule34Bot:

    def __init__(self, settings: dict):
        self.settings = settings

        self.bot = telebot.TeleBot(
            settings["token"],
            parse_mode="HTML"
        )

        self.parser = Rule34Parser(settings)

        self.channel = str(
            settings["channel_id"]
        ).strip()

        self.lock = threading.Lock()
        self.running = True

        self.autopost_running = bool(
            settings.get("autopost", False)
        )

        self.interval = max(
            int(settings.get("interval", 30) or 30),
            5
        )

        self.next_post_at = (
            time.time() + self.interval
            if self.autopost_running
            else 0
        )

        self.data_path = os.path.join(
            "Data",
            "Posts.json"
        )

        self.data = self._load_data()
        self.sent_set = set(self.data["sent"])

        self.last_error_at = 0.0

        self._register_handlers()

    def _load_data(self):
        try:
            with open(
                self.data_path,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

        except (
            FileNotFoundError,
            json.JSONDecodeError
        ):
            data = {}

        data.setdefault("sent", [])

        return data

    def _save_data(self):
        with open(
            self.data_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                self.data,
                f,
                ensure_ascii=False,
                indent=2
            )

    def _save_settings(self):
        with open(
            "Settings.json",
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                self.settings,
                f,
                ensure_ascii=False,
                indent=2
            )

    def _mark_sent(self, post_id: int):
        if post_id in self.sent_set:
            return

        self.sent_set.add(post_id)

        sent = self.data["sent"]
        sent.append(post_id)

        if len(sent) > 20000:
            del sent[:-20000]
            self.sent_set = set(sent)

        self._save_data()

    def _admins(self) -> list:
        return self.settings.setdefault(
            "admin_ids",
            []
        )

    def _is_admin(self, user_id: int) -> bool:
        return user_id in self._admins()

    def _claim_if_free(self, message) -> bool:
        if (
            not self._admins()
            and message.chat.type == "private"
        ):
            self._admins().append(
                message.from_user.id
            )

            self._save_settings()

            return True

        return False

    def _notify_admins(
        self,
        text: str,
        throttle: bool = True
    ):
        now = time.time()

        if (
            throttle
            and now - self.last_error_at < 600
        ):
            return

        self.last_error_at = now

        for uid in self._admins():
            try:
                self.bot.send_message(
                    uid,
                    text
                )
            except Exception:
                pass

    def _tags_text(self) -> str:
        tags = self.settings.get(
            "tags",
            []
        )

        if not tags:
            return "не выбраны"

        return ", ".join(
            f"<code>{escape(t)}</code>"
            for t in tags
        )

    def _menu(self):
        kb = types.InlineKeyboardMarkup()

        kb.row(
            types.InlineKeyboardButton(
                "➕ Добавить тег",
                callback_data="add"
            ),
            types.InlineKeyboardButton(
                "➖ Удалить тег",
                callback_data="remove"
            )
        )

        kb.row(
            types.InlineKeyboardButton(
                "📋 Теги",
                callback_data="show"
            ),
            types.InlineKeyboardButton(
                "🧹 Очистить",
                callback_data="clear"
            )
        )

        kb.row(
            types.InlineKeyboardButton(
                "▶️ Старт",
                callback_data="start"
            ),
            types.InlineKeyboardButton(
                "⏹ Стоп",
                callback_data="stop"
            )
        )

        kb.row(
            types.InlineKeyboardButton(
                "📨 Один пост сейчас",
                callback_data="once"
            )
        )

        return kb

    def _status_text(self) -> str:
        state = (
            "🟢 работает"
            if self.autopost_running
            else "🔴 остановлена"
        )

        return (
            "<b>Rule34 → канал</b>\n\n"
            f"Теги поиска: {self._tags_text()}\n"
            f"Автопубликация: {state} "
            f"(каждые {self.interval} с)\n"
            f"Уже опубликовано: "
            f"{len(self.sent_set)}\n\n"
            "/addtag <code>tag1 tag2</code> — "
            "добавить теги\n"
            "/deltag <code>tag</code> — "
            "удалить тег\n"
            "/tags — показать теги\n"
            "/clear — очистить теги\n"
            "/post — запустить автопубликацию\n"
            "/stop — остановить\n"
            "/once — опубликовать один пост сейчас"
        )

    def _register_handlers(self):
        bot = self.bot

        def admin_only(handler):
            def wrapper(message):
                if message.chat.type != "private":
                    return

                if not self._is_admin(
                    message.from_user.id
                ):
                    return

                handler(message)

            return wrapper

        @bot.message_handler(
            commands=["start", "help"]
        )
        def start(message):
            if message.chat.type != "private":
                return

            if self._claim_if_free(message):
                bot.send_message(
                    message.chat.id,
                    "✅ Вы назначены администратором бота."
                )

            if not self._is_admin(
                message.from_user.id
            ):
                return

            bot.send_message(
                message.chat.id,
                self._status_text(),
                reply_markup=self._menu()
            )

        @bot.message_handler(
            commands=["addtag"]
        )
        @admin_only
        def addtag(message):
            parts = message.text.split()[1:]

            if not parts:
                bot.reply_to(
                    message,
                    "Использование: "
                    "/addtag <code>tag1 tag2</code>"
                )
                return

            added = []
            rejected = []

            tags = self.settings.setdefault(
                "tags",
                []
            )

            for raw in parts:
                tag = raw.strip().lower()

                if (
                    not tag
                    or is_blocked(
                        [tag],
                        self.settings.get(
                            "exclude_tags"
                        )
                    )
                ):
                    rejected.append(raw)
                    continue

                if tag not in tags:
                    tags.append(tag)
                    added.append(tag)

            self._save_settings()

            msg = ""

            if added:
                msg += (
                    "Добавлено: "
                    + ", ".join(
                        f"<code>{escape(t)}</code>"
                        for t in added
                    )
                    + "\n"
                )

            if rejected:
                msg += (
                    "Не принято: "
                    + ", ".join(
                        escape(t)
                        for t in rejected
                    )
                    + "\n"
                )

            msg += (
                f"Теги поиска: "
                f"{self._tags_text()}"
            )

            bot.reply_to(
                message,
                msg
            )

        @bot.message_handler(
            commands=["deltag"]
        )
        @admin_only
        def deltag(message):
            parts = message.text.split()[1:]

            if not parts:
                bot.reply_to(
                    message,
                    "Использование: "
                    "/deltag <code>tag</code>"
                )
                return

            tags = self.settings.setdefault(
                "tags",
                []
            )

            removed = [
                t.lower()
                for t in parts
                if t.lower() in tags
            ]

            for tag in removed:
                tags.remove(tag)

            self._save_settings()

            text = (
                "Удалено: "
                + ", ".join(removed)
                if removed
                else "Таких тегов нет."
            )

            text += (
                f"\nТеги поиска: "
                f"{self._tags_text()}"
            )

            bot.reply_to(
                message,
                text
            )

        @bot.message_handler(
            commands=["tags"]
        )
        @admin_only
        def tags_cmd(message):
            bot.reply_to(
                message,
                f"Теги поиска: "
                f"{self._tags_text()}",
                reply_markup=self._menu()
            )

        @bot.message_handler(
            commands=["clear"]
        )
        @admin_only
        def clear(message):
            self.settings["tags"] = []

            self._save_settings()

            bot.reply_to(
                message,
                "Теги очищены."
            )

        @bot.message_handler(
            commands=["post"]
        )
        @admin_only
        def post_cmd(message):
            self.start_autopost(
                message.chat.id
            )

        @bot.message_handler(
            commands=["stop"]
        )
        @admin_only
        def stop_cmd(message):
            self.stop_autopost(
                message.chat.id
            )

        @bot.message_handler(
            commands=["once", "search"]
        )
        @admin_only
        def once_cmd(message):
            threading.Thread(
                target=self._once,
                args=(message.chat.id,),
                daemon=True
            ).start()

        @bot.callback_query_handler(
            func=lambda call: True
        )
        def callbacks(call):
            bot.answer_callback_query(
                call.id
            )

            if not self._is_admin(
                call.from_user.id
            ):
                return

            chat_id = call.message.chat.id
            action = call.data

            if action == "show":
                bot.send_message(
                    chat_id,
                    f"Теги поиска: "
                    f"{self._tags_text()}",
                    reply_markup=self._menu()
                )

            elif action == "add":
                bot.send_message(
                    chat_id,
                    "Напишите: "
                    "/addtag <code>tag1 tag2</code>"
                )

            elif action == "remove":
                bot.send_message(
                    chat_id,
                    "Напишите: "
                    "/deltag <code>tag</code>"
                )

            elif action == "clear":
                self.settings["tags"] = []

                self._save_settings()

                bot.send_message(
                    chat_id,
                    "Теги очищены."
                )

            elif action == "start":
                self.start_autopost(
                    chat_id
                )

            elif action == "stop":
                self.stop_autopost(
                    chat_id
                )

            elif action == "once":
                threading.Thread(
                    target=self._once,
                    args=(chat_id,),
                    daemon=True
                ).start()

    def start_autopost(self, chat_id):
        if not self.settings.get("tags"):
            self.bot.send_message(
                chat_id,
                "Сначала добавьте тег: "
                "/addtag <code>tag</code>"
            )
            return

        if self.autopost_running:
            self.bot.send_message(
                chat_id,
                "Автопубликация уже запущена."
            )
            return

        self.autopost_running = True
        self.settings["autopost"] = True

        self._save_settings()

        self.next_post_at = time.time()

        self.bot.send_message(
            chat_id,
            f"▶️ Автопубликация запущена: "
            f"пост каждые {self.interval} с."
        )

    def stop_autopost(self, chat_id):
        self.autopost_running = False
        self.next_post_at = 0

        self.settings["autopost"] = False

        self._save_settings()

        self.bot.send_message(
            chat_id,
            "⏹ Автопубликация остановлена."
        )

    def _once(self, chat_id):
        if not self.settings.get("tags"):
            self.bot.send_message(
                chat_id,
                "Сначала добавьте тег: "
                "/addtag <code>tag</code>"
            )
            return

        try:
            ok = self.publish_next()

            self.bot.send_message(
                chat_id,
                "✅ Опубликовано."
                if ok
                else
                "Новых постов по этим тегам "
                "не найдено."
            )

        except Exception as e:
            self.bot.send_message(
                chat_id,
                "Ошибка: "
                f"<code>{escape(str(e))}</code>"
            )

    def _autopost_loop(self):
        while self.running:
            if (
                self.autopost_running
                and self.settings.get("tags")
                and time.time() >= self.next_post_at
            ):
                try:
                    ok = self.publish_next()

                    if not ok:
                        self._notify_admins(
                            "ℹ️ По выбранным тегам "
                            "новых постов не найдено."
                        )

                except Exception as e:
                    print(
                        "Ошибка автопубликации:",
                        e
                    )

                    self._notify_admins(
                        "⚠️ Ошибка автопубликации: "
                        f"<code>{escape(str(e))}</code>"
                    )

                self.next_post_at = (
                    time.time() + self.interval
                )

            time.sleep(0.5)

    def build_caption(self, post: dict) -> str:
        def join(items, sep):
            return sep.join(
                h
                for h in (
                    hashtag(x)
                    for x in items
                )
                if h
            )

        characters = (
            join(
                post.get("characters", []),
                " & "
            )
            or "#Unknown"
        )

        fandoms = (
            join(
                post.get("fandoms", []),
                " & "
            )
            or "#Unknown"
        )

        head = (
            f"{SEPARATOR}\n"
            f"Character: {escape(characters)}\n"
            f"Fandom: {escape(fandoms)}\n"
            f"{SEPARATOR}\n\n"
        )

        tail = f"\n\n{FOOTER}"

        tag_items = [
            h
            for h in (
                hashtag(t)
                for t in post.get(
                    "general",
                    []
                )
            )
            if h
        ]

        line = []
        used = (
            len(head)
            + len("tags: ")
            + len(tail)
        )

        for h in tag_items:
            if (
                used
                + len(h)
                + 1
                > CAPTION_LIMIT
            ):
                break

            line.append(
                escape(h)
            )

            used += len(h) + 1

        return (
            f"{head}"
            f"tags: "
            f"{' '.join(line) if line else '#none'}"
            f"{tail}"
        )

    def _find_next_post(self):
        tags = self.settings["tags"]
        extra = self.settings.get(
            "exclude_tags"
        )

        for page in range(MAX_PAGES):
            ids = self.parser.list_post_ids(
                tags,
                page
            )

            if not ids:
                return None

            for pid in ids:
                if pid in self.sent_set:
                    continue

                post = self.parser.get_post(pid)

                if post is None:
                    self._mark_sent(pid)
                    continue

                if is_blocked(
                    post["all_tags"],
                    extra
                ):
                    self._mark_sent(pid)
                    continue

                return post

        return None

    def publish_next(self) -> bool:
        with self.lock:
            for _ in range(5):
                post = self._find_next_post()

                if post is None:
                    return False

                result = self._send_post(post)

                if result:
                    return True

            return False

    def _send_post(self, post: dict):
        path = None

        try:
            os.makedirs(
                "Temp",
                exist_ok=True
            )

            path = self.parser.download(
                post["file_url"],
                os.path.join(
                    "Temp",
                    str(post["id"])
                )
            )

            size = os.path.getsize(path)

            if size > MAX_FILE:
                self._mark_sent(
                    post["id"]
                )
                return None

            caption = self.build_caption(
                post
            )

            lower = path.lower()

            with open(
                path,
                "rb"
            ) as f:

                if lower.endswith(".gif"):
                    self.bot.send_animation(
                        self.channel,
                        f,
                        caption=caption
                    )

                elif lower.endswith(
                    (".mp4", ".webm")
                ):
                    if lower.endswith(".mp4"):
                        self.bot.send_video(
                            self.channel,
                            f,
                            caption=caption,
                            supports_streaming=True
                        )
                    else:
                        self.bot.send_document(
                            self.channel,
                            f,
                            caption=caption
                        )

                elif size <= MAX_PHOTO:
                    try:
                        self.bot.send_photo(
                            self.channel,
                            f,
                            caption=caption
                        )

                    except telebot.apihelper.ApiTelegramException as e:
                        if (
                            "PHOTO_" in str(e)
                            or "too big"
                            in str(e).lower()
                        ):
                            f.seek(0)

                            self.bot.send_document(
                                self.channel,
                                f,
                                caption=caption
                            )
                        else:
                            raise

                else:
                    self.bot.send_document(
                        self.channel,
                        f,
                        caption=caption
                    )

            self._mark_sent(
                post["id"]
            )

            return True

        except Exception:
            self._mark_sent(
                post["id"]
            )
            raise

        finally:
            if (
                path
                and os.path.exists(path)
            ):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def run(self):
        threading.Thread(
            target=self._autopost_loop,
            daemon=True
        ).start()

        print("Бот запущен.")
        print(
            "Теги:",
            ", ".join(
                self.settings.get(
                    "tags",
                    []
                )
            ) or "не выбраны"
        )
        print(
            "Канал:",
            self.channel,
            "| интервал:",
            self.interval,
            "с"
        )

        if not self._admins():
            print(
                "Админ не задан: "
                "отправьте боту /start "
                "в личные сообщения, "
                "чтобы стать админом."
            )

        while self.running:
            try:
                print(
                    "Telegram polling запущен."
                )

                self.bot.infinity_polling(
                    skip_pending=True,
                    timeout=60,
                    long_polling_timeout=50
                )

            except KeyboardInterrupt:
                print(
                    "Бот остановлен."
                )
                self.running = False
                break

            except Exception as e:
                print(
                    "Ошибка Telegram polling:",
                    e
                )
                print(
                    "Повторное подключение "
                    "через 5 секунд..."
                )

                time.sleep(5)