# AI Model Router — Project

## 1. Summary

Build an intelligent routing layer for AI models that lets the user write a single prompt without having to decide which model to use.

Main flow:

```text
User
  ↓
AI Router
  ↓
JEB (fast selector)
  ↓
Optimal model selection
  ↓
Selected provider / model
  ↓
Response
```

The goal is not to create another chatbot, but to abstract away the complexity of the model ecosystem.

Value proposition:

> **Write whatever you want. We choose the right model.**

El router debe optimizar simultáneamente:

- quality esperada
- cost
- latency
- complejidad de la tarea
- context requerido
- multimodalidad
- herramientas disponibles
- privacy
- presupuesto del usuario
- disponibilidad/fallos de proveedores

---

# 2. Problema

There are many models with different capabilities, prices, speeds, and specializations.

For a normal user, it is difficult to answer:

- Which model should I use?
- Do I need reasoning?
- Do I need the most powerful model?
- Am I overpaying?
- Which model is best for coding?
- Which one is sufficient for summarization?
- Which one is best for long documents?
- What do I do if a provider is down?
- How do I keep costs low without sacrificing too much quality?

The application removes that manual decision.

---

# 3. Hipótesis principal

The hypothesis we need to validate:

> An extremely cheap and fast selector model can determine which generative model offers the best cost/quality tradeoff for a given task, reducing average cost without significantly reducing quality.

The primary metric will not simply be "which model wins."

It will be:

> **Can we achieve quality close to the frontier model while using significantly cheaper models whenever possible?**

---

# 4. Principio de diseño

We do not want JEB to answer the task.

JEB should be a **router**.

Example:

```text
Prompt:
"Analiza este contrato de 80 páginas y encuentra cláusulas
potencialmente contradictorias."

JEB:
- task_type: document_analysis
- reasoning: high
- context_requirement: high
- precision_requirement: very_high
- multimodal: false
- recommended_model: frontier_reasoning
- confidence: 0.91
```

Then:

```text
Router
  ↓
elige proveedor/modelo
  ↓
ejecuta el prompt original
```

La respuesta final procede del modelo seleccionado.

---

# 5. Arquitectura MVP

## Components

### A. API Gateway

Single entry point.

Responsibilities:

- authenticate the user
- receive the prompt
- receive configuration
- log the request
- send the request to the router
- execute the selected model
- return the response

Suggested initial stack:

- Python
- FastAPI
- Pydantic
- PostgreSQL
- Redis opcional

---

### B. Router

Decision-making layer.

Input:

```json
{
  "prompt": "...",
  "attachments": [],
  "budget": "balanced",
  "latency_preference": "balanced",
  "quality_preference": "high"
}
```

Output:

```json
{
  "model": "MODEL_ID",
  "provider": "PROVIDER",
  "confidence": 0.91,
  "reason": {
    "task_type": "coding",
    "reasoning_required": 0.84,
    "context_required": 0.32,
    "precision_required": 0.90
  }
}
```

---

### C. Model Registry

Centralized model catalog.

Do not hardcode model information inside the router.

Example:

```json
{
  "id": "provider/model-name",
  "provider": "provider",
  "capabilities": {
    "reasoning": 0.9,
    "coding": 0.95,
    "vision": true,
    "long_context": true
  },
  "pricing": {
    "input_per_million": 0.0,
    "output_per_million": 0.0
  },
  "latency": {
    "p50_ms": 0,
    "p95_ms": 0
  },
  "limits": {},
  "status": "active"
}
```

The registry must be updatable without changing router code.

---

### D. Provider Adapters

Each provider should sit behind a common interface.

Example:

```python
class ModelProvider:
    async def generate(
        self,
        messages,
        model,
        tools=None,
        attachments=None
    ):
        ...
```

Implementaciones:

```text
OpenAIAdapter
AnthropicAdapter
GoogleAdapter
OpenRouterAdapter
HuggingFaceAdapter
LocalModelAdapter
```

Initially connect only a few providers. The architecture must make it easy to add more later.

---

# 6. Primera versión de modelos

Do not try to support the entire market in the MVP.

Crear un pequeño pool representativo:

### Cheap/fast model

For:

- classification
- summarization
- extraction
- translation
- preguntas sencillas
- tareas rutinarias

### Mid-tier general-purpose model

For:

- writing
- coding
- analysis
- moderate reasoning

### Frontier model

For:

- complex reasoning
- architecture
- hard problems
- analysis de documents críticos
- tasks where quality justifies the cost

### Specialized model

Opcional:

