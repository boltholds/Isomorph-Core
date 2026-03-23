# Isomorph

## Идея

**Isomorph** — это единое ядро реактивного исполнения workflow-графов с DSL, control-операторами, action-реестром, event bus и runtime-политиками.

Цель проекта:
- не продолжать параллельно `Monocle` и `zesty_edge`;
- не склеивать их целиком;
- а собрать **новое чистое execution kernel**, в который переносится только полезное и уже доказавшее ценность.

Рабочее определение:

> **Isomorph = DSL-driven reactive workflow kernel**

То есть:
- workflow описывается декларативно;
- компилируется в execution plan;
- исполняется строгим runtime;
- действия изолированы как actions;
- управление исполнением реализуется отдельными control nodes/operators;
- runtime и domain events разделены.

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
- идею разделения на contracts / runtime / nodes / policies;
- typed contracts (`image`, `text`, `error`, base content idea);
- registry-ориентированный подход;
- policy-компилятор и отдельный слой политик как концепт;
- event builder / runtime event naming как основу telemetry;
- vision / io stubs как примеры actions;
- plugin/runtime bootstrap как источник идей, но не как готовую реализацию.

### Не переносить как есть
- текущий `GraphPipeline` и его семантику исполнения;
- текущий `GraphPipelineAsync`;
- размазанную систему runtime-context сущностей;
- дублирующуюся type compatibility logic;
- прямую связку графа и узлов без промежуточного execution plan.

### Переносить после упрощения
- contracts;
- registry;
- policies DSL;
- runtime event taxonomy;
- некоторые io/vision nodes как actions examples.

---

## Из zesty_edge

### Оставить
- общий вектор на event-driven runtime;
- DSL/IR-мышление (`dsl_models`, parser, runtime separation);
- FSM / context / dispatcher как идеи прикладного уровня;
- hardware layer (`hw`) как product adapters;
- PDCA / metrics registry как базу observability-плагинов;
- action registry и entry-point подход как основу plugin ecosystem.

### Не переносить как есть
- текущий action contract;
- текущую реализацию `foreach`;
- dispatcher/runtime с разными сигнатурами action;
- flow execution builder в текущем виде;
- прикладные сущности, если они смешаны с kernel-семантикой.

### Переносить после упрощения
- parser / DSL model ideas;
- registry mechanics;
- metrics and plugin ideas;
- hw/actions как product packs.

---

## Что выкинуть полностью

- Любой код, где action сам решает маршрутизацию исполнения.
- Любой код, где control-operator притворяется обычным action.
- Любой код, где event bus фактически управляет графом скрыто.
- Любой код, где sync/async — две почти независимые модели исполнения.
- Любой код, где runtime context раздроблен на много пересекающихся фасадов без одного центра.

---

## Целевая архитектура Isomorph

## 1. Слои

### A. Definition Layer
Чистая декларативная модель workflow.

Содержит:
- `WorkflowDefinition`
- `NodeDefinition`
- `EdgeDefinition`
- `PortDefinition`
- `PolicyDefinition`

Задача:
- хранить пользовательский DSL;
- не содержать логики исполнения.

### B. Compiler Layer
Преобразует definition в execution plan.

Содержит:
- validator;
- graph normalization;
- port resolution;
- policy compilation;
- control-node lowering;
- condition compilation.

Результат:
- `ExecutionPlan`
- `ExecutionNode`
- `CompiledPolicySet`

### C. Runtime Layer
Ядро исполнения.

Содержит:
- scheduler;
- dispatcher;
- token engine;
- node input buffers;
- retry/timeout/cancel policies;
- state transitions;
- checkpoint hooks;
- runtime events.

### D. Operators Layer
Специальные управляющие узлы.

Минимум:
- `ActionOperator`
- `BranchOperator`
- `ForeachOperator`
- `JoinOperator`
- `WaitForEventOperator`

### E. Action Layer
Предметные действия.

