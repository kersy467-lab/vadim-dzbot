# НАТБИРЖА — P0/P2 hardening report

Дата проверки: 2026-09-19.

## P2: войны, турниры и premium-контур

- Добавлены шесть нормализованных типов войск, серверные уровни/готовность и
  совместимый ответ для старого frontend.
- Чистый детерминированный resolver считает разведку, воздух, землю,
  контрклассы, ±5% seed-разброс и потери обеих сторон.
- Добавлены 12 PvE-корпораций, разведка, одноразовый захват территории, награды,
  журнал боя и военный рейтинг.
- PvP работает только в активном 18-часовом турнире. После победы действует
  двухчасовой cooldown на конкретную пару; территория и экономика игроков не
  передаются.
- Автотурнир создаётся раз в 72 часа, переживает рестарт scheduler и выдаёт
  top-3 `150/100/70 PVC` через idempotent ledger.
- Creator запускает custom-турнир с тремя отдельными наградами 0–10 000 PVC;
  запуск записывается в audit log.
- `nat_balance` безопасно переносится в отдельный `pvc_balance`. Все начисления
  и списания PVC имеют immutable ledger entry.
- Premium-лицензии действуют 48 часов и корректно продлеваются.
- Литий, редкоземы, кобальт и галлий образуют свободно торгуемую позднюю ветку.
- Добавлены РЭБ, активная защита, точное наведение и автономные ударные БПЛА;
  улучшения требуют лицензии и редких ресурсов, имеют контрмеры и cap 20%.
- Добавлены USD, EUR, золото и серебро по официальным XML-курсам Банка России:
  неизменяемые snapshots, 72-часовой circuit breaker, серверный spread и
  идемпотентный журнал сделок.
- Государственные облигации получили календарь купонов и погашения, settlement
  ledger без двойных выплат и безопасное ожидание при нехватке денег в казне.
- Вторичный рынок облигаций резервирует бумаги и атомарно переводит Cash между
  игроками, не затрагивая казну.

## Что исправлено

- Авторизация НАТБИРЖИ теперь принимает личность только из криптографически проверенного Telegram Mini App `initData`.
- Удалены fallback-источники личности: `tg_user_id` в URL, `localStorage`, `sessionStorage`, `initDataUnsafe` и автоматическая подстановка admin ID.
- Test auth выключен по умолчанию и, когда явно включён, принимает только HMAC-подписанный test `initData`.
- Creator/State доступ определяется на сервере через роль администратора и `NATBIRZHA_CREATOR_TG_IDS`; frontend только отображает серверный `is_creator`.
- Убраны реальные-looking BOT token и DATABASE_URL из исходного `backend/config.py`; production обязан получать секреты из environment.
- Все player-компании, включая компанию creator/admin, получают одинаковый стартовый cash. Государственная treasury остаётся отдельным балансом.
- Выпуск государственных облигаций больше не создаёт деньги сам по себе: treasury не кредитуется до фактического размещения/покупки.
- Production переведён на строгий цикл `IDLE -> RUNNING -> READY -> COLLECT -> IDLE`.
- Offline/login catch-up и scheduler могут только завершать ранее запущенный цикл и не создают фоновые бесплатные циклы.
- Starter inventory выдаётся только при создании компании и больше не восстанавливается автоматически при нехватке сырья.
- Live-рецепты сведены к 48 canonical recipes (ровно по одному на предприятие); legacy IDs оставлены только как входные aliases.
- Проверяется соответствие recipe одновременно `factory_type` и specialization.
- Workers и Technology получили реальный server-side эффект выпуска; Automation реально сокращает длительность цикла.
- Цены, требования и эффекты upgrades вычисляются только backend; frontend больше не дублирует формулы.
- Добавлены DB row locks для критичных cash/inventory/factory операций и убран опасный merge устаревшего объекта компании.
- Idempotency record и P0 business mutation коммитятся одной транзакцией; гонка одинакового ключа откатывает проигравшую мутацию.
- Старый общий дневной лимит ликвидности NPC удалён: обычные ресурсы можно покупать и сдавать Госрезерву без суточной квоты. Отдельный малый запас сохранён только для premium-сырья.
- Неуспешные покупки редкого premium-сырья не расходуют его отдельный аварийный запас.
- Inventory cap проверяется для production collect, NPC BUY и P2P market settlement.
- P2P market использует блокировки ордеров/компаний/склада; self-trade исключён из matching.
- Каталог получил фильтр недоступных предприятий; state и upgrade status возвращаются сервером.
- Ссылки бота/игрового хаба на НАТБИРЖУ больше не добавляют `tg_user_id`.
- Полный reset одной компании теперь явно очищает нормализованную армию, бои,
  premium ledger, инструменты, облигации и прочие дочерние записи даже в старых
  SQLite dev-базах без включённых foreign-key cascades.

## Проверено локально

Успешно:

- `python -m compileall -q backend tests`
- `node --check` для всех изменённых JS-файлов
- `node tests/test_frontend_modules.js`
- `tests/natbirzha/test_dag_and_specialization.py`
- `tests/natbirzha/test_enterprise_expansion.py` — 31/31
- `tests/natbirzha/test_npc_liquidity_service.py`
- `tests/natbirzha/test_p0_hardening_services.py`
- `tests/natbirzha/test_p0_api_hardening.py` — реальный HTTP-контур FastAPI только с NAT API
- 14 P2 test scripts: schema/migration, combat, PVC, army, PvE, tournament,
  custom creator controls, premium production/upgrades, reference instruments,
  bond lifecycle и HTTP security
- `python tests/test_suite.py` — общий DZ Bot/RPG/NATBIRZHA suite
- `node tests/test_natbirzha_frontend.js`
- `git diff --check`
- scan исходников на удалённые секреты и Natbirzha URL UID fallback

Отдельные `frontend/js/rpg_modules/*` не являются самостоятельными валидными JS-файлами для `node --check` уже в исходном архиве; они собираются/склеиваются RPG build-процессом. Изменённые файлы проходят syntax-check.

## Перед деплоем

Обязательно задать через environment реальные значения `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_ID` и `NATBIRZHA_CREATOR_TG_IDS`. Оставить `NATBIRZHA_ALLOW_TEST_AUTH=false` в production.

В исходной копии были закоммичены реальные-looking Telegram token и PostgreSQL credentials. Их нужно **ротировать у провайдеров**, даже после удаления из исходников. Финальный ZIP намеренно не содержит `.git`, чтобы не распространять старую Git history с этими значениями.