- coding
- vision
- documents
- etc.

Specific model identifiers should be configured through environment/configuration and verified against each provider's current documentation.

---

# 7. JEB como router

JEB will initially be used as the decision component.

IMPORTANT:

No acoplar toda la architecture a JEB.

Crear una interfaz:

```python
class Router:
    async def route(self, request, candidates):
        ...
```

Initial implementation:

```python
class JEBRouter(Router):
    ...
```

In the future:

```text
JEBRouter
LearnedRouter
RulesRouter
EnsembleRouter
LocalRouter
```

This allows JEB to be replaced without rebuilding the product.

---

# 8. Prompt del router

The router should receive a structured representation of the options.

Conceptual example:

```text
You are an AI model routing system.

Your job is NOT to solve the user's task.

Determine which candidate model is most likely to solve
the task successfully while minimizing unnecessary cost
and latency.

Consider:

1. Task complexity
2. Reasoning requirements
3. Coding requirements
4. Context length
5. Multimodal requirements
6. Required precision
7. Expected output length
8. User latency preference
9. User budget
10. Model capabilities
11. Model cost
12. Model availability

Return ONLY structured routing data.
```

The output must be machine-parseable.

Never rely on free-form text for critical decisions.

---

# 9. Función objetivo

Initially use a conceptual function:

```text
Utility =
    QualityScore
    - CostPenalty
    - LatencyPenalty
    - RiskPenalty
```

Do not permanently hardcode arbitrary weights.

The system must allow experimentation with different weights.

Configuration:

```yaml
routing:
  quality_weight: 1.0
  cost_weight: 0.5
  latency_weight: 0.3
  risk_weight: 0.8
```

Más adelante los pesos podrán aprenderse a partir de resultados reales.

---

# 10. Estrategia fundamental: "sufficiently capable"

The router should not always select the highest-quality model.

It should seek:

> The cheapest model that has a sufficiently high probability of solving the task correctly.

Example:

```text
Task: translation sencilla

Cheap model:     99%
Medium model:    99%
Frontier model:  99%

→ Cheap
```

Otro:

```text
Task: architecture distribuida compleja

Cheap model:     45%
Medium model:    78%
Frontier model:  96%

→ Frontier
```

---

# 11. Confidence threshold

JEB confidence will be an important signal.

Example:

```text
confidence >= 0.90
→ execute the selected model

0.70 <= confidence < 0.90
→ seleccionar modelo más seguro

confidence < 0.70
→ fallback al modelo frontier
```

These thresholds must be configurable and later calibrated using data.

Do not initially assume that a probability emitted by JEB directly corresponds to the true probability of success.

We must measure calibration.

---

# 12. Segundo nivel: evaluación de respuesta

In a later phase:

```text
Prompt
 ↓
JEB
 ↓
Modelo seleccionado
 ↓
Response
 ↓
Evaluator
 ↓
¿Response suficiente?
   ↙           ↘
 Yes            No
 ↓              ↓
User       Retry / fallback
```

The evaluator can be another small model or a specialized system.

Example:

```json
{
  "quality": 0.91,
  "correctness": 0.94,
  "completeness": 0.87,
  "needs_retry": false
}
```

Do not introduce this into the initial MVP if it adds too much latency/cost.

First prove that direct routing works.

---

# 13. Fallbacks

All providers can fail.

The system must support:

```text
Modelo A
  ↓ error
Modelo B
  ↓ error
Modelo C
```

Failure types:

- timeout
- rate limit
- provider outage
- invalid request
- context overflow
- model unavailable
- tool incompatibility

Fallbacks must respect the budget and required capabilities.

---

# 14. Cost tracking

Each request should record:

```text
request_id
user_id
timestamp
router_model
selected_provider
selected_model
input_tokens
output_tokens
input_cost
output_cost
total_cost
latency_ms
status
fallback_used
```

Esto permitirá calcular el ROI real del router.

---

# 15. Métricas fundamentales

El MVP debe medir:

## Calidad

- success rate
- automated evaluation
- human evaluation on benchmark
- comparison against frontier model

## Coste

```text
cost_router
cost_best_frontier
savings = 1 - cost_router / cost_frontier
```

## Latencia

```text
routing_latency
generation_latency
total_latency
```

## Routing

- percentage of tasks sent to each model
- average confidence
- confidence vs actual success
- fallback rate
- error rate

---

# 16. Benchmark propio

Before building a sophisticated interface, create a task dataset.

Categories:

1. conversation
2. translation
3. summarization
4. extraction
5. classification
6. writing
7. razonamiento
8. math
9. coding
10. debugging
11. analysis documental
12. analysis multimodal
13. planning
14. tool-using tasks

Initially create 100-300 representative cases.

For each case:

```text
prompt
expected_properties
candidate_models
responses
quality_score
cost
latency
```

---

# 17. Experimento crítico #1

Compare:

### Baseline

Send every task to the frontier model.

vs.

### Router

JEB chooses the model.

Measure:

```text
Quality
Cost
Latency
```

Ideal result:

```text
Quality ≈ frontier
Cost << frontier
```

The initial priority is not to maximize savings at any cost.

A 50% cost reduction that destroys quality is not useful.

---

# 18. Experimento crítico #2

Compare routing against random selection.

This demonstrates whether JEB actually adds value.

---

# 19. Experimento crítico #3

Compare JEB against simple rules.

Example:

```text
if coding:
    use coding model

if reasoning:
    use frontier

else:
    use cheap
```

Si JEB no supera claramente reglas sencillas, hay que reconsiderar la architecture.

---

# 20. Experimento crítico #4

Measure the router's own cost.

The question:

> How much does it cost to decide which model to use?

It must be a small fraction of the savings achieved.

Métrica:

```text
Router overhead / total savings
```

Si el routing consume demasiado, no merece la pena.

---

# 21. UX del MVP

The interface should be extremely simple.

Main screen:

```text
┌──────────────────────────────────────────┐
│ What do you want to do?                  │
│                                          │
│ Analiza este documento y encuentra...    │
│                                          │
│ 📎 Attach        Auto ▼        Send →     │
└──────────────────────────────────────────┘
```

Default:

```text
Auto
```

The user does not need to know any model.

---

# 22. Modos de usuario

Inicialmente:

### Auto

The router decides.

### Cheapest

Prioritizes cost.

### Fastest

Prioritizes latency.

### Best

Prioritizes quality.

### Custom

Allows adjustment:

```text
Cost ←────●────→ Quality
Latency ←──●────→ Quality
```

---

# 23. Transparencia

After each response, optionally show:

```text
Auto-selected: Model X
Estimated cost: $0.004
Routing confidence: 92%
```

Optionally:

> Why?

```text
High-context document analysis + high precision
requirement. Model X was selected because it offers
the required context and reasoning capability at lower
expected cost than the frontier model.
```

Do not reveal private internal reasoning from models. Show only summarized, auditable decision signals.

---

# 24. Extensión del navegador

Later phase.

Goal:

Let users use the router from any page.

Example:

```text
Select text
→ Ask AI
→ Auto
```

The extension sends the content to the router API.

Do not start here.

First validate the backend and product economics.

---

# 25. API pública

Once the system works:

```http
POST /v1/chat/completions
```

Users could specify:

```json
{
  "model": "auto",
  "messages": [...]
}
```

The application chooses the actual model.

This would allow developers to integrate the router into their own applications.

---

# 26. Arquitectura de alto nivel

```text
                       ┌──────────────────┐
                       │ Web / Extension  │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │    API Gateway   │
                       └────────┬─────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
                 ▼                             ▼
        ┌────────────────┐            ┌─────────────────┐
        │   JEB Router   │            │ Model Registry  │
        └───────┬────────┘            └─────────────────┘
                │
                ▼
        ┌─────────────────┐
        │ Policy / Budget │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Provider Router │
        └───────┬─────────┘
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
    Provider  Provider  Provider
       │        │         │
       └────────┼─────────┘
                ▼
             Response
                │
                ▼
        ┌─────────────────┐
        │ Metrics / Logs  │
        └─────────────────┘
```

---

# 27. Seguridad

From day one:

- encrypted API keys
- secrets outside source code
- HTTPS
- rate limiting
- authentication
- user isolation
- logs without sensitive content by default
- option not to store prompts
- clear retention policy
- spending limits

Never store provider keys in plaintext.

---

# 28. Privacidad

The router should support policies such as:

```text
allow_providers:
  - provider_a
  - provider_b

blocked_providers:
  - provider_c

data_policy:
  store_prompts: false
```

Para empresas esto puede convertirse en una parte importante del producto.

---

# 29. Modelo de negocio

## Individual

Monthly subscription.

Possible plans:

```text
Free
Pro
Power
```

## API

Charge per usage or apply a margin to inference cost.

## Teams

Per-user billing.

## Enterprise

- SSO
- analytics
- políticas
- auditoría
- límites
- proveedores privados
- modelos locales
- soporte