Примеры:
- `capture_image`
- `detect_objects`
- `crop_region`
- `classify_crop`
- `mqtt_publish`
- `read_sensor`
- `hardware_command`

### F. Infra Layer
Внешняя инфраструктура.

Содержит:
- runtime bus;
- domain bus;
- persistence;
- telemetry;
- plugin loading;
- CLI;
- API;
- MQTT/HTTP/DB adapters;
- hardware adapters.

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
- action получает только входы, контекст и конфиг;
- action не знает о графе целиком;
- action не запускает другие узлы;
- action не управляет маршрутизацией;
- action может эмитить domain events через `ActionResult.events` или сервис из контекста.

---

## 3. Типы узлов

## Task Nodes
Обычные work units.
- action
- transform
- validate

## Control Nodes
Операторы исполнения.
- branch
- foreach
- join
- wait_for_event
- merge

## Policy/Timing Nodes
- delay
- retry wrapper
- timeout wrapper
- debounce
- throttle

Принцип:
- В DSL это могут быть узлы.
- В runtime это должны быть **разные executor/operator types**.

---

## 4. Модель исполнения

## ExecutionPlan
Нормализованное описание исполнения.

Содержит:
- список execution nodes;
- входные/выходные порты;
- зависимости;
- operator kinds;
- compiled policies;
- start nodes.

## ExecutionToken
Единица прохождения по графу.

Содержит:
- `token_id`
- `execution_id`
- `current_node_id`
- `payload`
- `correlation_id`
- `parent_token_id`

## ExecutionState
Содержит:
- статус workflow instance;
- статусы узлов;
- input buffers;
- pending joins;
- retry counters;
- checkpoints;
- cancellation flags.

---

## 5. Семантика исполнения

## Fan-out
По умолчанию payload копируется в исходящие рёбра, если явно не указано иное.

## Fan-in / Join
Join управляется runtime.

Поддерживаемые режимы:
- `all`
- `any`
- `quorum(n)`
- `collect`

Узел не стартует, пока не выполнено правило join.

## Foreach
`foreach`:
- читает список items из входа;
- создаёт дочерние tokens;
- запускает child subtree для каждого item;
- собирает результаты через `collect`/`join`.

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
- `workflow_started`
- `workflow_completed`
- `node_started`
- `node_completed`
- `node_failed`
- `token_spawned`
- `retry_scheduled`
- `workflow_cancelled`

Назначение:
- observability;
- tracing;
- UI;
- debugging;
- replay.

## Domain Bus
Предметные события:
- `image_captured`
- `door_opened`
- `sku_detected`
- `temperature_alert`

Назначение:
- реактивная логика;
- интеграции;
- внешние подписчики.

Правило:
- runtime bus не должен скрыто определять маршрутизацию графа.

---

## 7. Политики

Политики должны компилироваться отдельно и применяться в runtime.

Минимальный набор:
- retry;
- timeout;
- overflow/backpressure;
- concurrency limit;
- fallback;
- sync barrier;
- circuit breaker.

Решение:
- перенести идею policy layer из Monocle;
- переписать её под `ExecutionPlan` и operator semantics.

---

## 8. Plugin System

Нужен единый plugin API.

Типы плагинов:
- action packs;
- adapters;
- metrics providers;
- serializers / codecs;
- domain packs.

Интерфейсы:
- `ActionRegistry`
- `OperatorRegistry`
- `MetricsRegistry`
- `CodecRegistry`

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
- `contracts/*` → `isomorph_packs.cv.contracts` или `isomorph.contracts_shared` по необходимости
- `runtime/events.py` → `isomorph/events/runtime_bus.py`
- `runtime/registry.py` → разделить на `actions/registry.py`, `policies/registry.py`, `plugins/loader.py`
- `policies/*` → `isomorph/policies/*`
- `nodes/vision/*` → `isomorph_packs.cv.actions/*`
- `nodes/io/*` → `isomorph_packs.cv.actions/*` или `isomorph_packs.edge.actions/*`

