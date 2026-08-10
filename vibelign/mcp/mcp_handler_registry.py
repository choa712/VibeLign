# === ANCHOR: MCP_HANDLER_REGISTRY_START ===
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Protocol, cast

from vibelign.core.feature_flags import is_enabled
from vibelign.core.memory.capability_grants import is_capability_granted


# === ANCHOR: MCP_HANDLER_REGISTRY_TEXTCONTENTFACTORY_START ===
class TextContentFactory(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY___CALL___START ===
    def __call__(self, *, type: str, text: str) -> object: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY___CALL___END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_TEXTCONTENTFACTORY_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_CHECKPOINTHANDLERSMODULE_START ===
class CheckpointHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_CREATE_START ===
    def handle_checkpoint_create(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_CREATE_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_LIST_START ===
    def handle_checkpoint_list(
        self, root: Path, text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_LIST_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_START ===
    def handle_checkpoint_restore(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_DIFF_START ===
    def handle_checkpoint_diff(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_DIFF_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_PREVIEW_RESTORE_START ===
    def handle_checkpoint_preview_restore(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_PREVIEW_RESTORE_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_FILES_START ===
    def handle_checkpoint_restore_files(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_FILES_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_SUGGESTIONS_START ===
    def handle_checkpoint_restore_suggestions(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_RESTORE_SUGGESTIONS_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_HAS_CHANGES_START ===
    def handle_checkpoint_has_changes(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CHECKPOINT_HAS_CHANGES_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RETENTION_APPLY_START ===
    def handle_retention_apply(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RETENTION_APPLY_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_CHECKPOINTHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_TRANSFERHANDLERSMODULE_START ===
class TransferHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_CREATE_START ===
    def handle_handoff_create(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_CREATE_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROJECT_CONTEXT_GET_START ===
    def handle_project_context_get(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROJECT_CONTEXT_GET_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_TRANSFERHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_HEALTHHANDLERSMODULE_START ===
class HealthHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_RUN_START ===
    def handle_doctor_run(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_RUN_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_GUARD_CHECK_START ===
    def handle_guard_check(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_GUARD_CHECK_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_HEALTHHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_PROTECTHANDLERSMODULE_START ===
class ProtectHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROTECT_ADD_START ===
    def handle_protect_add(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROTECT_ADD_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_PROTECTHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_ANCHORHANDLERSMODULE_START ===
class AnchorHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_RUN_START ===
    def handle_anchor_run(
        self, root: Path, text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_RUN_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_AUTO_INTENT_START ===
    def handle_anchor_auto_intent(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_AUTO_INTENT_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_SET_INTENT_START ===
    def handle_anchor_set_intent(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_SET_INTENT_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_GET_META_START ===
    def handle_anchor_get_meta(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_GET_META_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_READ_CONTENT_START ===
    def handle_anchor_read_content(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_READ_CONTENT_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_ANCHORHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_MISCHANDLERSMODULE_START ===
class MiscHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_EXPLAIN_GET_START ===
    def handle_explain_get(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_EXPLAIN_GET_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_LIST_START ===
    def handle_anchor_list(
        self, root: Path, text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_ANCHOR_LIST_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CONFIG_GET_START ===
    def handle_config_get(
        self, root: Path, text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_CONFIG_GET_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROJECT_MAP_GET_START ===
    def handle_project_map_get(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PROJECT_MAP_GET_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PLANNING_GET_START ===
    def handle_planning_get(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_PLANNING_GET_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_MISCHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_MEMORYHANDLERSMODULE_START ===
class MemoryHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_MEMORY_SUMMARY_READ_START ===
    def handle_memory_summary_read(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_MEMORY_SUMMARY_READ_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_CREATE_START ===
    def handle_handoff_draft_create(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_CREATE_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_ACCEPT_START ===
    def handle_handoff_draft_accept(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_ACCEPT_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_DISMISS_START ===
    def handle_handoff_draft_dismiss(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_DISMISS_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_UNDO_START ===
    def handle_handoff_draft_undo(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_HANDOFF_DRAFT_UNDO_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_MEMORYHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_RECOVERYHANDLERSMODULE_START ===
class RecoveryHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_PREVIEW_START ===
    def handle_recovery_preview(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_PREVIEW_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_RECOMMEND_START ===
    def handle_recovery_recommend(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_RECOMMEND_END ===

    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_APPLY_START ===
    def handle_recovery_apply(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_RECOVERY_APPLY_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_RECOVERYHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_DENIEDHANDLERSMODULE_START ===
class DeniedHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DENIED_CAPABILITY_START ===
    def handle_denied_capability(
        self,
        root: Path,
        arguments: dict[str, object],
        text_content: TextContentFactory,
        *,
        capability: str,
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DENIED_CAPABILITY_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_DENIEDHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_DOCTORHANDLERSMODULE_START ===
class DoctorHandlersModule(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_PLAN_START ===
    def handle_doctor_plan(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_PLAN_END ===


    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_APPLY_START ===
    def handle_doctor_apply(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY_HANDLE_DOCTOR_APPLY_END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_DOCTORHANDLERSMODULE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY_DISPATCHHANDLER_START ===
class DispatchHandler(Protocol):
    # === ANCHOR: MCP_HANDLER_REGISTRY___CALL___START ===
    def __call__(
        self, root: Path, arguments: dict[str, object], text_content: TextContentFactory
    ) -> list[object]: ...
    # === ANCHOR: MCP_HANDLER_REGISTRY___CALL___END ===
# === ANCHOR: MCP_HANDLER_REGISTRY_DISPATCHHANDLER_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__CHECKPOINT_HANDLERS_START ===
def _checkpoint_handlers() -> CheckpointHandlersModule:
    return cast(
        CheckpointHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_checkpoint_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__CHECKPOINT_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__TRANSFER_HANDLERS_START ===
def _transfer_handlers() -> TransferHandlersModule:
    return cast(
        TransferHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_transfer_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__TRANSFER_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HEALTH_HANDLERS_START ===
def _health_handlers() -> HealthHandlersModule:
    return cast(
        HealthHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_health_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__HEALTH_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__PROTECT_HANDLERS_START ===
def _protect_handlers() -> ProtectHandlersModule:
    return cast(
        ProtectHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_protect_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__PROTECT_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__ANCHOR_HANDLERS_START ===
def _anchor_handlers() -> AnchorHandlersModule:
    return cast(
        AnchorHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_anchor_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__ANCHOR_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__MISC_HANDLERS_START ===
def _misc_handlers() -> MiscHandlersModule:
    return cast(
        MiscHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_misc_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__MISC_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__MEMORY_HANDLERS_START ===
def _memory_handlers() -> MemoryHandlersModule:
    return cast(
        MemoryHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_memory_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__MEMORY_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__RECOVERY_HANDLERS_START ===
def _recovery_handlers() -> RecoveryHandlersModule:
    return cast(
        RecoveryHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_recovery_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__RECOVERY_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__DENIED_HANDLERS_START ===
def _denied_handlers() -> DeniedHandlersModule:
    return cast(
        DeniedHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_denied_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__DENIED_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__DOCTOR_HANDLERS_START ===
def _doctor_handlers() -> DoctorHandlersModule:
    return cast(
        DoctorHandlersModule,
        cast(object, importlib.import_module("vibelign.mcp.mcp_doctor_handlers")),
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__DOCTOR_HANDLERS_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_CHECKPOINT_LIST_START ===
def _handle_checkpoint_list(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    _ = arguments
    return _checkpoint_handlers().handle_checkpoint_list(root, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_CHECKPOINT_LIST_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_RUN_START ===
def _handle_anchor_run(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    _ = arguments
    return _anchor_handlers().handle_anchor_run(root, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_RUN_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_AUTO_INTENT_START ===
def _handle_anchor_auto_intent(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _anchor_handlers().handle_anchor_auto_intent(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_AUTO_INTENT_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_SET_INTENT_START ===
def _handle_anchor_set_intent(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _anchor_handlers().handle_anchor_set_intent(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_SET_INTENT_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_GET_META_START ===
def _handle_anchor_get_meta(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _anchor_handlers().handle_anchor_get_meta(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_GET_META_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_READ_CONTENT_START ===
def _handle_anchor_read_content(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _anchor_handlers().handle_anchor_read_content(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_READ_CONTENT_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_PROJECT_MAP_GET_START ===
def _handle_project_map_get(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _misc_handlers().handle_project_map_get(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_PROJECT_MAP_GET_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_PLANNING_GET_START ===
def _handle_planning_get(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _misc_handlers().handle_planning_get(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_PLANNING_GET_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_DECISION_START ===
def _handle_transfer_set_decision(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    from vibelign.mcp.mcp_transfer_handlers import handle_transfer_set_decision
    return handle_transfer_set_decision(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_DECISION_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_VERIFICATION_START ===
def _handle_transfer_set_verification(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    from vibelign.mcp.mcp_transfer_handlers import handle_transfer_set_verification
    return handle_transfer_set_verification(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_VERIFICATION_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_RELEVANT_START ===
def _handle_transfer_set_relevant(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    from vibelign.mcp.mcp_transfer_handlers import handle_transfer_set_relevant
    return handle_transfer_set_relevant(root, arguments, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_TRANSFER_SET_RELEVANT_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_MEMORY_FULL_READ_START ===
def _handle_memory_full_read(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _denied_handlers().handle_denied_capability(
        root, arguments, text_content, capability="memory_full_read"
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_MEMORY_FULL_READ_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_MEMORY_WRITE_START ===
def _handle_memory_write(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _denied_handlers().handle_denied_capability(
        root, arguments, text_content, capability="memory_write"
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_MEMORY_WRITE_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_RECOVERY_APPLY_START ===
def _handle_recovery_apply(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    tool = str(arguments.get("tool", ""))
    feature_enabled = is_enabled("RECOVERY_APPLY")
    if tool and is_capability_granted(root, tool, "recovery_apply") and feature_enabled:
        return _recovery_handlers().handle_recovery_apply(root, arguments, text_content)
    return _denied_handlers().handle_denied_capability(
        root, arguments, text_content, capability="recovery_apply"
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_RECOVERY_APPLY_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_HANDOFF_EXPORT_START ===
def _handle_handoff_export(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    return _denied_handlers().handle_denied_capability(
        root, arguments, text_content, capability="handoff_export"
    )
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_HANDOFF_EXPORT_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_LIST_START ===
def _handle_anchor_list(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    _ = arguments
    return _misc_handlers().handle_anchor_list(root, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_ANCHOR_LIST_END ===


# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_CONFIG_GET_START ===
def _handle_config_get(
    root: Path, arguments: dict[str, object], text_content: TextContentFactory
) -> list[object]:
    _ = arguments
    return _misc_handlers().handle_config_get(root, text_content)
# === ANCHOR: MCP_HANDLER_REGISTRY__HANDLE_CONFIG_GET_END ===


DISPATCH_TABLE: dict[str, DispatchHandler] = {
    "checkpoint_create": _checkpoint_handlers().handle_checkpoint_create,
    "checkpoint_list": _handle_checkpoint_list,
    "checkpoint_restore": _checkpoint_handlers().handle_checkpoint_restore,
    "checkpoint_diff": _checkpoint_handlers().handle_checkpoint_diff,
    "checkpoint_preview_restore": _checkpoint_handlers().handle_checkpoint_preview_restore,
    "checkpoint_restore_files": _checkpoint_handlers().handle_checkpoint_restore_files,
    "checkpoint_restore_suggestions": _checkpoint_handlers().handle_checkpoint_restore_suggestions,
    "checkpoint_has_changes": _checkpoint_handlers().handle_checkpoint_has_changes,
    "retention_apply": _checkpoint_handlers().handle_retention_apply,
    "memory_summary_read": _memory_handlers().handle_memory_summary_read,
    "handoff_draft_create": _memory_handlers().handle_handoff_draft_create,
    "handoff_draft_accept": _memory_handlers().handle_handoff_draft_accept,
    "handoff_draft_dismiss": _memory_handlers().handle_handoff_draft_dismiss,
    "handoff_draft_undo": _memory_handlers().handle_handoff_draft_undo,
    "memory_full_read": _handle_memory_full_read,
    "memory_write": _handle_memory_write,
    "recovery_preview": _recovery_handlers().handle_recovery_preview,
    "recovery_recommend": _recovery_handlers().handle_recovery_recommend,
    "recovery_apply": _handle_recovery_apply,
    "handoff_export": _handle_handoff_export,
    "handoff_create": _transfer_handlers().handle_handoff_create,
    "project_context_get": _transfer_handlers().handle_project_context_get,
    "doctor_run": _health_handlers().handle_doctor_run,
    "guard_check": _health_handlers().handle_guard_check,
    "protect_add": _protect_handlers().handle_protect_add,
    "anchor_run": _handle_anchor_run,
    "anchor_auto_intent": _handle_anchor_auto_intent,
    "anchor_set_intent": _handle_anchor_set_intent,
    "anchor_get_meta": _handle_anchor_get_meta,
    "anchor_read_content": _handle_anchor_read_content,
    "transfer_set_decision": _handle_transfer_set_decision,
    "transfer_set_verification": _handle_transfer_set_verification,
    "transfer_set_relevant": _handle_transfer_set_relevant,
    "explain_get": _misc_handlers().handle_explain_get,
    "anchor_list": _handle_anchor_list,
    "config_get": _handle_config_get,
    "project_map_get": _handle_project_map_get,
    "planning_get": _handle_planning_get,
    "doctor_plan": _doctor_handlers().handle_doctor_plan,
    "doctor_apply": _doctor_handlers().handle_doctor_apply,
}
# === ANCHOR: MCP_HANDLER_REGISTRY_END ===
