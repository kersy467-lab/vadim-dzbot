# Instructions for AI Assistant (Code Quality & Architecture Guidelines)

## 1. Строгий лимит на размер файлов (File Size & Clean Architecture)
- **Лимит строк**: Ни один файл с исходным кодом (Python, JavaScript, HTML, CSS) не должен превышать **350–400 строк**. Оптимальный целевой размер — **150–300 строк**.
- **Запрет на разрастание**: Категорически запрещено создавать новые файлы-монолиты или бездумно дописывать новые функции в уже крупные файлы.
- **Принцип единственной ответственности (SRP)**: Каждый файл должен решать строго одну задачу (например, добавление сущности, валидация, логика БД или визуальное отображение).

## 2. Стандарт декомпозиции (Модульный подход)
Если файл приближается к 350 строкам или начинает решать смежные задачи:
1. **Преобразование в пакет**:
   - Файл `module.py` заменяется папкой `module/` с обязательным `__init__.py`.
2. **100% обратная совместимость (Zero Breaking Changes)**:
   - В `__init__.py` обязательно импортируются и реэкспортируются все публичные классы, функции, роутеры и переменные, чтобы ни один существующий импорт в проекте не сломался.
3. **Логическое разделение**:
   - **Хэндлеры Aiogram**: разделять по действиям (`add.py`, `edit.py`, `list.py`, `actions.py`, `helpers.py`).
   - **CRUD SQLAlchemy**: разделять по доменным сущностям (`users.py`, `schedule.py`, `homework.py`, `bells.py` и т.д.).
   - **API Роутеры FastAPI**: выносить в `backend/api/routers/<domain>.py`.
   - **Frontend JS**: модули регистрировать в объектах пространства `window` (например, `window.AppLightbox`, `window.EGE.*`), выносить крупные подсистемы в отдельные файлы.

## 3. Обязательный протокол верификации
После любого добавления функционала, рефакторинга или декомпозиции:
1. Запустить проверку синтаксиса: `python -m py_compile ...` (для Python) или `node -c ...` (для JS).
2. Запустить полный набор тестов проекта: `python tests/test_suite.py`.
3. Убедиться, что нет циклических импортов (`Circular Import`) и все тесты проходят со статусом `=== ALL TESTS PASSED SUCCESSFULLY! ZERO ERRORS! ===`.

## 4. Git и деплой — обязательные правила пользователя
- Всегда выполнять команды из `C:\Users\User\Documents\antigravity\mysterious-darwin\dzbot`.
- Для каждой команды Git указывать `-c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot`.
- В PowerShell перед Git-командами, которым может понадобиться сеть, задавать `$env:GIT_TERMINAL_PROMPT=0`.
- Стандартный коммит: добавить все файлы, относящиеся к завершённой задаче, и создать коммит с понятным сообщением.
- Полный деплой всегда отправляет один и тот же коммит в обе ветки (`main` и `dev`) каждого из трёх remote (`origin`, `vadim`, `mybot`):
  1. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push origin main`
  2. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push origin dev`
  3. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push vadim main`
  4. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push vadim dev`
  5. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push mybot main`
  6. `git -c safe.directory=C:/Users/User/Documents/antigravity/mysterious-darwin/dzbot push mybot dev`
- До отправки синхронизировать локальные `main` и `dev` на коммите деплоя; после отправки проверить, что все шесть remote-веток указывают на него.
