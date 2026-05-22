# Complete User → Code Workflow Map

This document traces every user action through the entire stack, from browser click to database write.

---

## How to Read This Document

Each section follows this structure:

```
USER ACTION
  └─► Frontend component + function   (frontend/src/...)
        └─► HTTP call                 (method + URL)
              └─► Backend router      (app/routers/...)
                    └─► Service/class (app/services/... or app/workflows/...)
                          └─► DB / AI / Storage
```

---

## 0. App Bootstrap — What Happens When the Page Loads

```
Browser opens https://app/
  └─► App.tsx — React Router matches path → renders page component
        └─► AuthContext.tsx — reads JWT from localStorage
              └─► if token exists: GET /api/auth/me
                    └─► app/routers/auth.py:51  get_me()
                          └─► auth.get_current_user() — decodes JWT → queries Client by user_id
                                └─► returns UserOut to frontend → user is "logged in"
```

---

## 1. Authentication

### 1a. Register

```
User fills form → clicks "Register"
  └─► RegisterPage.tsx
        └─► POST /api/auth/register
            Body: { username, email, password }
              └─► app/routers/auth.py:16  register()
                    └─► db.query(User).filter(email)  ← check no duplicate
                    └─► hash_password(body.password)  ← bcrypt hash
                    └─► Client(user_id=uuid4(), username, email, password_hash)
                    └─► db.add(client) + db.commit()  ← writes users + clients tables
                    └─► create_access_token(subject=user_id) ← HS256 JWT, 30 day expiry
              └─► Returns: { access_token, token_type: "bearer" }
        └─► setToken(token) → stored in localStorage
        └─► navigate("/workspace")
```

### 1b. Login

```
User fills form → clicks "Login"
  └─► LoginPage.tsx
        └─► POST /api/auth/login
            Body: { email, password }
              └─► app/routers/auth.py:39  login()
                    └─► db.query(Client).filter(email)
                    └─► verify_password(plain, hash)  ← bcrypt check
                    └─► create_access_token(subject=user_id)
              └─► Returns: { access_token }
        └─► setToken(token) → localStorage
        └─► navigate("/workspace")
```

Every subsequent request attaches `Authorization: Bearer <token>` via `apiFetch()` in `frontend/src/lib/api.ts:17`.

---

## 2. Projects

### 2a. View Project List

```
User navigates to /workspace (no ?projectId in URL)
  └─► WorkspacePage.tsx:145  → renders <ProjectPicker />
        └─► useEffect on mount:
              apiFetch(GET /api/projects)
                └─► app/routers/project.py  GET /
                      └─► db.query(Project).filter(user_id).order_by(creation_date DESC)
                └─► Returns: { projects: [{ id, project_name, status, total_edits, ... }] }
        └─► setProjects(data) → list renders in UI
```

### 2b. Create New Project

```
User clicks "+ Create new project"
  └─► WorkspacePage.tsx:95  → <CreateProjectModal open={true} />
        └─► CreateProjectModal.tsx
              └─► POST /api/projects
                  Body: { project_name }
                    └─► app/routers/project.py  POST /
                          └─► Project(project_name, status="draft", user_id=current_user.user_id)
                          └─► db.add(project) + db.commit()
                    └─► Returns: ProjectOut
              └─► setSearchParams({ projectId }) → URL becomes /workspace?projectId=5
```

### 2c. Select Existing Project

```
User clicks a project card
  └─► WorkspacePage.tsx:44  pick(id) → setSearchParams({ projectId: id })
        └─► URL becomes /workspace?projectId=N
        └─► WorkspacePage re-renders → returns <WorkspaceEditor projectId="N" />
```

---

## 3. Workspace Page Load (with a Project)

```
WorkspaceEditor mounts with projectId
  └─► useEffect #1 — fetch project name
        apiFetch(GET /api/projects/{projectId})
          └─► app/routers/project.py  GET /{project_id}
                └─► db.get(Project, id)
          └─► setProjectName(p.project_name)

  └─► useEffect #2 — restore latest session
        apiFetch(GET /api/workflow/edit-flow/sessions?project_id={projectId})
          └─► app/routers/edit_flow.py:137  get_latest_project_session()
                └─► EditFlowService(db).get_latest_for_project(project_id)
                      └─► SELECT * FROM edit_flow_sessions
                          WHERE project_id=N ORDER BY created_at DESC LIMIT 1
                └─► _session_out() — loads session + all messages
          └─► If found: restores sessionId, phase, messages, baseImageUrl, referenceUrls, editUrls

  └─► useEffect #3 — health check
        fetch(GET /api/health) → sets apiStatus ("ok" / "error")
```

