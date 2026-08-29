# MuleSoft Connector — что видит и чем управляет пользователь после подключения

## 1. Целевой пользователь
Интеграционный архитектор в enterprise-компании, использующий MuleSoft Anypoint Platform
как основную iPaaS для связывания десятков внутренних и внешних систем (SAP, Salesforce,
базы данных) через API-led connectivity.

## 2. Момент истины после подключения
Сразу после `connect_mulesoft` — сводка по развёрнутым приложениям (applications): сколько
запущено, сколько упало, какая нагрузка на CloudHub worker'ы прямо сейчас.

## 3. Что пользователь видит
- Приложения (Mule applications), развёрнутые на CloudHub/RTF, и их статус — `list_applications`,
  `get_application_status`.
- API, зарегистрированные в API Manager, и политики (rate limiting, security) на них —
  `list_apis`, `list_api_policies`.
- Логи приложения (для диагностики упавшего интеграционного потока) — `get_application_logs`.
- Использование ресурсов (vCores, воркеры) по среде (dev/test/prod) — `get_environment_usage`.
- Экземпляры Exchange-ассетов (переиспользуемые API-спецификации, коннекторы) —
  `list_exchange_assets`.
- Алерты по SLA/производительности API — `list_alerts`.

## 4. Чем пользователь может управлять
- Разворачивать/останавливать/перезапускать приложение на CloudHub — `deploy_application`,
  `stop_application`, `restart_application`.
- Применять/менять политику безопасности или rate-limit на API — `apply_api_policy`.
- Масштабировать приложение (добавить воркеры) — `scale_application`.
- Публиковать новый API-контракт в Exchange для переиспользования командой —
  `publish_exchange_asset`.
- Настраивать алерт по метрике производительности — `create_alert`.

## 5. "Вау"-момент для демо потенциальному клиенту
"Смотри — говорю Webbee: 'какое из моих интеграционных приложений сейчас падает чаще всего
и почему?'. Она находит через `get_application_logs` точную причину — а я прошу
перезапустить и увеличить число воркеров, `restart_application` + `scale_application`
делают это без захода в Anypoint Runtime Manager."

## 6. Что делает это "заточенным под него"
`list_exchange_assets` работает с РЕАЛЬНЫМИ переиспользуемыми API-компонентами, которые
именно эта команда архитекторов уже собрала — специфика её собственной API-экосистемы,
а не общий каталог MuleSoft.
