# Rule34 → Telegram-канал

Бот использует официальный API rule34.xxx для поиска и получения постов, берёт изображение и теги оттуда же
и публикует в канал по шаблону каждые 30 секунд, пока не нажать «Стоп».

## Запуск (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

1. Добавьте бота **администратором канала** (право «Публикация сообщений»).
2. Запустите `main.py`, напишите боту в личные сообщения `/start` — вы станете администратором.
3. `/addtag yaoi male_only` — выбрать теги (поиск идёт по всем сразу).
4. `/post` — старт автопубликации, `/stop` — стоп. `/once` — один пост сейчас.

## Settings.json

| поле | значение |
|---|---|
| token | токен бота |
| channel_id | id канала (`-100...`) |
| admin_ids | заполняется автоматически |
| interval | интервал в секундах (30) |
| proxy | например `http://127.0.0.1:8080` или `socks5://...` (если API/Telegram недоступны) |
| api_user_id | ID пользователя Rule34 для API |
| api_key | API-ключ Rule34 |
| exclude_tags | теги, исключаемые из поиска |

Для socks-прокси: `pip install requests[socks]`.

API-ключ и `api_user_id` берутся в настройках аккаунта Rule34 в разделе API Access Credentials. Без них API может вернуть 403.

## Формат поста

```
✧ ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ ✧
Character: #Character1 & #Character2
Fandom: #Fandom
✧ ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ ✧

tags: #tag1 #tag2 #tag3

MLM | YAOI
```

Character / Fandom берутся из тегов типов `character` / `copyright`, tags — из общих (`general`) тегов поста.
Теги художника и служебные (metadata) не публикуются.

## Фильтр

Посты с тегами loli/shota/child/underage и подобными пропускаются всегда — на уровне каждого поста,
независимо от настроек.
