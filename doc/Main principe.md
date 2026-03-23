# Isomorph

## Идея

**Isomorph** — это единое ядро реактивного исполнения workflow-графов с DSL, control-операторами, action-реестром, event bus и runtime-политиками.

Цель проекта:

* не продолжать параллельно `Monocle` и `zesty_edge`;
* не склеивать их целиком;
* а собрать **новое чистое execution kernel**, в который переносится только полезное и уже доказавшее ценность.

Рабочее определение:

> **Isomorph = DSL-driven reactive workflow kernel**

То есть:

* workflow описывается декларативно;
* компилируется в execution plan;
* исполняется строгим runtime;
* действия изолированы как actions;
* управление исполнением реализуется отдельными control nodes/operators;
* runtime и domain events разделены.

---

## Главные принципы

1. **Definition != Runtime**
   DSL и execution state не смешиваются.

2. **Control nodes != Actions**
   `foreach`, `join`, `branch`, `wait_for_event` — это операторы исполнения, а не обычные actions.

3. **Single Action Contract**
   Во всей системе один контракт вызова action.

4. **Compile before execute**
   DSL не исполняется напрямую; сначала валидация и компиляция.

5. **Runtime owns execution semantics**
   Retry, timeout, join, cancellation, fan-in/out — ответственность ядра.

6. **Separate Runtime Bus and Domain Bus**
   События движка и предметные события разделены.

7. **Products are adapters around the same kernel**
   Minibar, CV, hardware orchestration и т.д. — это не отдельные framework’и, а наборы actions/adapters поверх общего ядра.

---

## Что переносим из старых проектов

## Из Monocle

### Оставить

* идею разделения на contracts / runtime / nodes / policies;
* typed contracts (`image`, `text`, `error`, base content idea);
* registry-ориентированный подход;
* policy-компилятор и отдельный слой политик как концепт;
* event builder / runtime event naming как основу telemetry;
* vision / io stubs как примеры actions;
* plugin/runtime bootstrap как источник идей, но не как готовую реализацию.

### Не переносить как есть

* текущий `GraphPipeline` и его семантику исполнения;
* текущий `GraphPipelineAsync`;
* размазанную систему runtime-context сущностей;
* дублирующуюся type compatibility logic;
* прямую связку графа и узлов без промежуточного execution plan.

### Переносить после упрощения

* contracts;
* registry;
* policies DSL;
* runtime event taxonomy;
* некоторые io/vision nodes как actions examples.

---

## Из zesty_edge

### Оставить

* общий вектор на event-driven runtime;
* DSL/IR-мышление (`dsl_models`, parser, runtime separation);
* FSM / context / dispatcher как идеи прикладного уровня;
* hardware layer (`hw`) как product adapters;
* PDCA / metrics registry как базу observability-плагинов;
* action registry и entry-point подход как основу plugin ecosystem.

### Не переносить как есть

* текущий action contract;
* текущую реализацию `foreach`;
* dispatcher/runtime с разными сигнатурами action;
* flow execution builder в текущем виде;
* прикладные сущности, если они смешаны с kernel-семантикой.

### Переносить после упрощения

* parser / DSL model ideas;
* registry mechanics;
* metrics and plugin ideas;
* hw/actions как product packs.

---

## Что выкинуть полностью

* Любой код, где action сам решает маршрутизацию исполнения.
* Любой код, где control-operator притворяется обычным action.
* Любой код, где event bus фактически управляет графом скрыто.
* Любой код, где sync/async — две почти независимые модели исполнения.
* Любой код, где runtime context раздроблен на много пересекающихся фасадов без одного центра.

---

## Целевая архитектура Isomorph

## 1. Слои

### A. Definition Layer

Чистая декларативная модель workflow.

Содержит:

* `WorkflowDefinition`
* `NodeDefinition`
* `EdgeDefinition`
* `PortDefinition`
* `PolicyDefinition`

Задача:

* хранить пользовательский DSL;
* не содержать логики исполнения.

### B. Compiler Layer

Преобразует definition в execution plan.

Содержит:

* validator;
* graph normalization;
* port resolution;
* policy compilation;
* control-node lowering;
* condition compilation.

Результат:

* `ExecutionPlan`
* `ExecutionNode`
* `CompiledPolicySet`

### C. Runtime Layer

Ядро исполнения.

Содержит:

* scheduler;
* dispatcher;
* token engine;
* node input buffers;
* retry/timeout/cancel policies;
* state transitions;
* checkpoint hooks;
* runtime events.

### D. Operators Layer

Специальные управляющие узлы.

Минимум:

* `ActionOperator`
* `BranchOperator`
* `ForeachOperator`
* `JoinOperator`
* `WaitForEventOperator`

### E. Action Layer

Предметные действия.

Примеры:

* `capture_image`
* `detect_objects`
* `crop_region`
* `classify_crop`
* `mqtt_publish`
* `read_sensor`
* `hardware_command`

### F. Infra Layer

Внешняя инфраструктура.

Содержит:

