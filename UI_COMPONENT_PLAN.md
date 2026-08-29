# MuleSoft Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на `POST_CONNECT_EXPERIENCE.md` этого приложения.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(business group/org) + `ui.Divider` + navigation `ui.ListItem`(Applications/APIs/Exchange) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Application List (CloudHub, center, `center_overlay=True`) | `ui.Stats`(Running/Stopped/Failed) + `ui.DataTable`(name, environment, status Toggle-колонка editable started/stopped, workers; sortable) | Запуск/остановка Mule-приложения прямо из таблицы через editable toggle-колонку. |
| Application Detail | Back-button + `ui.KeyValue`(runtime version/workers/region) + `ui.Chart`(type="line" — CPU/memory usage over time) + `ui.Code`(language="text", app logs tail, readonly) | `Chart` для метрик воркеров, `Code` для лога приложения. |
| API Manager List | `ui.DataTable`(api name, version, status Badge active/deprecated, policies count; sortable) | Табличный обзор управляемых API в API Manager. |
| API Policy List (api detail) | Back-button + `ui.List`(applied policies: name, order) + `ui.Button`("Add Policy") | Простой список применённых policy (rate limiting, OAuth, etc). |
| API Analytics | `ui.Stats`(Requests today/Avg latency/Error rate) + `ui.Chart`(type="line" — requests over time) + `ui.DataTable`(top consumers: client app, requests count; sortable) | Стандартная связка Stats+Chart+DataTable для API traffic analytics. |
| Exchange Asset Browser | `ui.DataTable`(asset name, type Badge connector/template/API spec, version; sortable) | Табличный каталог переиспользуемых ассетов Anypoint Exchange. |
| Deploy Dialog | `ui.Dialog`(title="Задеплоить приложение?", content=`ui.Select`(target environment), confirm_label="Задеплоить") | Деплой в environment (особенно production) — значимое действие с явным подтверждением. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Business Group/Environment Select]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__mulesoft_sidebar` рендерит business group + разделы,
   `auto_action` открывает Application List для текущего environment.
2. Application List: editable toggle "started" → `on_cell_edit` вызывает
   `start_application`/`stop_application` напрямую (обратимо) → `refresh_panels`.
3. Клик на строку приложения → Application Detail — `Chart` метрик, `Code` логов.
4. API Manager доступен отдельным пунктом сайдбара → API List → клик на API →
   API Policy List + API Analytics (через Tabs или отдельные экраны).
5. Exchange Asset Browser — read-only каталог, доступен из сайдбара.
6. "Задеплоить" (продвинутый сценарий) → `ui.Dialog` подтверждение выбора
   environment → `ui.Call("deploy_application")` → `refresh_panels`.
7. App Settings — только через кнопку в сайдбаре, единственное место с disconnect.

## 3. Экраны/карточки (артефакты для реализации)

- `panels.py`: `__panel__mulesoft_sidebar` (left).
- `panels_applications.py`: `__panel__application_list` (center, `center_overlay=True`,
  editable toggle), `__panel__application_detail` (center, параметризован `app_id`).
- `panels_api_manager.py`: `__panel__api_list` (center), `__panel__api_detail`
  (center, параметризован `api_id`, policies+analytics).
- `panels_exchange.py`: `__panel__asset_browser` (center).
- `panels_settings.py`: `__panel__app_settings` (center overlay, Accordion,
  единственное место с disconnect).