### Не переносить
- `core/graph.py`
- `core/graph_async.py`
- раздробленные `runtime/context/*` как есть

## Перенос из zesty_edge в Isomorph

### Переименовать / адаптировать
- `graph/dsl_models.py` → `isomorph/definitions/*`
- `graph/parser.py` → `isomorph/compiler/parser.py` или `loader.py`
- `actions/registry.py` → `isomorph/actions/registry.py`
- `pdca/metrics/*` → `isomorph/telemetry/*` или `plugins/metrics/*`
- `hw/*` → `isomorph_packs.edge.adapters.hw/*`
- `application/fsm.py` → `isomorph_packs.edge.domain/fsm.py` или прикладной слой поверх ядра

### Не переносить
- текущий `graph/runtime.py`
- текущий `application/dispatcher.py` в прямом виде
- текущий action constructor contract

---

## 11. Что реализовать первым

## Этап 1. Kernel Spec
Нужно описать документом:
- action contract;
- operator types;
- token model;
- execution semantics;
- event model;
- policy ownership.

## Этап 2. Minimal Compiler
Нужно реализовать:
- definition models;
- validator;
- planner в `ExecutionPlan`.

## Этап 3. Minimal Runtime
Нужно реализовать:
- action operator;
- branch operator;
- foreach operator;
- join operator;
- runtime events;
- in-memory state store.

## Этап 4. Registries + Plugins
Нужно реализовать:
- action registry;
- operator registry;
- metrics registry;
- entry-point loader.

## Этап 5. Product Packs
Сначала:
- `isomorph_packs.cv`
- `isomorph_packs.edge`

Позже:
- `isomorph_packs.minibar`

---

## 12. Первое MVP ядра

MVP считается готовым, если есть:
- загрузка workflow definition;
- компиляция в execution plan;
- запуск simple DAG;
- action node;
- branch node;
- foreach + join;
- runtime event stream;
- retry policy;
- базовые тесты на fan-in/fan-out.

---

## 13. Первые обязательные тесты

### Graph Semantics
- node with two upstreams waits on `join=all`;
- node with `join=any` starts after first input;
- foreach spawns child tokens;
- join collects foreach results correctly;
- branch routes only selected edges.

### Runtime Guarantees
- retry increments attempts and re-emits runtime events;
- timeout marks node failed;
- cancellation stops new scheduling;
- failure path is deterministic.

### Plugin/Registry
- action registry resolves built-ins;
- entry-point plugins load correctly;
- duplicate names are rejected.

---

## 14. Жёсткие архитектурные запреты

В Isomorph запрещено:
- action’у запускать следующий узел;
- event bus использовать как скрытый графовый роутер;
- вызывать child node вручную внутри `foreach`;
- исполнять raw DSL напрямую;
- держать разные action contracts в разных подсистемах;
- смешивать product FSM и kernel execution state.

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
- `WorkflowDefinition`
- `ExecutionPlan`
- `ExecutionNode`
- `ExecutionToken`
- `ExecutionState`
- `Action`
- `ActionResult`
- `Operator`
- `RuntimeBus`
- `DomainBus`
- `PolicySet`

Проектовые наборы:
- `isomorph_packs.cv`
- `isomorph_packs.edge`
- `isomorph_packs.minibar`

---

## 17. Итог

`Isomorph` должен стать:
- не третьей вариацией старых ошибок;
- не свалкой перенесённого кода;
- а **новым чистым execution kernel**, в котором Monocle и zesty_edge выступают донорами идей и полезных модулей.

Формула проекта:

> **Kernel from scratch, migration by selection, not by copy-paste.

---

## 18. Стартовый каркас репозитория Isomorph

Ниже — минимальный стартовый набор файлов и интерфейсов, с которых можно начинать новый репозиторий без переноса старого runtime-кода.

### Дерево проекта