* runtime bus;
* domain bus;
* persistence;
* telemetry;
* plugin loading;
* CLI;
* API;
* MQTT/HTTP/DB adapters;
* hardware adapters.

---

## 2. Канонический Action Contract

```python
class ActionContext(Protocol):
    execution_id: str
    node_id: str
    cancellation_requested: bool
    services: Any

class ActionResult(BaseModel):
    status: Literal["success", "error", "skipped"]
    outputs: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    metrics: dict[str, float] = {}
    error: str | None = None

class Action(Protocol):
    async def run(
        self,
        inputs: dict[str, Any],
        ctx: ActionContext,
        config: dict[str, Any],
    ) -> ActionResult:
        ...
```

Правила:

* action получает только входы, контекст и конфиг;
* action не знает о графе целиком;
* action не запускает другие узлы;
* action не управляет маршрутизацией;
* action может эмитить domain events через `ActionResult.events` или сервис из контекста.

---

## 3. Типы узлов

## Task Nodes

Обычные work units.

* action
* transform
* validate

## Control Nodes

Операторы исполнения.

* branch
* foreach
* join
* wait_for_event
* merge

## Policy/Timing Nodes

* delay
* retry wrapper
* timeout wrapper
* debounce
* throttle

Принцип:

* В DSL это могут быть узлы.
* В runtime это должны быть **разные executor/operator types**.

---

## 4. Модель исполнения

## ExecutionPlan

Нормализованное описание исполнения.

Содержит:

* список execution nodes;
* входные/выходные порты;
* зависимости;
* operator kinds;
* compiled policies;
* start nodes.

## ExecutionToken

Единица прохождения по графу.

Содержит:

* `token_id`
* `execution_id`
* `current_node_id`
* `payload`
* `correlation_id`
* `parent_token_id`

## ExecutionState

Содержит:

* статус workflow instance;
* статусы узлов;
* input buffers;
* pending joins;
* retry counters;
* checkpoints;
* cancellation flags.

---

## 5. Семантика исполнения

## Fan-out

По умолчанию payload копируется в исходящие рёбра, если явно не указано иное.

## Fan-in / Join

Join управляется runtime.

Поддерживаемые режимы:

* `all`
* `any`
* `quorum(n)`
* `collect`

Узел не стартует, пока не выполнено правило join.

## Foreach

`foreach`:

* читает список items из входа;
* создаёт дочерние tokens;
* запускает child subtree для каждого item;
* собирает результаты через `collect`/`join`.

`foreach` **не** вызывает child action вручную.

## Branch

Выбирает исходящие ветки по условию.

## Retry

Retry — это runtime policy.

## Timeout / Cancel

Timeout и отмена принадлежат runtime и policy layer, а не actions.

---

## 6. Event Model

## Runtime Bus

События ядра:

* `workflow_started`
* `workflow_completed`
* `node_started`
* `node_completed`
* `node_failed`
* `token_spawned`
* `retry_scheduled`
* `workflow_cancelled`

Назначение:

* observability;
* tracing;
* UI;
* debugging;
* replay.

## Domain Bus

Предметные события:

* `image_captured`
* `door_opened`
* `sku_detected`
* `temperature_alert`

Назначение:

* реактивная логика;
* интеграции;
* внешние подписчики.

Правило:

* runtime bus не должен скрыто определять маршрутизацию графа.

---

## 7. Политики

Политики должны компилироваться отдельно и применяться в runtime.

Минимальный набор:

* retry;
* timeout;
* overflow/backpressure;
* concurrency limit;
* fallback;
* sync barrier;
* circuit breaker.

Решение:

* перенести идею policy layer из Monocle;
* переписать её под `ExecutionPlan` и operator semantics.

---

## 8. Plugin System

Нужен единый plugin API.

Типы плагинов:

* action packs;
* adapters;
* metrics providers;
* serializers / codecs;
* domain packs.

Интерфейсы:

* `ActionRegistry`
* `OperatorRegistry`
* `MetricsRegistry`
* `CodecRegistry`

---

## 9. Структура репозитория

```text
src/
  isomorph/
    definitions/
      workflow.py
      node.py
      edge.py
      ports.py
      policies.py

    compiler/
      validator.py
      planner.py
      normalize.py
      ports.py
      conditions.py
      policies.py

    runtime/
      engine.py
      dispatcher.py
      scheduler.py
      state.py
      token.py
      node_state.py
      checkpoints.py
      cancellation.py

    operators/
      base.py
      action.py
      branch.py
      foreach.py
      join.py
      wait_for_event.py

    actions/
      contracts.py
      registry.py
      result.py
      context.py

    events/
      runtime_bus.py
      domain_bus.py
      events.py

    policies/
      retry.py
      timeout.py
      concurrency.py
      overflow.py
      fallback.py

    plugins/
      loader.py
      entrypoints.py
      manifests.py

    telemetry/
      metrics.py
      tracing.py
      logging.py

    persistence/
      interfaces.py
      memory.py
      sqlite.py

    codecs/
      base.py
      json.py
      yaml.py

    cli/
      main.py

    api/
      app.py

  isomorph_packs/
    cv/
      actions/
      contracts/
    edge/
      actions/
      adapters/
    minibar/
      actions/
      domain/
```

