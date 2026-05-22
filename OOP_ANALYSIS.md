# OOP Principles in imgwen-ado

## What Is This App?

**imgwen-ado** is an AI-powered image-editing platform. Users upload a photo, have a conversation with an AI assistant about what they want changed (e.g. "change my jacket to black with a Puma logo"), optionally attach style reference images, and then trigger a multi-step AI pipeline that produces the edited photo.

### How It Works — System Flow

```
User (browser)
  │
  │  1. Upload base image → POST /api/workflow/edit-flow/upload
  │  2. Start chat session → POST /api/workflow/edit-flow/sessions
  │  3. Chat about the edit → POST /sessions/{id}/chat        ← AI replies, may ask for references
  │  4. Attach references  → POST /sessions/{id}/references
  │  5. Trigger edit       → POST /sessions/{id}/run-edit
  │
FastAPI Backend
  │
  ├── Auth layer (JWT tokens)
  ├── EditFlowService  ← orchestrates the conversation state
  │     ├── DashScopeClient  ← calls Alibaba AI vision/text/image-edit models
  │     ├── ObjectStorage    ← stores images in MinIO (local S3)
  │     └── ImageEditWorkflow← multi-step AI pipeline
  │           ├── Vision model analyses the base image
  │           ├── Embedding model converts text→vectors
  │           ├── Qdrant (vector DB) finds matching style references
  │           ├── Text planner writes a precise edit prompt
  │           └── Image-edit model applies the edit
  │
PostgreSQL
  ├── users / clients     ← who is logged in
  ├── projects            ← a user's collection of work
  ├── edit_flow_sessions  ← one conversational editing thread
  └── edit_flow_messages  ← each chat turn in a session
```

---

## OOP Principle 1 — Encapsulation

### Concept

**Encapsulation** means bundling data (attributes) and the operations on that data (methods) together inside a class, and restricting direct access to internal state from outside.  
Think of it like a vending machine: you press a button and get a snack — you never reach inside the machine or care how it works internally.

Key signals in Python:
- A class `__init__` storing private state (`self._something`)
- Public methods that expose controlled operations
- Callers never touch raw internals

### In the Codebase

#### `ObjectStorage` — `app/services/object_storage.py:40`

```python
class ObjectStorage:
    """Thin wrapper around a single MinIO bucket for image blobs."""

    def __init__(self) -> None:
        self.bucket = settings.minio_bucket
        self.public_base = settings.minio_public_url.rstrip("/")
        self._owned_prefixes = tuple(...)   # private — callers never touch this
        self._client = Minio(...)           # private — the raw MinIO SDK client
        self._bucket_ready = False          # private — internal flag
```

The `_client`, `_owned_prefixes`, and `_bucket_ready` attributes are **private** (prefixed with `_`).  
Nobody outside the class ever creates a `Minio` object or manages the bucket policy.  
Instead, callers only use the clean public interface:

```python
# Public interface — all callers need to know:
storage.put_bytes(raw_bytes, content_type="image/png")  → returns public URL
storage.get_bytes("some-key")                           → returns (bytes, content_type)
storage.public_url("some-key")                          → returns full URL string
```

#### `DashScopeClient` — `app/services/dashscope_qwen.py:14`

```python
class DashScopeClient:
    def __init__(self, *, api_key: str, base_http_api_url: str) -> None:
        self.api_key = api_key
        self.base_http_api_url = base_http_api_url

    def _configure(self) -> None:       # private — sets module-level SDK globals
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = ...
```

Every time it makes an API call, it calls `self._configure()` first to re-apply credentials.  
Users of this class never touch `dashscope.api_key` directly — the class **encapsulates** that detail.  
The public methods (`embed_text`, `run_image_edit`, `critic_json`, etc.) are the only entry points needed.

#### `EditFlowService` — `app/services/edit_flow_service.py:21`

```python
class EditFlowService:
    REF_REQUEST_MARKER = "[[REQUEST_REFERENCES]]"  # class-level constant
    GEN_REFS_MARKER    = "[[GENERATE_REFERENCES]]"  # class-level constant

    def __init__(self, db: Session) -> None:
        self.db = db   # the database session is encapsulated here
```

