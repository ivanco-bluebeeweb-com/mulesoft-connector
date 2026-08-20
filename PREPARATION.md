# MuleSoft (Anypoint Platform) Connector — Preparation

**Статус:** Фаза 1 (Discovery + архитектурные решения) завершена. Влад
подтвердил объём релиза 2026-08-20 — «максимум» (Ярус 1+2+3). Готово к
Фазе 2/3 (реализация).
**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-20, v0.1
**Vikunja task:** #2152 (BBW Imperal Apps), [App Development].

**Почему сейчас:** MuleSoft (Anypoint Platform, Salesforce) — классический
enterprise iPaaS-лидер по историческому объёму выручки (~14% оценочной
доли рынка). Даёт Imperal выход на самый консервативный enterprise-сегмент
— компании, уже глубоко завязанные на Salesforce-экосистему. Шестой и
последний коннектор из серии (#2140–#2155), выбранный после Zapier
(заблокирован курицей-и-яйцом), n8n, Make.com, Power Automate.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «MuleSoft»**. Внутренний
app_id/папка: `mulesoft-connector`.

**MuleSoft Connector** — коннектор к Anypoint Platform через CloudHub API
(деплойменты Mule-приложений) и API Manager API (реестр managed API).
BYOK: пользователь подключает свою собственную Anypoint Platform
организацию через собственный Connected App (OAuth2 client credentials).
Imperal ничего не хостит и не проксирует помимо самого запроса.

---

## 2. Ключевые факты об Anypoint Platform API (см. `CONNECTOR_DISCOVERY.md`)

### 2.1 Нет единого API — выбран CloudHub как основной домен

В отличие от Make.com/n8n/Power Automate, у Anypoint Platform нет одного
API — это семейство из ~15+ отдельных REST API. Discovery выделил три
домена как релевантные операционному use-case (список полностью в
`CONNECTOR_DISCOVERY.md` §2):

- **CloudHub API** (`anypoint.mulesoft.com/cloudhub/api/*`) — ВЫБРАН как
  основной. Управление Mule-приложениями: list/get/create/deploy/start/
  stop/restart/delete, metadata (workers, Mule runtime version), logs,
  alerts, schedules. Ближайший аналог "сценариев" из других коннекторов.
- **API Manager API** — реестр managed API (list/get instances, статус
  Active/Inactive/Unregistered). Governance-функции (policies/contracts/
  SLA tiers) сознательно отложены как P2 — требуют глубокого знания
  структуры конкретной policy, риск ошибок выше обычного CRUD.
- **Access Management API** — административный слой организации
  (users/roles/business groups), не про интеграции — не входит в этот
  заход, добавить при явном запросе ("покажи кто в организации").

### 2.2 CloudHub Application entity — реальные поля

Подтверждено против `docs.mulesoft.com/cloudhub/cloudhub-api` (полный
reference) и `apis.io/schemas/mulesoft/mulesoft-applicationcreate/`:

- Endpoint base: `https://anypoint.mulesoft.com/cloudhub/api/applications`
- Ключевые операции: `GET /applications` (list), `POST /applications`
  (create+deploy), `GET /applications/{domain}` (get), `POST
  /applications/{domain}/status` (start/stop/restart через `{"status":
  "START"|"STOP"|"RESTART"}`), `DELETE /applications/{domain}` (delete),
  `PUT /applications/{domain}` (update metadata: workers, muleVersion,
  properties).
- Требуемые заголовки на каждый вызов: `Authorization: Bearer <token>`,
  `X-ANYPNT-ENV-ID`, `X-ANYPNT-ORG-ID`.
- `domain` — уникальный идентификатор приложения (аналог `workflow_id` у
  Power Automate) — lowercase буквы/цифры/дефисы.
- `muleVersion.updateId` vs `latestUpdateId` — поля для определения
  устаревшей Mule runtime (используется в нашем value-add
  `get_stale_applications`).
- Логи: `GET /applications/{domain}/logs` и per-worker вариант.

### 2.3 Auth — Connected Apps (OAuth2 client credentials), без курицы-и-яйца

Anypoint Platform поддерживает Connected Apps с грантами Client
Credentials/Authorization Code/Password/JWT Bearer
(`docs.mulesoft.com/access-management/connected-apps-overview`). Как и
Power Automate — **client credentials flow**, но проще: Connected App
можно создать и получить `client_id`/`client_secret` немедленно в
Anypoint Access Management, никакого внешнего ревью не требуется (в
отличие от Zapier). Токен: `POST
https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token` с
`grant_type=client_credentials`.

Требуемые поля от пользователя:
1. `client_id` — Connected App client ID
2. `client_secret` — Connected App client secret
3. `org_id` — Anypoint organisation ID (нужен на каждый CloudHub-вызов
   как заголовок)
4. `environment_id` — конкретное окружение (Sandbox/Production и т.п.)
5. `label` (опционально) — как у Power Automate, поддержка нескольких
   организаций/окружений в одном секрете (JSON-массив, тот же паттерн,
   что у Power Automate/Slack — `ctx.secrets` не имеет примитива "один
   секрет на id").

### 2.4 API Manager (второстепенный домен, Ярус 2)

`GET /apimanager/api/v1/organizations/{orgId}/environments/{envId}/apis`
— список managed API instances со статусом трекинга
(Active/Inactive/Unregistered). Используется для `list_api_instances` /
`get_api_instance`. Тот же токен/org_id/environment_id, что и CloudHub.

---

## 3. Решённые архитектурные вопросы

| # | Вопрос | Решение | Обоснование |
|---|---|---|---|
| 1 | BYOK или центральный брокер? | **BYOK**, как Make.com/n8n/Power Automate | Пользователь управляет своей Anypoint-организацией; Imperal не хостит и не проксирует организационные Mule-данные. |
| 2 | Какой домен API основной? | **CloudHub** (приложения) + **API Manager** (реестр API) как вторичный | Ближайший аналог "сценариев"/"потоков" из других коннекторов портфеля; governance-домены (Access Management, SLA/policy management) отложены. |
| 3 | Auth механизм? | **Connected App, OAuth2 client credentials** | Официальный рекомендованный Microsoft-аналог для server-to-server; создаётся немедленно, без внешнего ревью (в отличие от Zapier). |
| 4 | Сколько секретов? | **Четыре + label**: `client_id`, `client_secret`, `org_id`, `environment_id` | Все обязательны для аутентификации и адресации конкретной организации/окружения. |
| 5 | Объём релиза? | **«Максимум» = Ярус 1+2+3** | Решение Влада 2026-08-20. |
| 6 | Policies/Contracts/SLA (API Manager governance)? | **Вне охвата P0**, задокументировано как deferred в CONNECTOR_DISCOVERY.md | Каждый тип policy имеет свой JSON-schema — риск ошибок выше обычного CRUD; добавить по явному запросу. |
| 7 | Load Balancers / VPC / VPN / Static IP (CloudHub инфраструктура)? | **Вне охвата**, `not applicable` | Сетевой уровень, требует глубокого VPC-контекста — высокий риск непреднамеренного простоя без явного запроса. |

---

## 4. Функциональный охват («максимум» = Ярус 1+2+3)

### Ярус 1 (P0 — ключевые функции)
- `connect_mulesoft` (client_id, client_secret, org_id, environment_id, label) — проверка + сохранение через `ctx.secrets`
- `disconnect_mulesoft`
- `list_connections`
- `list_cloudhub_applications` (domain, статус, workers, muleVersion)
- `get_cloudhub_application`
- `start_cloudhub_application` / `stop_cloudhub_application` / `restart_cloudhub_application`
- `get_cloudhub_application_logs`
- `list_api_instances` (API Manager)
- `get_api_instance`

### Ярус 2 (полное покрытие CloudHub + API Manager инстансов)
- `update_cloudhub_application` (workers count, env properties, Mule runtime version)
- `delete_cloudhub_application` (деструктивная)
- `list_cloudhub_alerts` / `create_cloudhub_alert` / `delete_cloudhub_alert`
- `list_cloudhub_schedules` / `set_cloudhub_schedule_enabled` / `run_cloudhub_schedule`

### Ярус 3 (наш value-add)
- `bulk_restart_cloudhub_applications` (explicit domain list, 1-100)
- `bulk_stop_cloudhub_applications` / `bulk_start_cloudhub_applications`
- `audit_cloudhub_environment` — агрегирующий отчёт по всем приложениям окружения одним вызовом (статус + workers + Mule version + свежесть деплоя), по аналогии с `run_audit` в других коннекторах
- `get_stale_applications` — приложения на устаревшей Mule runtime (сверка `muleVersion.updateId` vs `latestUpdateId`)

---

## 5. Открытые вопросы для Влада

Нет открытых вопросов — объём релиза подтверждён 2026-08-20 («максимум»).

---

## 6. Журнал проверки дублей

`search_marketplace` по «MuleSoft»/«Anypoint» — дублей не найдено в
существующем портфеле Imperal на момент 2026-08-20.