---

## 10. Migration Matrix

## Перенос из Monocle в Isomorph

### Переименовать / адаптировать

* `contracts/*` → `isomorph_packs.cv.contracts` или `isomorph.contracts_shared` по необходимости
* `runtime/events.py` → `isomorph/events/runtime_bus.py`
* `runtime/registry.py` → разделить на `actions/registry.py`, `policies/registry.py`, `plugins/loader.py`
* `policies/*` → `isomorph/policies/*`
* `nodes/vision/*` → `isomorph_packs.cv.actions/*`
* `nodes/io/*` → `isomorph_packs.cv.actions/*` или `isomorph_packs.edge.actions/*`

### Не переносить

* `core/graph.py`
* `core/graph_async.py`
* раздробленные `runtime/context/*` как есть

## Перенос из zesty_edge в Isomorph

### Переименовать / адаптировать

* `graph/dsl_models.py` → `isomorph/definitions/*`
* `graph/parser.py` → `isomorph/compiler/parser.py` или `loader.py`
* `actions/registry.py` → `isomorph/actions/registry.py`
* `pdca/metrics/*` → `isomorph/telemetry/*` или `plugins/metrics/*`
* `hw/*` → `isomorph_packs.edge.adapters.hw/*`
* `application/fsm.py` → `isomorph_packs.edge.domain/fsm.py` или прикладной слой поверх ядра

### Не переносить

* текущий `graph/runtime.py`
* текущий `application/dispatcher.py` в прямом виде
* текущий action constructor contract

---

## 11. Что реализовать первым

## Этап 1. Kernel Spec

Нужно описать документом:

* action contract;
* operator types;
* token model;
* execution semantics;
* event model;
* policy ownership.

## Этап 2. Minimal Compiler

Нужно реализовать:

* definition models;
* validator;
* planner в `ExecutionPlan`.

## Этап 3. Minimal Runtime

Нужно реализовать:

* action operator;
* branch operator;
* foreach operator;
* join operator;
* runtime events;
* in-memory state store.

## Этап 4. Registries + Plugins

Нужно реализовать:

* action registry;
* operator registry;
* metrics registry;
* entry-point loader.

## Этап 5. Product Packs

Сначала:

* `isomorph_packs.cv`
* `isomorph_packs.edge`

Позже:

* `isomorph_packs.minibar`

---

## 12. Первое MVP ядра

MVP считается готовым, если есть:

* загрузка workflow definition;
* компиляция в execution plan;
* запуск simple DAG;
* action node;
* branch node;
* foreach + join;
* runtime event stream;
* retry policy;
* базовые тесты на fan-in/fan-out.

---

## 13. Первые обязательные тесты

### Graph Semantics

* node with two upstreams waits on `join=all`;
* node with `join=any` starts after first input;
* foreach spawns child tokens;
* join collects foreach results correctly;
* branch routes only selected edges.

### Runtime Guarantees

* retry increments attempts and re-emits runtime events;
* timeout marks node failed;
* cancellation stops new scheduling;
* failure path is deterministic.

### Plugin/Registry

* action registry resolves built-ins;
* entry-point plugins load correctly;
* duplicate names are rejected.

---

## 14. Жёсткие архитектурные запреты

В Isomorph запрещено:

* action’у запускать следующий узел;
* event bus использовать как скрытый графовый роутер;
* вызывать child node вручную внутри `foreach`;
* исполнять raw DSL напрямую;
* держать разные action contracts в разных подсистемах;
* смешивать product FSM и kernel execution state.

---

## 15. Рекомендуемый порядок миграции

1. Создать новый пустой репозиторий `Isomorph`.
2. Сначала положить в него только spec + skeleton.
3. Реализовать minimal kernel без переноса старого runtime кода.
4. Перенести registry/event/policy идеи из Monocle.
5. Перенести DSL/parser ideas и packs из zesty_edge.
6. Перенести CV/edge actions как product packs.
7. Только потом заниматься CLI/API/UI.

---

## 16. Первое решение по naming

Основные сущности:

* `WorkflowDefinition`
* `ExecutionPlan`
* `ExecutionNode`
* `ExecutionToken`
* `ExecutionState`
* `Action`
* `ActionResult`
* `Operator`
* `RuntimeBus`
* `DomainBus`
* `PolicySet`

Проектовые наборы:

* `isomorph_packs.cv`
* `isomorph_packs.edge`
* `isomorph_packs.minibar`

---

## 17. Итог

`Isomorph` должен стать:

* не третьей вариацией старых ошибок;
* не свалкой перенесённого кода;
* а **новым чистым execution kernel**, в котором Monocle и zesty_edge выступают донорами идей и полезных модулей.

Формула проекта:

> **Kernel from scratch, migration by selection, not by copy-paste.**