All database queries, marker parsing, and AI calls are hidden inside this class.  
An API route handler just calls:

```python
service = EditFlowService(db)
text, phase, refs_requested, gen_urls = await service.post_chat_turn(session_id, user_message)
```

It has no idea that a multimodal vision model, message history construction, and state-machine transitions are happening behind that single call.

---

## OOP Principle 2 — Inheritance

### Concept

**Inheritance** allows one class (child / subclass) to acquire the attributes and methods of another class (parent / superclass). This models an **"is-a"** relationship.  
Example: a `Cat` *is-a* `Animal` — it inherits `eat()` and `sleep()` but can add `purr()`.

Key signals in Python:
- `class Child(Parent):` syntax
- Child class may override parent methods or add new ones
- `super()` to call parent logic

### In the Codebase

#### `User` → `Client` — `app/models/users/`

This is the clearest inheritance example in the project. It uses **SQLAlchemy's polymorphic inheritance** pattern to map the class hierarchy to two database tables (`users` and `clients`).

**Parent class** — `app/models/users/user.py:9`

```python
class User(Base):
    __tablename__ = "users"

    user_id:       Mapped[str] = mapped_column(String(36), primary_key=True)
    username:      Mapped[str] = mapped_column(String(255), nullable=False)
    email:         Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_type:     Mapped[str] = mapped_column(String(50))

    __mapper_args__ = {
        "polymorphic_on": user_type,   # tells SQLAlchemy: use this column to identify subclass
    }
```

**Child class** — `app/models/users/client.py:9`

```python
class Client(User):              # ← inherits from User
    __tablename__ = "clients"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)

    projects: Mapped[list["Project"]] = relationship(  # added by child
        back_populates="client",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": "client",  # the value stored in user_type column
    }
```

`Client` **inherits** `user_id`, `username`, `email`, `password_hash`, and `user_type` from `User`.  
It **adds** the `projects` relationship that belongs only to clients.  
When SQLAlchemy loads a row from the `users` table with `user_type = "client"`, it automatically returns a `Client` object — a `Client` *is-a* `User`.

#### Pydantic Schema Inheritance — `app/schemas/auth.py`

Pydantic `BaseModel` is also used via inheritance throughout the schemas layer:

```python
class RegisterRequest(BaseModel):   # inherits from Pydantic BaseModel
    username: str = Field(..., min_length=2, max_length=255)
    email:    str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

class UserOut(BaseModel):           # inherits from Pydantic BaseModel
    user_id:   str
    username:  str
    email:     str
    user_type: str
    model_config = {"from_attributes": True}  # added by child
```

All schemas inherit validation, serialisation, and `.model_dump()` from `BaseModel` for free.

---

## OOP Principle 3 — Abstraction

### Concept

**Abstraction** means hiding complex implementation details and exposing only a simplified interface.  
You interact with the *what*, not the *how*.  
Example: when you call `.sort()` on a list, you don't implement merge-sort — you just get sorted results.

Abstraction is closely related to Encapsulation but focuses on **simplifying the interface**, not just protecting data.

### In the Codebase

#### `ImageEditWorkflow` — `app/workflows/image_edit_workflow.py:37`

The workflow class abstracts a **5-step AI pipeline** into a single method call:

```python
class ImageEditWorkflow:
    """
    vision (qwen-vl) → Qdrant embedding search → text planner (qwen3) →
    qwen-image-edit-max → vision critic
    """

    def run(self, ...) -> ImageEditWorkflowResult:
        # Step 1: Vision model analyses base image + chat history → JSON scene description
        # Step 2: Embed the retrieval query → float vector
        # Step 3: Qdrant vector search → top-k reference images
        # Step 4: Text planner writes precise edit prompt
        # Step 5: Image-edit model applies the edit
        # Step 6: Vision critic scores the result
        # Step 7: Persist result images to MinIO
        ...
```

