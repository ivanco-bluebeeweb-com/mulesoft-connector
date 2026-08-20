# MuleSoft (Anypoint Platform) Connector — Connector Discovery

**Дата discovery:** 2026-08-20
**Статус:** Ярусы 1-3 пройдены (свежее чтение официальной документации dev-portal.mulesoft.com / docs.mulesoft.com / help.mulesoft.com, 2026-08-20). §6 (решение по объёму) ТРЕБУЕТ явного выбора Влада — в задаче #2152 не было заранее заявлено "делаем максимум", поэтому исключение Шага 5 не применяется.

---

## 1. Целевой сервис и источники

MuleSoft Anypoint Platform (Salesforce) — enterprise iPaaS / API management платформа. В отличие от Make.com/n8n/Power Automate, у неё **нет единого API** — это семейство из ~15+ отдельных REST API под разные компоненты платформы (подтверждено `dev-portal.mulesoft.com` — official "Anypoint Platform APIs" hub, 77 задокументированных операций только в перечисленных ниже доменах).

Источники (прочитаны 2026-08-20):
- `dev-portal.mulesoft.com/` — общий каталог всех Anypoint Platform API
- `dev-portal.mulesoft.com/apis/access-management.html`, `api-manager.html`, `api-platform.html`, `cloudhub.html`, `exchange-experience.html`
- `docs.mulesoft.com/access-management/` (Overview, Users, Roles, Connected Apps Overview, Creating Connected Apps)
- `docs.mulesoft.com/cloudhub/cloudhub-api` (CloudHub API — полный reference)
- `docs.mulesoft.com/api-manager/latest/` (Overview, Client Applications/Contracts, Policies, SLA Tiers)
- `help.mulesoft.com` — Connected App bearer token, start/stop/restart CloudHub apps, fetch logs

## 2. Карта возможностей (направление на каждую)

| Домен API | Возможность | Ingress/Egress/Both | Комментарий |
|---|---|---|---|
| **Access Management** | List/invite/manage users, roles, permissions, business groups | Both | Административный слой — не про интеграции, а про сам Anypoint-аккаунт |
| **Access Management** | Connected Apps (OAuth2/OIDC client credentials, JWT Bearer) | — (auth infra) | Механизм аутентификации для остальных API — не бизнес-функция сама по себе |
| **Access Management** | Audit logs (кто что сделал в организации) | Ingress | Полезно как read-функция для аудита действий в самом Anypoint |
| **CloudHub** | List/get/create/deploy/start/stop/restart/delete приложений (Mule apps на CloudHub workers) | Both | Ближайший аналог "сценариев" из Make/n8n — это и есть основная боль пользователя MuleSoft |
| **CloudHub** | Update app metadata (workers count, Mule runtime version, env vars/properties) | Egress | Конфигурация деплоя |
| **CloudHub** | Logs (получить/скачать лог-файл приложения или воркера) | Ingress | Диагностика — важная функция для operations-персонала |
| **CloudHub** | Alerts (create/update/delete alert, получить историю алертов) | Both | Мониторинг состояния приложений |
| **CloudHub** | Notifications (создать/прочитать/отметить) | Both | Внутренние уведомления CloudHub |
| **CloudHub** | Schedules (enable/disable/run schedule приложения) | Egress | Управление cron-задачами внутри Mule-приложения |
| **CloudHub** | Load balancers (create/update/delete/list, test rules) | Both | Инфраструктурный уровень — далеко от "интеграций", ближе к сетевому админству |
| **CloudHub** | VPC/VPN/Transit Gateway management | Both | Глубокая сетевая инфраструктура — вне типичного сценария для чат-агента |
| **CloudHub** | Static IP management | Egress | Инфраструктурная деталь конкретного приложения |
| **CloudHub** | Persistent queues stats/clear | Both | Специфичная internals-функция очередей Mule runtime |
| **API Manager** | List/get API instances (managed APIs), их статус (Active/Inactive/Unregistered) | Ingress | Реестр всех API, зарегистрированных в организации |
| **API Manager** | Manage policies (apply/remove gateway policy на API instance: rate-limit, auth, etc.) | Egress | Governance-слой — включение/выключение политик на прокси |
| **API Manager** | Client Applications, Contracts (list/create/revoke contract между client app и API) | Both | Управление доступом сторонних клиентских приложений к API |
| **API Manager** | SLA Tiers (create/edit/delete tier, approve/reject/revoke заявку на tier) | Both | Управление уровнями доступа/лимитами по API |
| **API Platform** | Organizations (get/update/delete), org permissions, org alerts | Both | В основном совпадает по сути с Access Management на уровне организации |
| **Exchange** | List/search assets (API specs, connectors, templates), publish asset | Both | Каталог переиспользуемых активов внутри организации |
| **Design Center** | Create/manage API spec projects, branches, publish to Exchange | Egress | Про проектирование самого API-контракта — далеко от operations-задач |

## 3. Классификация по типу функционала (Шаг 1 стандарта)

- **Ingress (сильный)**: список приложений CloudHub и их статус, логи, список API instances, список Connected/Client Apps, audit logs — это то, что коннектор в первую очередь должен уметь *показывать*.
- **Egress (сильный)**: start/stop/restart/deploy/delete CloudHub-приложения, apply/remove policy на API instance, управление SLA tier approvals, управление schedules — это реальные операционные действия с последствиями.
- **Both**: контракты между client apps и API (create = запись, list = чтение), alerts.

## 4. Ярус 1 — Ключевые функции (P0-кандидаты)