Do not set final pricing until real costs are known.

---

# 30. Ventaja competitiva potencial

Model selection should not be the only moat.

Build progressively:

### A. Routing data

```text
task → decision → model → result → quality
```

### B. Own benchmark

Continuous measurement of real models on real tasks.

### C. Cost/quality intelligence

Know when a cheap model is good enough.

### D. Feedback loop

```text
routing
 ↓
result
 ↓
evaluation
 ↓
training data
 ↓
better routing
```

### E. Integration

The more providers and applications the system supports, the more useful it becomes.

---

# 31. Riesgos

## Risk 1 — Providers build their own routing

Mitigation:

- provider independence
- multi-provider support
- global cost optimization
- privacy
- enterprise policies
- open-source/local models

## Risk 2 — JEB routes poorly

Mitigation:

- benchmark
- calibración
- fallback
- reglas híbridas
- entrenar posteriormente router propio

## Risk 3 — Routing adds too much latency

Mitigation:

- very fast selector
- caching
- classification ligera
- parallel routing when useful

## Risk 4 — Insufficient savings

Mitigation:

- measure economics before building the full product
- include cheap and specialized models
- optimize for budget

## Risk 5 — API complexity

Mitigation:

- provider adapters
- interfaz común
- provider-specific tests

---

# 32. Qué NO hacer inicialmente

Do not:

- build a huge interface
- support 50 models
- build a mobile app
- build the extension before the backend
- train a router from scratch
- implement complex agents
- store all prompts
- add an expensive evaluator to every request
- try to solve every modality
- spend money on infrastructure before validating routing

---

# 33. MVP real

The first goal is extremely concrete:

> Demonstrate that JEB can significantly reduce average inference cost while maintaining quality close to sending every task to a frontier model.

MVP:

```text
Python
FastAPI
JEB
3-5 modelos
2-3 proveedores
PostgreSQL
benchmark
cost tracking
basic web UI
```

---

# 34. Orden de implementación

## Fase 0 — Investigación

1. Verificar documentación y disponibilidad actuales de JEB.
2. Verificar APIs y precios actuales de los modelos candidatos.
3. Definir 3-5 modelos iniciales.
4. Definir benchmark.
5. Definir métricas.

## Fase 1 — Router offline

Construir:

```text
benchmark
 ↓
JEB
 ↓
selection
```

Sin API pública todavía.

Goal:

Validar decisiones.

## Fase 2 — Ejecución

Añadir adapters:

```text
router
 ↓
provider
 ↓
response
```

## Fase 3 — Métricas

Registrar:

- cost
- latency
- selection
- quality
- errores

## Fase 4 — API

Crear:

```text
POST /v1/chat/completions
```

## Fase 5 — UI

Interfaz mínima.

## Fase 6 — Evaluación

Compare:

```text
frontier-only
vs
JEB-router
vs
rules-router
```

## Fase 7 — Beta

Users reales.

---

# 35. Primer objetivo técnico

No empezar por el frontend.

Crear primero un comando:

```bash
python benchmark.py
```

It should produce:

```text
==================================================
AI MODEL ROUTER BENCHMARK
==================================================

Tasks: 200

Baseline:
  Cost:       $X.XX
  Quality:    XX.X%
  Latency:    XXXX ms

JEB Router:
  Cost:       $X.XX
  Quality:    XX.X%
  Latency:    XXXX ms

Savings:
  XX.X%

Quality delta:
  -X.X%

Routing overhead:
  XX ms
==================================================
```

This result determines whether it is worth continuing.

---

# 36. Criterio de éxito inicial

No fijar un número arbitrario antes de medir.

Pero buscar una combinación donde:

```text
quality ≈ baseline frontier
cost << baseline frontier
routing overhead << generation cost
```

Como objetivo experimental, una reducción de cost del orden de decenas de porcentaje manteniendo una pérdida de quality pequeña sería una señal fuerte para continuar.

---

# 37. Desarrollo con Claude Code

Claude should work incrementally.

First instruction:

> Lee este archivo completo. No empieces construyendo la interfaz. Primero inspecciona el repositorio, identifica el stack actual y determina qué necesitamos para construir el benchmark del router.

Then:

```text
1. Crear estructura del proyecto.
2. Implement Model Registry.
3. Implementar interfaces de Provider.
4. Implementar JEB Router.
5. Crear benchmark.
6. Añadir primer provider.
7. Añadir modelos candidatos.
8. Ejecutar benchmark.
9. Analizar resultados.
10. Solo entonces construir API/UI.
```