The caller in `EditFlowService` only sees:

```python
workflow = ImageEditWorkflow()
result = workflow.run(
    base_image_url=...,
    reference_urls=...,
    conversation_transcript=...,
    ...
)
edited_urls = result.edited_image_urls
```

All the model switching, prompt engineering, vector database calls, and image persistence are **abstracted away**.

#### `@dataclass ImageEditWorkflowResult` — `app/workflows/image_edit_workflow.py:27`

```python
@dataclass
class ImageEditWorkflowResult:
    reasoning:            dict[str, Any]
    retrieved_references: list[dict[str, Any]]
    plan:                 dict[str, Any]
    edited_image_urls:    list[str]
    critique:             Optional[dict[str, Any]]
    warnings:             list[str] = field(default_factory=list)
    planner_reasoning_text: Optional[str] = None
```

This **data class** abstracts all output from the pipeline into one structured object, so the caller doesn't have to unpack a tuple of seven values.

#### `DashScopeClient` method grouping — `app/services/dashscope_qwen.py`

The client class provides high-level abstractions over the low-level SDK:

| Abstraction (what you call) | What it hides underneath |
|---|---|
| `embed_text(model, text)` | `TextEmbedding.call()`, response parsing, vector extraction |
| `multimodal_chat_text(model, messages)` | `MultiModalConversation.call()`, error flattening, content parsing |
| `run_image_edit(model, base, refs, prompt)` | building the multi-image content list, SDK call, URL extraction |
| `critic_json(model, base, edited, prompt)` | building critic system prompt, call, JSON parsing |

---

## OOP Principle 4 — Polymorphism

### Concept

**Polymorphism** means "many forms" — the same interface (method name / class type) can behave differently depending on the actual object.  
There are two main types:
- **Subtype polymorphism**: a parent-type variable holding a child object, calling an overridden method
- **Method polymorphism via class/static methods**: the same class offering methods that work at the class level, not just on instances

### In the Codebase

#### SQLAlchemy Polymorphic Identity — `User` / `Client`

When SQLAlchemy fetches a user from the database, the `user_type` column determines which Python class is instantiated:

```python
# In User model:
__mapper_args__ = {"polymorphic_on": user_type}

# In Client model:
__mapper_args__ = {"polymorphic_identity": "client"}
```

If in future a `Designer` or `Admin` type were added, they'd also extend `User` with their own `polymorphic_identity`.  
A query for all `User` objects would return a mix of `Client`, `Designer`, `Admin` — same type variable, different actual objects. That is subtype polymorphism.

#### `@classmethod` vs `@staticmethod` vs instance methods — `DashScopeClient`

Python classes support three kinds of methods, all used in this codebase:

```python
class DashScopeClient:

    # INSTANCE METHOD — needs self (the specific object's api_key/base_url)
    def embed_text(self, *, model, text):
        self._configure()   # uses self.api_key
        ...

    # CLASS METHOD — receives the class itself, not an instance
    # Used here to call other class methods (like _flatten_error) without needing an instance
    @classmethod
    def _require_ok(cls, resp, step) -> None:
        detail, inner_code, _ = cls._flatten_error(resp)  # calls another classmethod
        ...

    # STATIC METHOD — no self, no cls — pure utility function namespaced to the class
    @staticmethod
    def parse_json_object(text: str) -> dict:
        raw = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if fence:
            raw = fence.group(1).strip()
        return json.loads(raw)
```

This is **method-level polymorphism** — three methods with the same syntactic call style but different binding behavior (bound to instance, class, or neither).

#### Edit-type Strategy — `ImageEditWorkflow` — `app/workflows/image_edit_workflow.py`

The workflow detects which *type* of edit is requested (clothing / hair / general) and dynamically selects different prompts and behavior:

```python
class ImageEditWorkflow:
    _CLOTHING_KEYWORDS = frozenset({"jacket", "hoodie", "shirt", ...})
    _HAIR_KEYWORDS     = frozenset({"hair", "hairstyle", "dye", ...})

    _NEGATIVE_PROMPTS = {
        "clothing": "...",   # garment-specific negative prompt
        "hair":     "...",   # hair-specific negative prompt
        "general":  "...",   # fallback
    }

    @classmethod
    def _edit_type(cls, prompt: str) -> str:   # returns "clothing", "hair", or "general"
        ...
```

