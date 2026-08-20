# Pricing History — MuleSoft Connector

Обязательный журнал: каждое выставление или изменение цен на функции этого
приложения фиксируется здесь — что изменилось, почему, и на основании
чего. Не переписывать прошлые записи — только дописывать новые сверху.

---

## 2026-08-20 — процесс-инцидент: приложение отправлено на ревью ДО прайсинга

**Что произошло:** `submit_for_review` для `mulesoft-connector` был вызван
сразу после успешного `deploy_app`, БЕЗ предварительного выставления цены
через `developer.update_pricing`. Это прямое нарушение канонического
`PRICING_POLICY.md` (который уже требовал прайсинг "перед публикацией",
но был явно переформулирован именно из-за этого случая — см. §1 там,
редакция 2026-08-20). Влад указал на ошибку напрямую: "ты прайсинг должен
выставлять до того как подашь на ревью! это и в таск запиши и в
документ!".

**Исправление, выполненное тем же ходом:**
1. `PRICING_POLICY.md` §1 переформулирован — правило теперь явно называет
   `submit_for_review` как границу, а не расплывчато "публикацию".
2. Прайсинг выставлен задним числом через `developer.update_pricing` (см.
   ниже) — приложение уже было в `pending_review`, но платформа позволяет
   менять цену независимо от статуса ревью.
3. Этот файл создан, чтобы правило "прайсинг → потом ревью" было
   зафиксировано и для этого коннектора лично, не только в общем
   документе.

**Метод применения — `developer.update_pricing` (подтверждённо рабочий
метод, см. канонический `PRICING_POLICY.md` §3, прецедент n8n Connector
2026-08-19). `save_pricing` НЕ использовался.**

Первая попытка вызова `update_pricing` ловила ошибку валидации Pydantic
(`pricing_config` как строка, а не объект) — исправлено передачей
`pricing_config` как настоящего JSON-объекта, не экранированной строки.
`revenue_split_dev=95` передан явным параметром (partner-тир этого
разработчика), не только внутри `pricing_config` — по тому же правилу,
что и n8n Connector.

**Цены — фиксированная платформенная шкала {0, 8, 16, 20, 40, 60}, без
исключений и без x1.8-маркапа (MuleSoft не Google-backed API):**

| Цена | Функции |
|---|---|
| 0 | `connect_mulesoft`, `disconnect_mulesoft`, `list_connections` (настройка доступа, не операция с Anypoint API) |
| 8 | `list_cloudhub_applications`, `get_cloudhub_application`, `get_cloudhub_application_logs`, `list_cloudhub_alerts`, `list_cloudhub_schedules`, `list_api_instances`, `get_api_instance` (простое чтение состояния) |
| 16 | `start_cloudhub_application`, `stop_cloudhub_application`, `restart_cloudhub_application`, `update_cloudhub_application`, `delete_cloudhub_application`, `create_cloudhub_alert`, `delete_cloudhub_alert`, `set_cloudhub_schedule_enabled` (стандартное одиночное write/destructive-действие) |
| 20 | `run_cloudhub_schedule` (действие, реально запускающее работу в проде пользователя) |
| 40 | `audit_cloudhub_environment`, `get_stale_applications` (агрегированные value-add отчёты по всему окружению) |
| 60 | `bulk_start_cloudhub_applications`, `bulk_stop_cloudhub_applications`, `bulk_restart_cloudhub_applications`, `bulk_delete_cloudhub_applications` (bulk-операции сразу по многим приложениям) |

`pricing_model = "per_action"`, `monthly_price = 0`, `revenue_split_dev = 95`
(partner-тир).

**Источник истины продублирован в `imperal.json["pricing"]`** этого
приложения (не только в runtime-вызове) — так цена видна прямо в
манифесте независимо от состояния платформенного API, по тому же
правилу, что и у Make.com/n8n Connector.
