# MuleSoft Connector — идеальный первый запуск

Источник: `ONBOARDING_FIRST_LAUNCH_STANDARD.md`. Целевой пользователь: интеграционный
архитектор enterprise-компании на Anypoint Platform.

## 1. Credential type
OAuth client-credentials (Connected App: Client ID + Client Secret).

## 2. Идеальный флоу
1. **Первое открытие** — `Empty` со ссылкой на Anypoint Access Management > Connected
   Apps + список нужных scopes (Runtime Manager, CloudHub) сгруппированных по тому,
   что реально нужно делать (мониторинг деплоев vs полное управление).
2. **Форма** — Client ID + Client Secret с лейблами, контекстный placeholder.
3. **Business Group/Environment selector** — идеально: у Anypoint часто несколько
   Business Groups и Environments (Sandbox/Production) под одной организацией —
   явный двухуровневый выбор СРАЗУ после успешной аутентификации, до показа
   какого-либо приложения/деплоя, иначе пользователь увидит "пусто", думая что
   подключение не сработало, хотя на самом деле активен не тот Environment.
4. **После успеха** — сводка по развёрнутым приложениям (running/failed) + текущая
   нагрузка CloudHub worker'ов сразу, без доп. клика.
5. **Ошибка "insufficient business group permissions"** — конкретное сообщение с
   именем Business Group, к которому не хватает доступа, не общая 403.
6. **CloudHub worker down** — не ошибка ПОДКЛЮЧЕНИЯ, а статус мониторинга — не должно
   маскироваться под "не удалось подключиться", а как отдельный `Alert(warn)` внутри
   уже подключённого состояния.

## 3. Разница с реализацией сейчас
См. `UI_COMPONENT_PLAN.md` §0.
