"""Human-facing industry metadata and target population shares."""

INDUSTRIES = {
    "miner": {"name": "Горнодобывающая промышленность", "icon": "⛏️", "target_share": 0.15, "difficulty": 3, "summary": "Сырьё для металлургии, энергетики и высоких технологий."},
    "agrarian": {"name": "Аграрная промышленность", "icon": "🌾", "target_share": 0.12, "difficulty": 2, "summary": "Продовольствие и сельхозсырьё для работников и армии."},
    "power_engineer": {"name": "Энергетика", "icon": "⚡", "target_share": 0.12, "difficulty": 3, "summary": "Электроэнергия для практически всей экономики."},
    "water": {"name": "Водоснабжение", "icon": "💧", "target_share": 0.08, "difficulty": 2, "summary": "Техническая, очищенная и сверхчистая вода."},
    "oilman": {"name": "Нефтегазовая промышленность", "icon": "🛢️", "target_share": 0.10, "difficulty": 3, "summary": "Нефть, газ и топливо для транспорта, промышленности и армии."},
    "metallurgist": {"name": "Металлургия", "icon": "🔩", "target_share": 0.10, "difficulty": 4, "summary": "Переработка руды в металлы, прокат и специальные сплавы."},
    "chemist": {"name": "Химическая промышленность", "icon": "🧪", "target_share": 0.08, "difficulty": 4, "summary": "Удобрения, реагенты, полимеры и технологическая химия."},
    "construction": {"name": "Строительство", "icon": "🏗️", "target_share": 0.04, "difficulty": 3, "summary": "Стройматериалы и мощность для корпоративных проектов."},
    "forester": {"name": "ИИ и дата-центры", "icon": "🧠", "target_share": 0.06, "difficulty": 3, "summary": "Машинное обучение и вычислительная мощность: стартовый спрос от отраслей, кратный рост при автоматизации."},
    "technoprom": {"name": "Технологическая промышленность", "icon": "💻", "target_share": 0.10, "difficulty": 4, "summary": "Электроника, автоматика, роботы и микроэлектроника."},
    "logistics": {"name": "Логистика", "icon": "🚚", "target_share": 0.05, "difficulty": 3, "summary": "Перевозки, терминалы, склады и транспортная мощность."},
    "brewery": {"name": "Пивоварение", "icon": "🍺", "target_share": 0.03, "difficulty": 3, "summary": "Пиво, вино и выдержанные напитки из сельскохозяйственного сырья."},
}

__all__ = ["INDUSTRIES"]