---

## 4. Upload Base Image

### 4a. File Upload

```
User clicks "Upload file…" → picks a file
  └─► WorkspacePage.tsx:292  onPickBaseFile()
        └─► uploadImageFile(file)
              └─► POST /api/workflow/edit-flow/upload
                  Body: FormData { file }
                    └─► app/routers/edit_flow.py:78  upload_image()
                          └─► validates: content_type in {jpeg, png, webp, gif}, size < 10MB
                          └─► object_storage().put_bytes(raw, content_type)
                                └─► ObjectStorage.put_bytes()  (app/services/object_storage.py:109)
                                      └─► key = uuid4().hex + ".jpg"
                                      └─► MinioClient.put_object(bucket, key, bytes)
                                      └─► returns public URL: http://minio:9000/imgwen/{key}.jpg
                    └─► Returns: { url, content_type, size_bytes }
        └─► setBaseImageUrl(url) → preview image updates
```

### 4b. Paste URL

```
User types a URL into the input
  └─► WorkspacePage.tsx:607  onChange → setBaseImageUrl(e.target.value)
        └─► (local state only — no API call until "Start" is clicked)
```

---

## 5. Start Session

```
User clicks "Start"
  └─► WorkspacePage.tsx:331  startSession()
        └─► POST /api/workflow/edit-flow/sessions
            Body: { base_image_url, project_id }
              └─► app/routers/edit_flow.py:180  create_session()
                    └─► EditFlowService(db).create_session()
                          └─► app/services/edit_flow_service.py:152
                                └─► EditFlowSession(
                                      base_image_url = body.base_image_url,
                                      phase           = EditFlowPhase.chatting,
                                      reference_urls  = [],
                                      project_id      = N
                                    )
                                └─► db.add(row) + db.commit()
                    └─► _session_out(db, row.id) → returns full session with empty messages
              └─► Returns: { id, phase:"chatting", base_image_url, reference_urls:[], messages:[] }
        └─► setSessionId(s.id), setPhase("chatting"), setMessages([])
```

---

## 6. Chat Turn (User Sends a Message)

This is the core conversational loop.

```
User types message → presses Enter or clicks "Send"
  └─► WorkspacePage.tsx:403  sendChat()
        └─► sendChatMessage(text)
              └─► POST /api/workflow/edit-flow/sessions/{sessionId}/chat
                  Body: { message: "change my jacket to black" }
                    └─► app/routers/edit_flow.py:204  post_chat()
                          └─► EditFlowService(db).post_chat_turn(session_id, user_message)
                                └─► app/services/edit_flow_service.py:224

                                [STEP 1] If session.phase == edit_completed → reset to "chatting"

                                [STEP 2] Load history
                                  history = self.list_messages(session_id)
                                  └─► SELECT * FROM edit_flow_messages
                                      WHERE session_id=N ORDER BY id ASC

                                [STEP 3] Build multimodal message list
                                  _build_multimodal_messages(
                                    base_image_url,
                                    history,
                                    new_user_text,
                                    reference_urls
                                  )
                                  └─► resolve_for_model(base_image_url)
                                        └─► ObjectStorage.get_bytes(key) → base64 data:image URI
                                  └─► system prompt: REASONING_CHAT_SYSTEM (the big instruction block)
                                  └─► for each past message → build {role, content:[{image:base},{text:msg}]}
                                  └─► new user turn → [{image:base}, *refs, {text:note+message}]

                                [STEP 4] Save user message to DB
                                  append_message(role="user", content=user_message)
                                  └─► INSERT INTO edit_flow_messages (session_id, role, content)

                                [STEP 5] Call vision model (qwen-vl-max)
                                  DashScopeClient.multimodal_chat_text(
                                    model = settings.qwen_vision_model,
                                    messages = msgs
                                  )
                                  └─► app/services/dashscope_qwen.py:410
                                        └─► self._configure()  ← sets dashscope.api_key
                                        └─► MultiModalConversation.call(...)
                                        └─► self.multimodal_assistant_text(resp) → raw text

                                [STEP 6] Parse markers from AI response
                                  _parse_chat_markers(raw)
                                  └─► looks for [[REQUEST_REFERENCES]] → requested_refs = True
                                  └─► looks for [[GENERATE_REFERENCES]] → extracts gen_prompts list
                                  └─► strips markers → assistant_clean

                                [STEP 7a] If [[GENERATE_REFERENCES]] found — generate reference images
                                  for prompt in gen_prompts (max 3):
                                    DashScopeClient.generate_image_from_text(
                                      model = qwen_image_generation_model,  ← wan2.2-t2i-plus
                                      prompt = "flat-lay product photo of black hoodie..."
                                    )
                                    └─► ImageSynthesis.call(...) or ImageGeneration.call(...)
                                    └─► returns signed OSS URL (expires in ~1hr)
                                  generated_urls = [persist(u) for u in raw_urls]
                                    └─► object_storage.persist() downloads OSS → uploads to MinIO
                                        └─► permanent URL: http://minio:9000/imgwen/{uuid}.jpg

                                [STEP 8] Save assistant message to DB
                                  append_message(
                                    role="assistant",
                                    content=assistant_clean,
                                    reference_urls=generated_urls   ← attached images
                                  )
                                  └─► INSERT INTO edit_flow_messages (role, content, reference_urls)

                                [STEP 9] Update session phase if references were requested
                                  if requested_refs or generated_urls:
                                    session.phase = EditFlowPhase.awaiting_references
                                  db.commit()

                          └─► Returns: (assistant_clean, phase, requested_refs, generated_urls)
                    └─► Returns: EditFlowChatResponse {
                          assistant_message,
                          phase,
                          requested_references,
                          generated_reference_urls
                        }
              └─► setPhase(body.phase)
              └─► if requested_references: setRequestedRefs(true) → shows reference panel
              └─► syncSession(sessionId)  ← GET /sessions/{id} to refresh all state
```

