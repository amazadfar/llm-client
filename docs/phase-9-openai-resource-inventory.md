# Phase 9 OpenAI Resource Inventory

Verified against:

- installed `openai` Python SDK `2.36.0`;
- official OpenAI API documentation on 2026-06-15;
- Phase 0 decision D5;
- `docs/milestone-5-phase-9-codex-handoff.md`.

This inventory describes package wrappers and installed-SDK availability. It does not
claim that every OpenAI account is entitled to every resource. Completion-model
capabilities remain catalog data and are intentionally separate from resource
availability.

## Implemented D5 Resources

| Resource | Package surface | SDK surface | Result types | Stability |
|---|---|---|---|---|
| Models | `list_models`, `retrieve_model` | `client.models.list/retrieve` | shared `ResourcePage`, `ModelInfo` | stable |
| Batches | existing Phase 6 lifecycle | `client.batches.*`, `client.files.*` | `BatchJob`, `BatchResultItem` | stable |
| Containers | create/retrieve/list/delete | `client.containers.*` | `ContainerResource`, `ContainersPage`, `DeletionResult` | stable |
| Container files | create/retrieve/list/delete | `client.containers.files.*` | `ContainerFileResource`, `ContainerFilesPage`, `DeletionResult` | stable |
| Skills | create/retrieve/list/update/delete | `client.skills.*` | `SkillResource`, `SkillsPage`, `DeletionResult` | stable |
| Skill versions | create/retrieve/list/delete | `client.skills.versions.*` | `SkillVersionResource`, `SkillVersionsPage`, `DeletionResult` | stable |
| Audio transcription | existing `transcribe_audio` | `client.audio.transcriptions.create` | `AudioTranscriptionResult` | stable |
| Audio translation | existing `translate_audio` | `client.audio.translations.create` | `AudioTranscriptionResult` | stable |
| Speech | existing `synthesize_speech` | `client.audio.speech.create` | `AudioSpeechResult` | stable |
| Realtime client secrets | existing client-secret/transcription-session wrappers | `client.realtime.client_secrets.create` | realtime typed results | stable |
| Realtime calls | existing create/accept/reject/hangup/refer | `client.realtime.calls.*` | `RealtimeCallResult` | stable |
| Realtime WebSocket | existing connect wrappers | `client.realtime.connect` | `RealtimeConnection` | stable |
| Videos | create, create-and-poll, retrieve, poll, list, delete, download, edit, extend, remix, character create/retrieve | `client.videos.*` | `VideoResource`, `VideosPage`, `VideoContentResult`, `VideoCharacterResource` | experimental |

Videos are marked experimental in their normalized results and resource discovery.
OpenAI's official guide describes the API as asynchronous and notes that remix is being
deprecated in favor of edit. The package exposes remix only as a compatibility operation
and directs new integrations to `edit_video`.

## SDK 2.36 Reconciliation

- Added `create_image_variation` for `client.images.create_variation`.
- Added `pause_fine_tuning_job` and `resume_fine_tuning_job` for
  `client.fine_tuning.jobs.pause/resume`.
- Confirmed current file, upload, vector-store, image generation/edit, audio
  transcription/translation/speech, Realtime call/client-secret/connect, and
  fine-tuning create/retrieve/list/cancel/event signatures.
- Confirmed transcription client secrets use
  `client.realtime.client_secrets.create(session=...)`; the legacy beta SDK also exposes
  `client.beta.realtime.transcription_sessions`, but the package does not add a second
  overlapping public path.

## Explicit Exclusions

These are documented exclusions, not claimed implementations:

| Surface | Reason |
|---|---|
| Container-file content download | Official endpoint exists, but installed SDK 2.36 has no `containers.files.content` method. No raw HTTP method is invented. |
| Skill content and skill-version content download | Official endpoints exist, but installed SDK 2.36 exposes no corresponding `skills` content helper. |
| Custom voice consent and custom voice lifecycle | Official docs describe the APIs for eligible customers, but installed SDK 2.36 exposes neither `audio.voice_consents` nor `audio.voices`. |
| Typed Realtime translations resource | Official docs describe `gpt-realtime-translate` transport, but installed SDK 2.36 has no `realtime.translations` client. Direct transport remains possible outside this typed resource layer. |
| Fine-tuning checkpoint permissions and grader administration | Not part of the Phase 0 D5 approved resource inventory. |
| Model deletion | Phase 9 Models scope is list/retrieve. SDK deletion applies to eligible fine-tuned models and is not presented as general catalog lifecycle. |
| Organization administration, billing, RBAC, audit logs, project management | Explicitly out of scope under D5. |

## Capability Discovery Contract

`OpenAIProvider.get_resource_availability()` returns
`ProviderResourceAvailability`:

- `available` means the installed SDK exposes the resource namespace;
- `unavailable` records SDK-bound exclusions and reasons;
- `experimental` identifies the Videos API;
- `account_access="unknown"` prevents SDK presence from being represented as account
  entitlement.

Model support remains separate:

- endpoint and broad native-tool support come from the model profile/catalog;
- exact native-tool validation uses catalog v2 `tools.server_tools` when present;
- unresolved models cannot use managed native tools without authoritative catalog
  metadata;
- no hardcoded model/tool compatibility matrix is introduced.

## Official References

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/guides/tools
- https://developers.openai.com/api/docs/guides/tools-skills
- https://developers.openai.com/api/docs/guides/tools-shell
- https://developers.openai.com/api/docs/guides/video-generation
- https://developers.openai.com/api/docs/guides/realtime
- https://developers.openai.com/api/docs/guides/text-to-speech