```text
isomorph/
  pyproject.toml
  README.md
  .gitignore
  src/
    isomorph/
      __init__.py

      definitions/
        __init__.py
        workflow.py
        node.py
        edge.py
        ports.py
        policies.py

      compiler/
        __init__.py
        validator.py
        planner.py

      runtime/
        __init__.py
        engine.py
        state.py
        token.py
        node_state.py

      operators/
        __init__.py
        base.py
        action.py
        branch.py
        foreach.py
        join.py

      actions/
        __init__.py
        contracts.py
        context.py
        result.py
        registry.py

      events/
        __init__.py
        runtime_bus.py
        domain_bus.py
        models.py

      policies/
        __init__.py
        retry.py
        timeout.py

      persistence/
        __init__.py
        interfaces.py
        memory.py

      plugins/
        __init__.py
        loader.py

      telemetry/
        __init__.py
        logging.py
        metrics.py

  tests/
    test_validator.py
    test_planner.py
    test_runtime_simple_dag.py
    test_runtime_join.py
    test_runtime_foreach.py
```

---

## 19. Минимальный pyproject.toml

```toml
[project]
name = "isomorph"
version = "0.1.0"
description = "DSL-driven reactive workflow kernel"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7,<3.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "ruff>=0.6",
  "mypy>=1.10",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100

[tool.setuptools.packages.find]
where = ["src"]
```

---

## 20. Минимальные definition models

### `src/isomorph/definitions/ports.py`

```python
from pydantic import BaseModel


class PortRef(BaseModel):
    node_id: str
    port: str
```

### `src/isomorph/definitions/edge.py`

```python
from pydantic import BaseModel
from isomorph.definitions.ports import PortRef


class EdgeDefinition(BaseModel):
    source: PortRef
    target: PortRef
```

### `src/isomorph/definitions/node.py`

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


NodeKind = Literal["action", "branch", "foreach", "join"]


class NodeDefinition(BaseModel):
    id: str
    kind: NodeKind
    ref: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
```

### `src/isomorph/definitions/workflow.py`

```python
from pydantic import BaseModel, Field
from isomorph.definitions.node import NodeDefinition
from isomorph.definitions.edge import EdgeDefinition


class WorkflowDefinition(BaseModel):
    id: str
    version: str = "1.0"
    nodes: list[NodeDefinition] = Field(default_factory=list)
    edges: list[EdgeDefinition] = Field(default_factory=list)
```

---

## 21. План исполнения

### `src/isomorph/compiler/planner.py`

```python
from pydantic import BaseModel, Field
from isomorph.definitions.workflow import WorkflowDefinition


class ExecutionNode(BaseModel):
    id: str
    kind: str
    ref: str | None = None
    incoming: list[str] = Field(default_factory=list)
    outgoing: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    policy: dict = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    workflow_id: str
    nodes: dict[str, ExecutionNode]
    start_nodes: list[str]


class WorkflowPlanner:
    def build(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        nodes = {
            node.id: ExecutionNode(
                id=node.id,
                kind=node.kind,
                ref=node.ref,
                config=node.config,
                policy=node.policy,
            )
            for node in workflow.nodes
        }

        for edge in workflow.edges:
            src = edge.source.node_id
            dst = edge.target.node_id
            nodes[src].outgoing.append(dst)
            nodes[dst].incoming.append(src)

        start_nodes = [node_id for node_id, node in nodes.items() if not node.incoming]
        return ExecutionPlan(workflow_id=workflow.id, nodes=nodes, start_nodes=start_nodes)
```

---

## 22. Валидация

### `src/isomorph/compiler/validator.py`

```python
from isomorph.definitions.workflow import WorkflowDefinition


class WorkflowValidationError(ValueError):
    pass


class WorkflowValidator:
    def validate(self, workflow: WorkflowDefinition) -> None:
        node_ids = [node.id for node in workflow.nodes]
        unique_ids = set(node_ids)

        if len(node_ids) != len(unique_ids):
            raise WorkflowValidationError("Node ids must be unique.")

        for edge in workflow.edges:
            if edge.source.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown source node: {edge.source.node_id}"
                )
            if edge.target.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown target node: {edge.target.node_id}"
                )