---

## 7. Reference Handling

### 7a. AI Generated References (shown inline in chat)

```
AI reply included [[GENERATE_REFERENCES]] → images appear in the chat bubble
  └─► WorkspacePage.tsx:791  <ChatReferencePicker urls={m.reference_urls} ... />
        └─► User clicks an image thumbnail → toggleRefSelection(url)
              └─► setSelectedRefUrls([...prev, url]) (max 2)
        └─► User clicks "Use selected (N/2)"
              └─► applySelectedReferences(selectedRefUrls)
                    └─► POST /api/workflow/edit-flow/sessions/{id}/references
                        Body: { urls: [url1, url2] }
                          └─► app/routers/edit_flow.py:232  post_references()
                                └─► _normalize_ref_urls(body.urls, max_refs=2)
                                └─► EditFlowService(db).set_references(session_id, urls)
                                      └─► session.reference_urls = urls
                                      └─► session.phase = awaiting_references
                                      └─► db.commit()
                    └─► syncSession() → refreshes savedRefUrls in UI
                    └─► ingestReferenceUrlsQuietly(urls, ["Session"])
                          └─► fire-and-forget POST /references/ingest for each URL
                                └─► saves to Qdrant for future retrieval
```

### 7b. User Uploads a Reference File

```
User clicks "Upload ref 1" → picks file
  └─► WorkspacePage.tsx:308  onPickRefFile("a", e)
        └─► uploadImageFile(file)
              └─► POST /api/workflow/edit-flow/upload  (same as base image upload)
                    └─► MinIO.put_object(...)
              └─► url = permanent MinIO URL
        └─► setRefAEmbedded(url)
        └─► ingestReferenceToLibraryQuietly(url, ["Uploaded"])  ← background Qdrant ingest
```

### 7c. User Pastes a Reference URL + Saves

```
User types URL in "Reference 1 HTTPS URL" field
  └─► setRefAUrl(e.target.value)
User clicks "Save references"
  └─► WorkspacePage.tsx:475  saveReferences()
        └─► applySelectedReferences([refAEmbedded || refAUrl, refBEmbedded || refBUrl])
              └─► POST /sessions/{id}/references  (same as 7a above)
```

### 7d. Save Reference to Library