Claude must avoid assuming current prices, model names, endpoints, or capabilities: it should verify the relevant documentation and keep them configurable.

---

# 38. Estructura de repositorio propuesta

```text
ai-model-router/
├── README.md
├── PROJECT.md
├── pyproject.toml
├── .env.example
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── router/
│   │   ├── base.py
│   │   ├── jeb.py
│   │   ├── policies.py
│   │   └── scoring.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── provider_a.py
│   │   ├── provider_b.py
│   │   └── provider_c.py
│   │
│   ├── models/
│   │   ├── registry.py
│   │   └── schemas.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   └── telemetry/
│       ├── costs.py
│       └── metrics.py
│
├── benchmarks/
│   ├── tasks.jsonl
│   ├── run.py
│   └── evaluate.py
│
├── tests/
│   ├── test_router.py
│   ├── test_registry.py
│   └── test_providers.py
│
└── docs/
    ├── architecture.md
    ├── routing.md
    └── benchmark.md
```

---

# 39. Reglas de ingeniería

Claude must:

- keep components decoupled
- use static typing
- validate inputs
- write tests
- avoid duplication
- keep configuration outside source code
- do not hardcode prices
- do not hardcode API keys
- document important decisions
- use interfaces for providers and routers
- make small, descriptive commits
- do not introduce unnecessary dependencies

Before adding an abstraction, verify that it actually adds value.

---

# 40. Filosofía del producto

The product should follow this rule:

> **Complexity belongs to the router, not the user.**

The user should not need to know:

- which model to use
- which provider has the best price
- how much context is needed
- which model reasons best
- which model is available

They should only have to say:

> "Haz esto."

The system handles the rest.

---

# 41. Evolución futura

Después del MVP:

### Adaptive router

Learn from real outcomes.

### Personalization

Learn user preferences:

```text
user prefers:
  quality > cost
```

### Budget-based routing

```text
$0.01 → cheap
$0.10 → medium
$1.00 → frontier
```

### Multimodal routing

Choose models based on:

- text
- image
- audio
- video
- documents

### Tool-aware routing

Consider whether the model needs:

- web
- code
- terminal
- function calling
- computer use

### Local models

Integrate models running on local hardware.

### Enterprise

Policies, security, and observability.

---

# 42. Visión final

La vision no es:

> "Una app que usa JEB."

La vision es:

> **A universal intelligence layer between users and AI models.**

```text
                 ┌───────────────┐
                 │     USER      │
                 └───────┬───────┘
                         │
                         ▼
                ┌─────────────────┐
                │   AI ROUTER     │
                │                 │
                │ task analysis   │
                │ cost            │
                │ quality         │
                │ latency         │
                │ privacy         │
                │ capabilities    │
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       MODEL A         MODEL B        MODEL C
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                      RESULT
```

The final experience:

> **One prompt. Any task. The right model automatically.**

---

# 43. Primera tarea para Claude

When starting development, Claude must do exactly this:

1. Read `PROJECT.md`.
2. Inspect the entire repository.
3. Do not build UI yet.
4. Verify available technologies and APIs.
5. Design the minimum benchmark.
6. Implement Model Registry.
7. Implement the `Router` interface.
8. Implement the initial JEB integration.
9. Implement at least three candidate models.
10. Run an initial benchmark.
11. Report:
    - cost
    - latency
    - selection
    - quality
    - comparison against baseline
12. Only after analyzing the results should Claude propose the next iteration.

The absolute priority is **validar la economía y la quality del routing antes de invertir en producto, frontend o infraestructura compleja**.

---

# 44. Definición de "hecho" para el MVP

The MVP will be beta-ready when:

- a user can send a prompt
- the router can automatically select a model
- the task executes without manual intervention
- fallback exists
- se registre cost y latency
- a reproducible benchmark exists
- we can compare against a frontier baseline
- we can demonstrate with data whether routing provides savings
- adding a new model does not require modifying the core system

Until that is achieved, avoid secondary features.

---

## TL;DR

Construir:

```text
                    PROMPT
                       │
                       ▼
                 ┌──────────┐
                 │    JEB   │
                 │  ROUTER  │
                 └────┬─────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        CHEAP       MEDIUM      FRONTIER
          │           │           │
          └───────────┼───────────┘
                      ▼
                   ANSWER
```

La primera pregunta que debemos responder con code y datos es:

> **¿Puede JEB seleccionar sistemáticamente un modelo más barato sin producir una caída significativa de quality?**

If the answer is yes, build the product around that advantage.