```

На первом этапе этого достаточно. Проверку циклов можно добавить следующим шагом.

---

## 23. Action contract

### `src/isomorph/actions/result.py`

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class ActionResult(BaseModel):
    status: Literal["success", "error", "skipped"] = "success"
    outputs: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    error: str | None = None
```

### `src/isomorph/actions/context.py`

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActionContext:
    execution_id: str
    node_id: str
    services: dict[str, Any] = field(default_factory=dict)
    cancellation_requested: bool = False
```

### `src/isomorph/actions/contracts.py`

```python
from typing import Protocol, Any
from isomorph.actions.context import ActionContext
from isomorph.actions.result import ActionResult


class Action(Protocol):
    async def run(
        self,
        inputs: dict[str, Any],
        ctx: ActionContext,
        config: dict[str, Any],
    ) -> ActionResult:
        ...
```

### `src/isomorph/actions/registry.py`

```python
from typing import Type
from isomorph.actions.contracts import Action


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, Type[Action]] = {}

    def register(self, name: str, action_cls: Type[Action]) -> None:
        if name in self._actions:
            raise ValueError(f"Action already registered: {name}")
        self._actions[name] = action_cls

    def resolve(self, name: str) -> Type[Action]:
        try:
            return self._actions[name]
        except KeyError as exc:
            raise KeyError(f"Unknown action: {name}") from exc
```

---

## 24. Runtime model

### `src/isomorph/runtime/token.py`

```python
from pydantic import BaseModel, Field
from typing import Any
import uuid


class ExecutionToken(BaseModel):
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str
    current_node_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_token_id: str | None = None
```

### `src/isomorph/runtime/node_state.py`

```python
from typing import Literal
from pydantic import BaseModel


class NodeRunState(BaseModel):
    node_id: str
    status: Literal["idle", "waiting", "running", "done", "failed", "skipped"] = "idle"
    attempts: int = 0
```

### `src/isomorph/runtime/state.py`

```python
from pydantic import BaseModel, Field
from isomorph.runtime.node_state import NodeRunState


class ExecutionState(BaseModel):
    execution_id: str
    workflow_id: str
    node_states: dict[str, NodeRunState] = Field(default_factory=dict)
    input_buffers: dict[str, list[dict]] = Field(default_factory=dict)
    completed: bool = False
    failed: bool = False
```

---

## 25. Runtime events

### `src/isomorph/events/models.py`

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    type: Literal[
        "workflow_started",
        "workflow_completed",
        "node_started",
        "node_completed",
        "node_failed",
    ]
    execution_id: str
    node_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
```

### `src/isomorph/events/runtime_bus.py`

```python
from isomorph.events.models import RuntimeEvent


class InMemoryRuntimeBus:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def publish(self, event: RuntimeEvent) -> None:
        self.events.append(event)
```

### `src/isomorph/events/domain_bus.py`

```python
class InMemoryDomainBus:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def publish(self, event: dict) -> None:
        self.events.append(event)
```

---

## 26. Operators

### `src/isomorph/operators/base.py`

```python
from typing import Protocol
from isomorph.compiler.planner import ExecutionNode
from isomorph.runtime.token import ExecutionToken
from isomorph.actions.result import ActionResult


class Operator(Protocol):
    async def execute(
        self,
        node: ExecutionNode,
        token: ExecutionToken,
    ) -> ActionResult:
        ...
```

### `src/isomorph/operators/action.py`

```python
from isomorph.actions.context import ActionContext
from isomorph.actions.result import ActionResult
from isomorph.compiler.planner import ExecutionNode
from isomorph.runtime.token import ExecutionToken


class ActionOperator:
    def __init__(self, registry, services: dict | None = None) -> None:
        self._registry = registry
        self._services = services or {}

    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        action_name = node.ref
        if not action_name:
            return ActionResult(status="error", error=f"Node {node.id} has no action ref")

        action_cls = self._registry.resolve(action_name)
        action = action_cls()
        ctx = ActionContext(
            execution_id=token.execution_id,
            node_id=node.id,
            services=self._services,
        )
        return await action.run(token.payload, ctx, node.config)
```