```
User clicks "Save ref 1 URL to library" or "Save to library"
  └─► WorkspacePage.tsx:483  saveRefToLibrary("a")
        └─► ingestReferenceToLibrary(url, ["Saved"])
              └─► frontend/src/lib/references.ts:83
                    └─► POST /api/workflow/edit-flow/references/ingest
                        Body: { image_url, description:"", tags:["Saved"] }
                          └─► app/routers/edit_flow.py:110  post_ingest_reference()
                                └─► ReferenceLibrary().ingest(image_url, description, tags)
                                      └─► app/services/reference_library.py
                                            [1] persist(image_url) → upload to MinIO
                                            [2] if no description:
                                                DashScopeClient.multimodal_chat_text(
                                                  vision model describes the image
                                                )
                                            [3] DashScopeClient.embed_text(description)
                                                  → float[1024] vector
                                            [4] QdrantReferenceSearch.ingest_reference(
                                                  image_url, description, vector, tags
                                                )
                                                  └─► Qdrant upsert with stable UUID5 point ID
                    └─► Returns: { point_id, description }
        └─► setLibraryMsg({ slot:"a", text:"Saved to library: ..." })
```

---

## 8. Run Image Edit — The Full AI Pipeline

```
User clicks "Run image edit"
  └─► WorkspacePage.tsx:498  runEdit()
        └─► POST /api/workflow/edit-flow/sessions/{sessionId}/run-edit
              └─► app/routers/edit_flow.py:252  post_run_edit()
                    └─► EditFlowService(db).run_image_edit(session_id)
                          └─► app/services/edit_flow_service.py:326

                    ─────────────────────────────────────────────────────
                    [STEP 1] Load session + build transcript
                    ─────────────────────────────────────────────────────
                          msgs = list_messages(session_id)
                          transcript = _transcript(msgs)
                            └─► "USER: change my jacket...\nASSISTANT: ..."

                    ─────────────────────────────────────────────────────
                    [STEP 2] Vision consolidation — understand the scene
                    ─────────────────────────────────────────────────────
                          DashScopeClient.vision_reasoning_json(
                            model = qwen_vision_model,
                            base_image_url = resolve_for_model(session.base_image_url),
                            user_prompt = "Read the thread, output JSON with:
                              scene_description, salient_objects, user_goal,
                              constraints, retrieval_query"
                          )
                          └─► app/services/dashscope_qwen.py:431
                                └─► MultiModalConversation.call(model, messages)
                          └─► Returns reasoning dict:
                                {
                                  scene_description: "Person wearing a white hoodie...",
                                  salient_objects:   ["hoodie", "person", "background"],
                                  user_goal:         "Change hoodie to black with Puma logo",
                                  constraints:       ["keep same person", "keep pose"],
                                  retrieval_query:   "black Puma hoodie product shot"
                                }

                    ─────────────────────────────────────────────────────
                    [STEP 3–7] ImageEditWorkflow.run()
                    ─────────────────────────────────────────────────────
                          workflow = ImageEditWorkflow()
                          └─► app/workflows/image_edit_workflow.py:199

                          [STEP 3] Detect edit type
                            _edit_type(user_prompt)
                            └─► scans for CLOTHING_KEYWORDS → "clothing"
                            └─► scans for HAIR_KEYWORDS → "hair"
                            └─► else → "general"
                            auto-selects: negative_prompt, ref_desc_prompt,
                                          identity_lock, planner_part2 instructions

                          [STEP 4] Embed retrieval query → vector
                            DashScopeClient.embed_text(
                              model = qwen_embedding_model,   ← text-embedding-v4
                              text  = "black Puma hoodie product shot"
                            )
                            └─► TextEmbedding.call(model, input)
                            └─► Returns: [0.023, -0.41, ...] (1024 floats)

                          [STEP 5] Vector search in Qdrant
                            QdrantReferenceSearch.search_references(
                              query_vector = [0.023, ...],
                              limit = 8
                            )
                            └─► Qdrant nearest-neighbour search
                            └─► Returns: [{ image_url, description, tags, score }, ...]

                          [STEP 6] Merge staged + retrieved references
                            staged = session.reference_urls  (user picked these)
                            retrieved_urls = Qdrant results
                            merged = staged first (max 2), top up from Qdrant
                            merged = [resolve_for_model(u) for u in merged]
                              └─► MinIO URLs → base64 data:image URIs for DashScope

                          [STEP 7] Vision model describes each reference image
                            for ref in merged:
                              DashScopeClient.multimodal_chat_text(
                                model = qwen_vision_model,
                                messages = [{ image: ref, text: ref_desc_prompt }]
                              )
                            └─► "Reference 1: Black zip-up hoodie, Puma logo chest, fleece..."

                          [STEP 8] Text planner writes the final edit prompt
                            DashScopeClient.text_json_completion(
                              model  = qwen_text_model,  ← qwen3.6-max (Responses API or OpenAI-compat)
                              system = planner_system,
                              user   = planner_user
                            )
                            planner_user contains:
                              - full conversation transcript
                              - reasoning JSON (scene, goal, constraints)
                              - extracted reference descriptions
                              - retrieved Qdrant styles
                            └─► Returns plan JSON:
                                {
                                  final_image_edit_prompt:
                                    "Keep the exact same person and scene from Image 1...
                                     [PART 2] Replace the hoodie with a black Puma zip-up hoodie,
                                     fleece texture, white Puma logo on left chest, avoid plastic look",
                                  reference_roles: [...],
                                  notes: "..."
                                }

                          [STEP 9] Image-edit model applies the edit
                            DashScopeClient.run_image_edit(
                              model              = qwen_image_edit_model,  ← qwen-image-edit-max
                              base_image_url     = base_image_url,
                              reference_image_urls = refs_for_edit,  (empty for hair edits)
                              edit_prompt        = final_image_edit_prompt,
                              negative_prompt    = "unrealistic fabric, ..."
                            )
                            └─► app/services/dashscope_qwen.py:621
                                  └─► builds content: [{image:base}, {image:ref1}, {text:prompt}]
                                  └─► MultiModalConversation.call(model, messages, n=1, size=1024*1024)
                                  └─► Returns edited image OSS URL (expires ~1 hr)

                          [STEP 10] Vision critic evaluates the result
                            DashScopeClient.critic_json(
                              model            = qwen_vision_model,
                              base_image_url   = original,
                              edited_image_url = edited,
                              user_prompt      = transcript,
                              edit_prompt      = final_prompt
                            )
                            └─► Returns { pass, score_1_to_10, issues, suggested_prompt_tweak }

                          └─► Returns ImageEditWorkflowResult {
                                reasoning, retrieved_references, plan,
                                edited_image_urls, critique, warnings,
                                planner_reasoning_text
                              }

                    ─────────────────────────────────────────────────────
                    [STEP 11] Save planner reasoning to DB (if returned)
                    ─────────────────────────────────────────────────────
                          append_message(role="reasoning", content=planner_reasoning)
                          └─► INSERT INTO edit_flow_messages (role="reasoning", content=trace)

                    ─────────────────────────────────────────────────────
                    [STEP 12] Persist edited images to MinIO
                    ─────────────────────────────────────────────────────
                          edited_image_urls = [persist(u) for u in result.edited_image_urls]
                            └─► downloads OSS URL → uploads to MinIO → returns permanent URL

                    ─────────────────────────────────────────────────────
                    [STEP 13] Save result to session
                    ─────────────────────────────────────────────────────
                          session.last_edit_result = { reasoning, plan, edited_image_urls, ... }
                          session.phase = EditFlowPhase.edit_completed
                          db.commit()

                    ─────────────────────────────────────────────────────
                    [STEP 14] Record in relational history
                    ─────────────────────────────────────────────────────
                          _record_relational_edit()
                          └─► Image(source_url=base_image_url)  → INSERT images
                          └─► Image(source_url=edited_urls[0])  → INSERT images
                          └─► ChatSession(
                                project_id, status="closed",
                                title=user_goal, description=final_prompt,
                                edit_sequence_number = last_seq + 1,
                                original_image_id, edited_image_id
                              ) → INSERT chat_sessions
                          └─► Project.total_edits += 1
                          └─► Project.thumbnail_url = edited_urls[0]
                          └─► Project.last_interaction_time = now()
                          └─► db.commit()

                    ─────────────────────────────────────────────────────
                    [STEP 15] Chain: next edit starts from the output
                    ─────────────────────────────────────────────────────
                          session.base_image_url = edited_image_urls[0]
                          db.commit()
                          └─► the next "Start session" uses the edited image as base

              └─► Returns: EditFlowRunEditResponse {
                    phase, reasoning, retrieved_references,
                    plan, edited_image_urls, critique, warnings,
                    planner_reasoning_text
                  }
        └─► setEditUrls(body.edited_image_urls)
        └─► setPhase("edit_completed")
        └─► syncSession(sessionId)  ← refreshes everything
        └─► images appear in "Edited outputs" grid (right panel)
```