The `run()` method then calls `self._edit_type(prompt)` and uses the result to look up the right prompt template from `_NEGATIVE_PROMPTS` and `_PLANNER_PART2`. Same method call (`_edit_type`) — different returned behavior. This is the **Strategy pattern** expressed through polymorphic dispatch.

---

## OOP Principle 5 — Composition

### Concept

**Composition** is an alternative to inheritance for code reuse. Instead of *inheriting* capabilities from a parent, a class *contains* objects of other classes as attributes and delegates work to them.  
It models a **"has-a"** relationship.  
Example: a `Car` *has-a* `Engine` — it doesn't extend `Engine`.

Composition is often preferred over deep inheritance hierarchies because it keeps classes focused.

### In the Codebase

#### `EditFlowService` composed of multiple services — `app/services/edit_flow_service.py`

```python
class EditFlowService:
    def __init__(self, db: Session) -> None:
        self.db = db    # has-a database session

    def run_image_edit(self, session_id, ...):
        # has-a DashScopeClient (created inside this method):
        client = DashScopeClient(api_key=settings.dashscope_api_key, ...)

        # has-a ImageEditWorkflow:
        workflow = ImageEditWorkflow()
        result   = workflow.run(...)

        # has-a ObjectStorage (via singleton):
        from app.services.object_storage import persist
        persisted_urls = [persist(u) for u in result.edited_image_urls]
```

`EditFlowService` **composes** `DashScopeClient`, `ImageEditWorkflow`, and `ObjectStorage` rather than inheriting from any of them.

#### `ImageEditWorkflow` composed of three services — `app/workflows/image_edit_workflow.py`

```python
class ImageEditWorkflow:
    def run(self, ...):
        client  = DashScopeClient(...)           # has-a AI client
        qdrant  = QdrantReferenceSearch(...)     # has-a vector database client
        storage = resolve_for_model              # has-a storage resolver
```

The workflow **delegates** to each service in turn — it owns the orchestration logic, not the individual capabilities.

---

## Summary Table

| Principle | Where in this codebase | File |
|---|---|---|
| **Encapsulation** | `ObjectStorage` hides `_client`, `_bucket_ready` | `app/services/object_storage.py:40` |
| **Encapsulation** | `DashScopeClient` hides `_configure()` and SDK globals | `app/services/dashscope_qwen.py:14` |
| **Encapsulation** | `EditFlowService` hides DB queries + AI calls behind `post_chat_turn()` | `app/services/edit_flow_service.py:21` |
| **Inheritance** | `Client` extends `User` (SQLAlchemy joined-table polymorphic) | `app/models/users/client.py:9` |
| **Inheritance** | All schemas extend Pydantic `BaseModel` | `app/schemas/auth.py` |
| **Abstraction** | `ImageEditWorkflow.run()` abstracts 6-step AI pipeline | `app/workflows/image_edit_workflow.py:37` |
| **Abstraction** | `DashScopeClient` methods abstract raw SDK calls | `app/services/dashscope_qwen.py` |
| **Polymorphism** | SQLAlchemy returns `Client` objects when querying `User` | `app/models/users/user.py:22` |
| **Polymorphism** | `@classmethod` / `@staticmethod` / instance methods co-exist | `app/services/dashscope_qwen.py` |
| **Polymorphism** | Edit-type strategy selects behavior at runtime | `app/workflows/image_edit_workflow.py:51` |
| **Composition** | `EditFlowService` *has-a* `DashScopeClient`, `ImageEditWorkflow`, `ObjectStorage` | `app/services/edit_flow_service.py` |
| **Composition** | `ImageEditWorkflow` *has-a* `DashScopeClient`, `QdrantReferenceSearch` | `app/workflows/image_edit_workflow.py` |