### `src/isomorph/operators/branch.py`

```python
from isomorph.actions.result import ActionResult
from isomorph.compiler.planner import ExecutionNode
from isomorph.runtime.token import ExecutionToken


class BranchOperator:
    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        return ActionResult(outputs=token.payload)
```

### `src/isomorph/operators/foreach.py`

```python
from isomorph.actions.result import ActionResult
from isomorph.compiler.planner import ExecutionNode
from isomorph.runtime.token import ExecutionToken


class ForeachOperator:
    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        items = token.payload.get("items", [])
        return ActionResult(outputs={"items": items})
```

### `src/isomorph/operators/join.py`

```python
from isomorph.actions.result import ActionResult
from isomorph.compiler.planner import ExecutionNode
from isomorph.runtime.token import ExecutionToken


class JoinOperator:
    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        return ActionResult(outputs=token.payload)
```

На первом этапе `branch/foreach/join` могут быть заглушками, но их классы должны существовать отдельно уже сейчас.

---

## 27. Minimal runtime engine

### `src/isomorph/runtime/engine.py`

```python
import uuid
from collections import deque
from typing import Any

from isomorph.actions.registry import ActionRegistry
from isomorph.compiler.planner import ExecutionPlan
from isomorph.events.models import RuntimeEvent
from isomorph.events.runtime_bus import InMemoryRuntimeBus
from isomorph.operators.action import ActionOperator
from isomorph.operators.branch import BranchOperator
from isomorph.operators.foreach import ForeachOperator
from isomorph.operators.join import JoinOperator
from isomorph.runtime.token import ExecutionToken


class WorkflowRuntime:
    def __init__(
        self,
        action_registry: ActionRegistry,
        runtime_bus: InMemoryRuntimeBus | None = None,
    ) -> None:
        self._action_registry = action_registry
        self._runtime_bus = runtime_bus or InMemoryRuntimeBus()
        self._action_operator = ActionOperator(action_registry)
        self._branch_operator = BranchOperator()
        self._foreach_operator = ForeachOperator()
        self._join_operator = JoinOperator()

    async def run(self, plan: ExecutionPlan, inputs: dict[str, Any]) -> dict[str, Any]:
        execution_id = str(uuid.uuid4())
        queue = deque(
            ExecutionToken(
                execution_id=execution_id,
                current_node_id=node_id,
                payload=dict(inputs),
            )
            for node_id in plan.start_nodes
        )

        last_outputs: dict[str, Any] = {}

        await self._runtime_bus.publish(
            RuntimeEvent(type="workflow_started", execution_id=execution_id)
        )

        while queue:
            token = queue.popleft()
            node = plan.nodes[token.current_node_id]

            await self._runtime_bus.publish(
                RuntimeEvent(type="node_started", execution_id=execution_id, node_id=node.id)
            )

            if node.kind == "action":
                result = await self._action_operator.execute(node, token)
            elif node.kind == "branch":
                result = await self._branch_operator.execute(node, token)
            elif node.kind == "foreach":
                result = await self._foreach_operator.execute(node, token)
            elif node.kind == "join":
                result = await self._join_operator.execute(node, token)
            else:
                raise ValueError(f"Unsupported node kind: {node.kind}")

            if result.status == "error":
                await self._runtime_bus.publish(
                    RuntimeEvent(
                        type="node_failed",
                        execution_id=execution_id,
                        node_id=node.id,
                        payload={"error": result.error},
                    )
                )
                raise RuntimeError(result.error or f"Node {node.id} failed")

            last_outputs = result.outputs

            await self._runtime_bus.publish(
                RuntimeEvent(
                    type="node_completed",
                    execution_id=execution_id,
                    node_id=node.id,
                    payload=result.outputs,
                )
            )

            for nxt in node.outgoing:
                queue.append(
                    ExecutionToken(
                        execution_id=execution_id,
                        current_node_id=nxt,
                        payload=dict(result.outputs),
                        parent_token_id=token.token_id,
                    )
                )

        await self._runtime_bus.publish(
            RuntimeEvent(type="workflow_completed", execution_id=execution_id)
        )
        return last_outputs
```