---

## 9. Post-Edit Feedback (Agree / Disagree)

```
Edit completes → "Planner and result" bar appears with Agree / Disagree buttons

User clicks "Agree"
  └─► WorkspacePage.tsx:410  sendPlannerFeedback(true)
        └─► sendChatMessage("I agree with the planner reasoning and the edit outcome.")
              └─► same as section 6 (Chat Turn)
              └─► service resets phase to "chatting" (edit_completed → chatting)

User clicks "Disagree"
  └─► sendPlannerFeedback(false)
        └─► sendChatMessage("I disagree with the planner reasoning or the edit outcome.")
        └─► setChatInput("I disagree because: ")
        └─► chatInputRef.current.focus() → user continues typing

User then sends follow-up → "Run image edit" again
  └─► new iteration: new chat turn → refine → run edit
      └─► session.base_image_url is now the PREVIOUS edited image
          so the model edits the already-edited output
```

---

## 10. Style Exploration / Reference Library

```
User navigates to /style-exploration
  └─► StyleExplorationPage.tsx
        └─► apiFetch(GET /api/workflow/edit-flow/references)
              └─► app/routers/edit_flow.py:100  get_reference_library()
                    └─► ReferenceLibrary().list()
                          └─► app/services/reference_library.py
                                └─► QdrantReferenceSearch.search.scroll(collection)
                                      ← paginated fetch of ALL stored reference points
                                └─► Returns [{ image_url, description, tags }]
        └─► renders grid of style tiles

User clicks "Start editing with this style" on a tile
  └─► navigate(`/workspace?ref=${encodeURIComponent(image_url)}`)
        └─► WorkspacePage loads with preloadedRef = image_url
        └─► When user clicks "Start":
              startSession()
              └─► payload.preloaded_reference_url = image_url
              └─► POST /sessions → EditFlowService.create_session(
                    preloaded_reference_url = image_url
                  )
                  └─► session.reference_urls = [image_url]  ← pre-loaded from the start
```

