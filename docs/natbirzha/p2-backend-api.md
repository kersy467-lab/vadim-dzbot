# NATBIRZHA P2 backend contract

Проверенная версия: 2026-09-19. Все mutation-запросы выполняются от компании,
полученной из подписанного Telegram Mini App `initData`. Идентификатор своей
компании клиент не передаёт.

## Общие правила

- Валюта premium-контура называется Pivocoins, код — `PVC`.
- Для покупки лицензии, найма, PvE/PvP-атаки и premium-upgrade требуется
  уникальный `Idempotency-Key`.
- Повтор того же ключа и payload возвращает сохранённый ответ. Тот же ключ с
  другим payload возвращает `409`.
- Время передаётся в ISO 8601. Серверная БД хранит источник истины для таймеров.
- Клиент никогда не присылает силу, потери, победителя, рейтинг или награду.

## Армия

`GET /api/natbirzha/military/status`

Возвращает `infantry`, `border_guards`, `tanks`, `drones`, `aircraft`,
`air_defense`, уровни, готовность, силу по фазам и общую `army_strength`.

`POST /api/natbirzha/military/recruit`

```json
{"unit_type":"aircraft","count":2}
```

Допустимы все шесть типов. Cash и материалы списываются в одной транзакции.

## PvE-корпоративные войны

- `GET /api/natbirzha/military/pve-targets`
- `POST /api/natbirzha/military/pve-targets/{code}/scout`
- `POST /api/natbirzha/military/pve-targets/{code}/attack`
- `GET /api/natbirzha/military/battles`
- `GET /api/natbirzha/military/battles/{battle_id}`

Каталог содержит 12 целей в четырёх тирах. Разведка возвращает диапазон силы;
20 БПЛА открывают точный состав. Победа может выдать землю, Cash, XP и ресурсы
ровно один раз. В журнале хранятся составы, модификаторы, потери и остаток армии.

Стабильные причины отказа: `target_not_found`, `target_inactive`,
`company_level`, `prerequisite`, `already_conquered`,
`insufficient_ground_force`, `invalid_operation_key`, `operation_conflict`.

## Турнир и PvP

- `GET /api/natbirzha/military/tournaments/current`
- `GET /api/natbirzha/military/tournaments/{id}/targets`
- `POST /api/natbirzha/military/tournaments/{id}/targets/{company_id}/attack`
- `GET /api/natbirzha/military/tournaments/{id}/leaderboard`

Автотурнир стартует раз в 72 часа и длится 18 часов. Во время активного окна
атаки не ограничены. После победы только пара «атакующий → побеждённая цель»
блокируется на два часа. PvP не меняет Cash, склад или территорию.

Стабильные причины отказа: `tournament_not_found`, `tournament_not_active`,
`attacker_not_participant`, `target_not_participant`, `self_attack`, `cooldown`,
`empty_army`, `target_empty_army`, `operation_conflict`.

Финальное место определяется только итоговой силой армии. Равная сила получает
одинаковое место. Стандартные призы: `150/100/70 PVC`.

## PVC, лицензии и поздняя военная ветка

- `GET /api/natbirzha/premium/wallet`
- `GET /api/natbirzha/premium/ledger`
- `GET /api/natbirzha/premium/licenses/catalog`
- `GET /api/natbirzha/premium/licenses`
- `POST /api/natbirzha/premium/licenses/{code}/purchase`
- `GET /api/natbirzha/premium/upgrades/catalog`
- `GET /api/natbirzha/premium/upgrades`
- `POST /api/natbirzha/premium/upgrades/{code}/purchase`

`rare_mining` и `advanced_defense` действуют 48 реальных часов. Продление до
истечения добавляет 48 часов к текущему `expires_at`; после истечения отсчёт
начинается заново. Lithium/rare-earth добыча проверяет лицензию при строительстве
и старте цикла, но collect уже начатого цикла не блокируется.

Военные upgrades постоянны, имеют три уровня и требуют активную
`advanced_defense` при исследовании плюс редкие ресурсы. Доступны РЭБ, активная
защита, точное наведение и автономные ударные БПЛА. Суммарный фазовый бонус
ограничен 20%.

## Официальные биржевые инструменты

- `GET /api/natbirzha/instruments`
- `POST /api/natbirzha/instruments/trade`

Доступны `USD`, `EUR`, `GOLD` и `SILVER`. Сервер получает валюты и цены
драгметаллов из XML-интерфейсов Банка России, нормализует валюты до рублей за
единицу и металлы до рублей за грамм. Клиент не передаёт цену. Каждый успешный
курс сохраняется неизменяемым snapshot с URL источника и временем котировки.

Покупка выполняется по reference + 1%, продажа — reference − 1%. Snapshot
допустим не более 72 часов, чтобы пережить выходные и короткий сбой upstream.
После этого новые сделки возвращают `503`, но портфель остаётся читаемым.
Mutation требует `Idempotency-Key`.

## Государственные облигации

- `GET /api/natbirzha/bonds`
- `POST /api/natbirzha/bonds/{bond_id}/buy`
- `POST /api/natbirzha/bonds/listings`
- `POST /api/natbirzha/bonds/listings/{listing_id}/buy`
- `DELETE /api/natbirzha/bonds/listings/{listing_id}`

Выпуск хранит даты следующего купона и погашения. Планировщик каждые пять минут
создаёт settlement-записи с уникальными operation keys. Купон и номинал
списываются только из государственной казны. При нехватке денег запись остаётся
`PENDING` и повторяется без двойного начисления.

Вторичный листинг резервирует облигации продавца. Покупка атомарно переводит Cash
от покупателя продавцу и бумаги покупателю; казна в этой сделке не участвует.
Запрещены перепродажа зарезервированного остатка, self-trade и повторное
исполнение листинга.

## Creator API

`POST /api/natbirzha/creator/tournaments/launch`

```json
{
  "reward_first_pvc": 150,
  "reward_second_pvc": 100,
  "reward_third_pvc": 70
}
```

Каждое значение — целое число от 0 до 10 000. Второй активный турнир запрещён.
Операция доступна только server-side creator/admin и записывается в audit log.

## Миграция и деплой

1. До первого релиза создать проверяемый snapshot/backup PostgreSQL.
2. Задать постоянный PostgreSQL `DATABASE_URL`; production SQLite запрещён.
3. Запустить приложение один раз. `Base.metadata.create_all` создаёт только новые
   таблицы, затем versioned runner применяет `natbirzha_p2_001` и
   `natbirzha_p2_002` и `natbirzha_p2_003_financial_markets`.
4. Проверить `nat_schema_versions`, число компаний, заводов, складских строк и
   армий до/после запуска.
5. Повторить restart и убедиться, что версии и normalized army rows не
   дублируются.

Rollback приложения может временно игнорировать новые таблицы. Rollback БД не
должен удалять P2-таблицы или откатывать PVC/армии: это потеря пользовательских
данных. Обратное преобразование выполняется только отдельной проверенной
миграцией после backup.

Обязательные environment values: `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_ID`,
`NATBIRZHA_CREATOR_TG_IDS`, `BASE_URL`, `WEBAPP_URL`.
`NATBIRZHA_ALLOW_TEST_AUTH` в production должен оставаться `false`.