Ближайший аналог "списка сценариев + запустить/остановить/посмотреть лог", по образцу существующих коннекторов:

1. `connect_mulesoft` / `disconnect_mulesoft` — OAuth2 Connected App (client_id + client_secret + org_id, опционально environment_id)
2. `list_cloudhub_applications` — список Mule-приложений в окружении, со статусом (STARTED/UNDEPLOYED/etc.)
3. `get_cloudhub_application` — детали одного приложения (workers, Mule version, domain, статус)
4. `start_cloudhub_application` / `stop_cloudhub_application` / `restart_cloudhub_application`
5. `get_cloudhub_application_logs` — получение логов приложения/воркера
6. `list_api_instances` (API Manager) — реестр managed API организации со статусом активности
7. `get_api_instance` — детали конкретного API instance (policies, contracts)

## 5. Ярус 2 — Полное покрытие

| Возможность | Статус | Причина/триггер |
|---|---|---|
| List/start/stop/restart/deploy/delete CloudHub app | included | Ярус 1 |
| Get CloudHub app logs | included | Ярус 1 |
| List/get API Manager instances | included | Ярус 1 |
| Manage CloudHub alerts (create/update/delete/history) | included | Естественное расширение мониторинга — небольшая добавка поверх уже нужного HTTP-клиента |
| Manage CloudHub schedules (enable/disable/run) | included | Частый operational use-case ("включи/выключи джобу") |
| Manage CloudHub app metadata (workers count, env properties) | included | Прямое продолжение "управления приложением" |
| API Manager: apply/remove policy на instance | deferred | Требует глубокого знания структуры конкретной policy (JSON schema отличается по типу policy) — риск ошибок выше обычного CRUD; вернуться после того как Ярус 1 стабилен и есть реальный запрос |
| API Manager: Client Apps / Contracts (list/create/revoke) | deferred | Нужен для управления доступом сторонних потребителей API — не операционная боль, а governance-задача; отложить до явного запроса |
| API Manager: SLA Tiers (create/edit/delete, approve/reject) | deferred | Governance-уровень, реже нужен в разговорном сценарии |
| Access Management: list users/roles/business groups | deferred | Административная функция уровня организации, не про интеграции — добавить если появится явный кейс "покажи кто в организации" |
| Access Management: audit logs | deferred | Полезно, но не входит в основную боль P0; добавить вместе с Access Management users |
| CloudHub: Load Balancers management | not applicable | Сетевая инфраструктура, требует глубокого контекста VPC — не подходит для разговорного use-case без явного запроса; слишком высокий риск непреднамеренного простоя |
| CloudHub: VPC/VPN/Transit Gateway | not applicable | То же — сетевой уровень, не операционные интеграции |
| CloudHub: static IP management | not applicable | Узкая инфраструктурная деталь, низкая ценность вне сетевого администрирования |
| CloudHub: persistent queues stats/clear | deferred | Диагностическая функция, полезна, но нишевая; добавить при явном запросе |
| Exchange: list/search/publish assets | deferred | Каталог активов — отдельный use-case ("что у нас есть переиспользуемого"), не входит в операционное P0 |
| Design Center: API spec projects | not applicable | Это дизайн-инструмент для написания самого API-контракта (аналог IDE) — не подходит под модель "агент управляет уже задеплоенным" |
| CloudHub notifications (mark read/unread) | not applicable | Внутренний UI-механизм CloudHub, низкая автономная ценность вне их родного интерфейса |

## 6. Ярус 3 — Функции на нашей стороне (value-add)

- **`bulk_restart_cloudhub_applications`** — рестарт нескольких приложений одним вызовом (CloudHub API отдаёт только по одному приложению за раз)
- **`audit_cloudhub_environment`** — агрегирующий отчёт по всему окружению: список приложений + их статус + workers count + Mule version + свежесть последнего деплоя одним вызовом, вместо ручного обхода каждого приложения по отдельности (похоже на уже существующий паттерн `run_audit` в других коннекторах Imperal)
- **`get_stale_applications`** — находит приложения на устаревшей Mule runtime версии (сверка `muleVersion.updateId` vs `latestUpdateId` из ответа API) — сервис отдаёт эти два поля, но не даёт готового "who is outdated" отчёта
- **preview-стиль подтверждение перед `stop`/`delete` приложения** — у CloudHub нет собственного dry-run для деструктивных операций

## 7. Решение по объёму этого захода — ТРЕБУЕТ выбора Влада

Явного "делаем максимум сразу" в задаче #2152 не было — оно содержало только предупреждение о риске узкого скоупа из-за фрагментированности API. Поэтому вопрос обязателен:

**Какую форму берём в этот заход?**
1. **Только Ярус 1** (7 функций: connect/disconnect, list/get/start/stop/restart CloudHub app, логи, список API instances) — минимальный операционный P0.
2. **Ярус 1 + Ярус 2** (добавляет: alerts, schedules, app metadata — итого ~13-14 функций) — полное покрытие CloudHub-домена, но без API Manager governance (policies/contracts/SLA) и без Access Management.
3. **Ярус 1 + Ярус 2 + Ярус 3** («максимум») — то же плюс bulk-обёртки и агрегирующие отчёты (audit/stale-apps) поверх.

Замечание: в отличие от Zapier, здесь **нет курицы-и-яйца** — Connected App можно создать сразу, без внешнего ревью, поэтому релиз в любом из трёх объёмов возможен немедленно после кода. Разница только в широте покрытия, не в доступности API.
