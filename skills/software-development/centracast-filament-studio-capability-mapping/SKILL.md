---
name: centracast-filament-studio-capability-mapping
description: Scan CentraCast Laravel Filament Studio surfaces (resources/pages/widgets), convert them into grouped human-web operational capabilities, and write the result into centracast-runtime architecture docs.
---

# CentraCast Filament Studio capability mapping

Use this when the task is to answer questions like:
- “What standard human operations already exist in the Studio web panel?”
- “Map Filament capabilities into operator actions / runtime contracts.”
- “Add Studio panel capability inventory into runtime docs.”

## Goal

Turn the Laravel Filament Studio panel from a vague UI surface into a concrete inventory of:
1. navigation groups
2. key resources/pages/widgets
3. human-triggerable actions
4. grouped operational capabilities
5. likely human web operations
6. runtime-boundary implications

## Repos and paths

Typical workspace:
- Laravel app: `/opt/gunamaya-ai/workspaces/centracast-studio/centracast`
- Runtime docs repo: `/opt/gunamaya-ai/workspaces/centracast-studio/centracast-runtime`

Primary code roots to scan:
- `app/Providers/Filament/StudioPanelProvider.php`
- `app/Filament/Studio/Resources/*`
- `app/Filament/Studio/Pages/*`
- `app/Filament/Studio/Widgets/*`

## Recommended workflow

### 1. Inspect the real Studio surfaces, not just route names

Read representative resource/page/widget files directly.
Prioritize:
- `*Resource.php`
- top-level `Pages/*.php`
- widgets backing dashboard/planner/analytics surfaces

Good signals to capture:
- `navigationGroup`
- `navigationLabel`
- `navigationSort`
- `Action::make(...)`
- `Section::make(...)`
- any `headerActions`, `bulkActions`, view-page actions, or dispatch jobs

Do not stop at model names alone. The useful truth is in the actions and forms.

### 2. Build the capability map by Studio navigation group

Expected groups often include things like:
- AI Ideation
- Raw Materials
- The Forge
- Broadcasting
- Infrastructure
- System

For each group, list:
- primary surfaces (resource/page/widget names)
- what a human can actually do from the panel
- the operational meaning of those capabilities
- likely human web operations represented by those capabilities

### 3. Translate UI affordances into human operations

Rewrite page/resource mechanics into plain-language operator actions.
Examples:
- “dispatch Suno generation” -> `generate music/audio`
- “create draft SingleRelease from asset” -> `turn audio track into release candidate`
- “drag-and-drop scheduled_publish_at” -> `reschedule content on calendar`
- “DispatchBroadcastJob / stop stream” -> `start/stop livestream`

This translation layer is the main value.

### 4. Capture the architectural implication

For CentraCast specifically, note whether Laravel is:
- only a system of record
- only a visibility layer
- or already a real human-operated execution console

Important finding from prior work:
- The Filament Studio panel already contains many real business mutations and job dispatches.
- So Laravel is not just persistence/visibility; it is already a fragmented human execution console.
- Runtime value is to unify these page-driven actions into structured action contracts with explicit done criteria.

### 5. Write the result into runtime docs

Best target docs are architecture/orchestration notes in `centracast-runtime/docs/`.
When patching docs, include sections like:
- capability map by Studio group
- dashboard/widget observations
- concrete inventory of standard human web operations
- boundary insight
- translation target for Telegram/runtime contract surface
- next-step implications

## Practical extraction heuristics

When scanning files, pay special attention to these patterns:
- `Action::make('...')`
- `Tables\Actions\Action::make('...')`
- `Infolists\Components\Actions\Action::make('...')`
- job dispatch calls like `::dispatch(...)`
- model updates changing schedule/publish/broadcast state
- form fields that reveal configuration authority (credentials, scheduling policy, infra settings)

Useful examples discovered previously:
- `PromptResource`: ideation, remix/extend, audio generation/regeneration
- `AssetResource`: upload assets, sync lyrics, create draft single release from audio asset
- `SingleReleaseWizard`: end-to-end single creation flow from concept to SEO/cover-art prep; also may dispatch direct YouTube upload on completion via `publishToYouTube()`
- `SingleReleaseResource`: cover art, thumbnails, slideshow assets, visualizer/media prep, Shorts actions, and ready-VOD publish actions
- `CompilationReleaseResource`: compilation assembly/render/thumbnail/publish-related actions
- `ViewSingleRelease`: detail-page Shorts publish actions and release-specific publish affordances worth checking separately from the table resource
- `ViewCompilationRelease`: confirmation-gated compilation publish to YouTube plus Shorts publish actions
- `BroadcastSessionResource`: start/stop broadcasts and monitor live sessions
- `ContentPlannerWidget`: schedule/reschedule VOD, Shorts, and compilations on a calendar
- `ChannelResource`: channel onboarding, infra config, YouTube connect, schedule policy
- `ClusterResource`: VPS + API key + BYOK OAuth config

## YouTube upload/publish audit checklist

When the user specifically asks about upload/publish capability, do not stop at broad capability language like “publish-related actions”. Verify the concrete semantics in code:
- whether publish exists on table actions, detail actions, wizard completion flow, or all three
- whether privacy/visibility is selectable (`public`, `unlisted`, `private`)
- whether there is an OAuth/token gate on the channel
- whether there is an environment gate such as `YouTubeUploadGate::enabled()`
- which status fields are updated (`youtube_upload_status`, `youtube_video_id`, `shorts_status`, etc.)
- which jobs are dispatched (`DispatchForemanUploadJob`, `UploadCompilationToYouTubeJob`, etc.)

If present, explicitly call out in the architecture doc that Laravel already has real human-triggered YouTube publication machinery. The gap to emphasize is then the runtime/Telegram action contract and done criteria, not the raw existence of publish capability.

## Good extension after the initial capability inventory

If the mapping is being used to design runtime execution, append three follow-on sections in the same doc:
1. capability matrix: Laravel Studio vs Runtime vs missing zone
2. intent-to-behavior map: intent -> backend mutation path -> done criteria
3. Telegram/runtime contract recommendations: normalized action names, request schema, publish guardrails, and honest status vocabulary

## Output style

Write the mapping in blunt human-readable architecture prose.
Good framing:
- “What the human can do from the web panel”
- “Human web operations represented here”
- “Operational meaning”
- “Boundary insight”

Avoid raw dump style. The goal is synthesis, not code transcription.

## Pitfalls

- Do not treat hidden/internal resources as primary user-facing capabilities; mark them as implementation intent or hidden surfaces.
- Do not assume a model implies a workflow; verify through actions/forms/view-page controls.
- Do not describe Laravel as merely CRUD if the resource dispatches jobs or mutates real business flow.
- Do not forget widgets/pages; planner and analytics meaning often lives there, not in resources.

## Done criteria

You are done when:
1. the major Studio groups are identified
2. key resources/pages/widgets are mapped to real human actions
3. the actions are translated into grouped operational capabilities
4. the runtime-boundary implication is stated clearly
5. the resulting analysis is inserted into the target runtime documentation