---

## 11. Edit History

```
User navigates to /history?projectId=N
  └─► HistoryPage.tsx
        └─► apiFetch(GET /api/workflow/edit-flow/project-history?project_id=N)
              └─► app/routers/edit_flow.py:149  get_project_history()
                    └─► EditFlowService(db).list_for_project(project_id)
                          └─► SELECT * FROM edit_flow_sessions
                              WHERE project_id=N ORDER BY created_at DESC
                    └─► For each session: unpacks last_edit_result JSON
                          → edited_image_urls, final_prompt, user_goal
              └─► Returns: { project_id, sessions: [EditFlowSessionSummary, ...] }
        └─► renders timeline of before/after image pairs
```

---

## State Machine Summary

The `EditFlowSession.phase` column acts as a state machine:

```
                  ┌──────────────────┐
  "Start" clicked │                  │
─────────────────►│    chatting      │◄──────────────────────────┐
                  │                  │                            │
                  └────────┬─────────┘                           │
                           │ AI responds with                     │ User sends
                           │ [[REQUEST_REFERENCES]] or            │ follow-up after
                           │ [[GENERATE_REFERENCES]]              │ agree/disagree
                           ▼
                  ┌──────────────────┐
                  │ awaiting_        │
                  │ references       │◄─── user saves refs
                  │                  │
                  └────────┬─────────┘
                           │ "Run image edit"
                           │ clicked
                           ▼
                  ┌──────────────────┐
                  │ edit_completed   │────► Agree/Disagree resets to chatting ──┘
                  │                  │
                  └──────────────────┘
                  (session.base_image_url is now the edited image)
```

---

## Data Written at Each Step

| User Action | Tables Written |
|---|---|
| Register | `users`, `clients` |
| Create project | `projects` |
| Upload image | MinIO bucket (binary blob) |
| Start session | `edit_flow_sessions` |
| Send chat message | `edit_flow_messages` (role=user) |
| AI replies | `edit_flow_messages` (role=assistant), MinIO (generated refs) |
| Save references | `edit_flow_sessions` (reference_urls updated) |
| Run edit | `edit_flow_sessions` (last_edit_result, phase, base_image_url) |
| Run edit | `edit_flow_messages` (role=reasoning, role=assistant) |
| Run edit | `images` (original + edited), `chat_sessions`, `projects` |
| Save to library | Qdrant (vector point), MinIO (image blob) |