Важно: этот runtime ещё **не реализует корректный fan-in/join semantics**. Но как стартовый каркас он подходит, потому что разделение уже сделано правильно.

---

## 28. In-memory persistence

### `src/isomorph/persistence/interfaces.py`

```python
from typing import Protocol
from isomorph.runtime.state import ExecutionState


class StateStore(Protocol):
    async def save(self, state: ExecutionState) -> None:
        ...

    async def load(self, execution_id: str) -> ExecutionState | None:
        ...
```

### `src/isomorph/persistence/memory.py`

```python
from isomorph.persistence.interfaces import StateStore
from isomorph.runtime.state import ExecutionState


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._storage: dict[str, ExecutionState] = {}

    async def save(self, state: ExecutionState) -> None:
        self._storage[state.execution_id] = state

    async def load(self, execution_id: str) -> ExecutionState | None:
        return self._storage.get(execution_id)
```

---

## 29. Пример action для первых тестов

### `tests/test_runtime_simple_dag.py`

```python
from isomorph.actions.result import ActionResult
from isomorph.actions.registry import ActionRegistry
from isomorph.compiler.planner import WorkflowPlanner
from isomorph.definitions.edge import EdgeDefinition
from isomorph.definitions.node import NodeDefinition
from isomorph.definitions.ports import PortRef
from isomorph.definitions.workflow import WorkflowDefinition
from isomorph.runtime.engine import WorkflowRuntime


class AddOneAction:
    async def run(self, inputs, ctx, config):
        value = inputs.get("value", 0)
        return ActionResult(outputs={"value": value + 1})


async def test_runtime_simple_dag():
    registry = ActionRegistry()
    registry.register("add_one", AddOneAction)

    workflow = WorkflowDefinition(
        id="wf",
        nodes=[
            NodeDefinition(id="n1", kind="action", ref="add_one"),
            NodeDefinition(id="n2", kind="action", ref="add_one"),
        ],
        edges=[
            EdgeDefinition(
                source=PortRef(node_id="n1", port="out"),
                target=PortRef(node_id="n2", port="in"),
            )
        ],
    )

    plan = WorkflowPlanner().build(workflow)
    runtime = WorkflowRuntime(registry)

    result = await runtime.run(plan, {"value": 1})
    assert result["value"] == 3
```

---

## 30. Что писать сразу после этого каркаса

После создания каркаса следующим коммитом нужно делать не плагины и не UI, а вот это:

1. корректный `join semantics`;
2. input buffers per node;
3. цикл-валидатор;
4. operator registry вместо ручных `if node.kind == ...`;
5. retry/timeout policies;
6. runtime/domain event separation в тестах;
7. первые pack’и `cv` и `edge`.

---

## 31. Первый набор коммитов

### Commit 1
`init: bootstrap isomorph kernel skeleton`

### Commit 2
`feat: add workflow definitions and execution planner`

### Commit 3
`feat: add action registry and base action contract`

### Commit 4
`feat: add minimal runtime engine and runtime bus`

### Commit 5
`test: cover validator, planner and simple dag execution`

### Commit 6
`feat: add join buffers and correct fan-in semantics`

### Commit 7
`feat: add foreach child token spawning`

---

## 32. Практический вывод

Стартовый каркас Isomorph должен быть:
- маленьким;
- честным;
- уже разделённым по слоям;
- но без фальшивой универсальности.

То есть лучше иметь минимальный runtime, который пока не умеет всё, чем большой каркас, где опять смешаны DSL, dispatcher, graph и event bus.
**

