"""
Helpers for inspecting CBRAIN *Tool* and *ToolConfig* objects.

The functions in this module wrap high-level ``CbrainClient`` calls and emit
human-readable summaries via :pymod:`logging`.  No complex objects are returned
because the surrounding **CLI** (``cbrain-cli``) is intended for quick,
shell-friendly inspection rather than rich downstream processing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

from ..api.client_openapi import ApiException, CbrainClient, CbrainTaskError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------#
# Top-level queries                                                             #
# -----------------------------------------------------------------------------#
def list_tools(base_url: str, token: str) -> None:
    """Log every *Tool* visible to the current session.

    Args:
        base_url: Fully-qualified portal root
            (for example ``https://portal.cbrain.mcgill.ca``).
        token: Valid ``cbrain_api_token`` obtained from the CBRAIN REST session.

    Returns:
        None.  One INFO-level line per tool is written to the root logger.
    """
    client = CbrainClient(base_url, token)
    try:
        tools = client.list_tools()
    except ApiException as exc:
        logger.error("Failed to list tools: %s", exc)
        return

    logger.info("Found %d tools:", len(tools))
    # Show only salient attributes to keep the output concise.  Normalise
    # newlines to avoid ``\r\n`` sequences when tools have multi-line
    # descriptions.
    for tool in tools:
        desc = (tool.description or "").replace("\r", " ").replace("\n", " ").strip()
        logger.info(
            " - ID=%d, name=%r, desc=%s",
            tool.id,
            tool.name,
            desc,
        )


def list_tool_configs(base_url: str, token: str, per_page: int = 500) -> None:
    """List every *ToolConfig* visible to the current session.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        per_page: Pagination size when walking through the endpoint.

    Returns:
        None.  Information is logged at INFO level.
    """
    client = CbrainClient(base_url, token)
    try:
        configs = client.list_tool_configs(per_page=per_page)
    except ApiException as exc:
        logger.error("Failed to list tool configs: %s", exc)
        return

    logger.info("Found %d tool configs:", len(configs))
    for cfg in configs:
        # Fallback to *description* when *name* is missing (legacy servers).
        name = getattr(cfg, "name", None) or getattr(cfg, "description", None) or "<no name>"
        logger.info(
            " - ID=%d, tool_id=%d, name=%s, bourreau=%d",
            cfg.id,
            cfg.tool_id,
            name,
            cfg.bourreau_id,
        )


def fetch_boutiques_descriptor(base_url: str, token: str, tool_config_id: int) -> None:
    """Pretty-print the Boutiques JSON descriptor associated with *tool_config_id*.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        tool_config_id: Numeric identifier for the *ToolConfig* entry.

    Returns:
        None.  The descriptor is dumped at INFO level.
    """
    client = CbrainClient(base_url, token)
    try:
        descriptor = client.fetch_boutiques_descriptor(tool_config_id)
    except Exception as exc:  # noqa: BLE001 – propagate all failures equally
        logger.error(
            "Failed to fetch Boutiques descriptor for config %d: %s",
            tool_config_id,
            exc,
        )
        return

    logger.info(
        "Boutiques descriptor for ToolConfig ID=%d:\n%s",
        tool_config_id,
        json.dumps(descriptor, indent=2),
    )


def list_bourreaus(base_url: str, token: str) -> None:
    """Log the unique execution server IDs referenced by current tool configs.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
    """
    client = CbrainClient(base_url, token)
    try:
        configs = client.list_tool_configs()
    except ApiException as exc:
        logger.error("Failed to list tool configs: %s", exc)
        return

    seen: set[int] = set()  # Track duplicates.
    logger.info("Available bourreaus (HPC clusters) from tool configs:")
    for cfg in configs:
        bourreau = getattr(cfg, "bourreau_id", None)
        if bourreau is not None and bourreau not in seen:
            seen.add(bourreau)
            logger.info(" - Bourreau ID: %d (from tool_config %d)", bourreau, cfg.id)


def list_execution_servers(base_url: str, token: str) -> None:
    """Log every execution server returned by ``/bourreaux``.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
    """
    client = CbrainClient(base_url, token)
    try:
        # Raw ``dict`` objects are returned because the schema contains non-
        # string booleans which break the generated Pydantic models.
        servers: List[Dict[str, Any]] = client.list_bourreaus()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to list execution servers: %s", exc)
        return

    logger.info("Found %d execution servers:", len(servers))
    for srv in servers:
        desc = str(srv.get("description", "")).replace("\r", " ").replace("\n", " ").strip()
        logger.info(
            " - ID=%s, name=%r, desc=%s, online=%s, read_only=%s",
            srv.get("id"),
            srv.get("name", ""),
            desc,
            srv.get("online"),
            srv.get("read_only"),
        )


def list_tool_bourreaus_for_tool(base_url: str, token: str, tool_name: str) -> None:
    """Display the bourreau→ToolConfig mapping for *tool_name*.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        tool_name: Short CBRAIN tool name (case-insensitive).
    """
    client = CbrainClient(base_url, token)
    try:
        pairs: List[Tuple[int, int]] = client.list_tool_bourreaus_for_tool(tool_name)
    except (ApiException, ValueError) as exc:
        logger.error("Error fetching bourreaus for tool %r: %s", tool_name, exc)
        return

    logger.info("Configurations for %r:", tool_name)
    logger.info("tool_config_id   bourreau_id")
    logger.info("--------------   -----------")
    for cfg_id, bourreau_id in pairs:
        logger.info("%-14d %d", cfg_id, bourreau_id)


def describe_tool_config_and_server(
    base_url: str,
    token: str,
    tool_config_id: int,
    bourreau_id: int,
) -> None:
    """Summarise server name and tool version for a ToolConfig/Bourreau pair.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        tool_config_id: *ToolConfig* identifier.
        bourreau_id: Execution server (*Bourreau*) identifier.
    """
    client = CbrainClient(base_url, token)

    # Resolve bourreau (execution server) name.
    try:
        servers = client.list_bourreaus()
        bourreau_name = next(
            (srv.get("name") for srv in servers if srv.get("id") == bourreau_id),
            "<unknown>",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to list execution servers: %s", exc)
        bourreau_name = "<error>"

    # Retrieve Boutiques descriptor to extract the *tool-version* field.
    try:
        descriptor = client.fetch_boutiques_descriptor(tool_config_id)
        version = (
            descriptor.get("tool-version")
            or descriptor.get("tool_version")
            or "<no-version>"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch descriptor for config %d: %s", tool_config_id, exc)
        version = "<error>"

    logger.info("ToolConfig %d on bourreau %d:", tool_config_id, bourreau_id)
    logger.info("  → Server: %s", bourreau_name)
    logger.info("  → Tool-version: %s", version)


# -----------------------------------------------------------------------------#
# Misc. diagnostics                                                             #
# -----------------------------------------------------------------------------#
def test_openapi_tools(base_url: str, token: str) -> None:
    """Smoke-test the ``/tools`` endpoint via the OpenAPI bindings.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
    """
    client = CbrainClient(base_url, token)
    try:
        tools = client.list_tools()
    except ApiException as exc:
        logger.error("OpenAPI Tools endpoint failed: %s", exc)
        return

    logger.info("Found %d tools via OpenAPI:", len(tools))
    for tool in tools:
        logger.info(
            " - ID=%d, name=%r, category=%r",
            tool.id,
            tool.name,
            tool.category,
        )


def show_task_status(base_url: str, token: str, task_id: int) -> None:
    """Retrieve and log the status of a CBRAIN task.

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        task_id: Numeric identifier for the CBRAIN task.

    Returns:
        None.  The status string is logged.
    """
    client = CbrainClient(base_url, token)
    try:
        status = client.get_task_status(task_id)
    except CbrainTaskError as exc:
        logger.error("Could not fetch status for task %d: %s", task_id, exc)
        return

    logger.info("Task %d is at status: %s", task_id, status)


def fetch_all_tasks(
    client: CbrainClient,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Return **all** tasks visible to the session.

    Args:
        client:    Authenticated :class:`CbrainClient`.
        per_page:  Pagination size used for ``/tasks``.

    Returns:
        List of raw task dictionaries.
    """

    all_tasks: List[Dict[str, object]] = []
    page_num: int = 1

    while True:
        logger.debug("Fetching tasks page %d…", page_num)
        try:
            page_data = client.list_tasks(
                page=page_num,
                per_page=per_page,
                timeout=timeout,
            )
            page_tasks = [
                t.to_dict() if hasattr(t, "to_dict") else t for t in page_data
            ]
        except ApiException as exc:  # noqa: BLE001 -- propagate network errors
            logger.error("Could not fetch tasks (page %d): %s", page_num, exc)
            break

        all_tasks.extend(page_tasks)

        if len(page_tasks) < per_page:
            break

        page_num += 1

    return all_tasks


def list_tasks_by_group(
    client: CbrainClient,
    group_id: int,
    *,
    task_type: str | None = None,
    per_page: int = 100,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Filter tasks by project and, optionally, tool type.

    ``task_type`` may be a case-insensitive prefix of the CBRAIN task
    ``type`` field or a numeric ``tool_config_id``.
    """

    tasks = fetch_all_tasks(client, per_page=per_page, timeout=timeout)

    filtered = [t for t in tasks if t.get("group_id") == group_id]

    if task_type:
        wanted = str(task_type).lower()
        filtered = [
            t
            for t in filtered
            if (
                str(t.get("type", "")).lower().startswith(wanted)
                or str(t.get("type", "")).lower().split("::")[-1].startswith(wanted)
                or str(t.get("tool_config_id", "")).lower() == wanted
            )
        ]

    return filtered


def show_group_tasks_status(
    base_url: str,
    token: str,
    group_id: int,
    *,
    task_type: str | None = None,
    per_page: int = 100,
    timeout: float | None = None,
) -> None:
    """Log the status of every task in ``group_id``.

    Args:
        base_url:  CBRAIN portal root.
        token:     ``cbrain_api_token``.
        group_id:  Project identifier to search within.
        task_type: Restrict output to this tool type (optional).
        per_page:  Pagination size for task queries.
        timeout:   Optional HTTP timeout forwarded to the API.
    """

    client = CbrainClient(base_url, token)

    tasks = list_tasks_by_group(
        client,
        group_id,
        task_type=task_type,
        per_page=per_page,
        timeout=timeout,
    )

    suffix = f" with {task_type}" if task_type else ""
    logger.info("Found %d task(s)%s", len(tasks), suffix)
    for task in tasks:
        logger.info("Task %s is at status: %s", task.get("id"), task.get("status"))


def _is_failed(status: str) -> bool:
    """Return ``True`` if *status* represents a failure state."""

    return "fail" in status.lower()


def _is_recoverable(status: str) -> bool:
    """Return ``True`` if *status* represents a recoverable error or failure state."""

    status_lower = status.lower()
    return "error" in status_lower or "fail" in status_lower


def retry_task(
    base_url: str,
    token: str,
    task_id: int,
    *,
    timeout: float | None = None,
    current_status: str | None = None,
) -> None:
    """Request a retry of ``task_id`` if it is in a failed state.

    The function first checks the task's status to avoid spurious API
    calls on running or completed tasks.  Any HTTP or CBRAIN errors are
    logged but do not raise exceptions.
    """

    client = CbrainClient(base_url, token)
    if current_status is None:
        try:
            current_status = client.get_task_status(task_id)
        except CbrainTaskError as exc:  # pragma: no cover - network failure
            logger.error("Could not fetch status for task %d: %s", task_id, exc)
            return

    if not _is_failed(current_status):
        logger.info(
            "Task %d not in failed state (%s); skipping",
            task_id,
            current_status,
        )
        return

    status_lower = current_status.lower()
    if "setup" in status_lower:
        operation = "restart_setup"
    elif "cluster" in status_lower:
        operation = "restart_cluster"
    elif "post" in status_lower:
        operation = "restart_postprocess"
    else:
        operation = "restart_cluster"

    try:
        client.operate_tasks(operation, [task_id], timeout=timeout)
    except CbrainTaskError as exc:
        logger.error("Could not retry task %d: %s", task_id, exc)
        return

    logger.info("Retry requested for task %d", task_id)


def retry_failed_tasks(
    base_url: str,
    token: str,
    group_id: int,
    *,
    task_type: str | None = None,
    per_page: int = 100,
    timeout: float | None = None,
) -> None:
    """Retry every failed task within ``group_id``.

    Tasks are filtered by *task_type* if provided.  Only entries whose
    status contains ``"fail"`` (case-insensitive) trigger a retry.
    """

    client = CbrainClient(base_url, token)

    tasks = list_tasks_by_group(
        client,
        group_id,
        task_type=task_type,
        per_page=per_page,
        timeout=timeout,
    )

    failed = [t for t in tasks if _is_failed(str(t.get("status", "")))]
    logger.info("Found %d failed task(s)", len(failed))

    for task in failed:
        tid = task.get("id")
        if tid is None:
            continue
        retry_task(
            base_url,
            token,
            int(tid),
            timeout=timeout,
            current_status=str(task.get("status", "")),
        )


def error_recover_task(
    base_url: str,
    token: str,
    task_id: int,
    *,
    timeout: float | None = None,
    current_status: str | None = None,
) -> None:
    """Trigger error recovery for ``task_id`` if in a failed or error state."""

    client = CbrainClient(base_url, token)
    if current_status is None:
        try:
            current_status = client.get_task_status(task_id)
        except CbrainTaskError as exc:  # pragma: no cover - network failure
            logger.error("Could not fetch status for task %d: %s", task_id, exc)
            return

    if not _is_recoverable(current_status):
        logger.info(
            "Task %d not in recoverable state (%s); skipping",
            task_id,
            current_status,
        )
        return

    try:
        client.operate_tasks("recover", [task_id], timeout=timeout)
    except CbrainTaskError as exc:  # pragma: no cover - network failure
        logger.error("Could not recover task %d: %s", task_id, exc)
        return

    logger.info("Error recovery requested for task %d", task_id)


def error_recover_failed_tasks(
    base_url: str,
    token: str,
    group_id: int,
    *,
    task_type: str | None = None,
    per_page: int = 100,
    timeout: float | None = None,
) -> None:
    """Trigger error recovery for every task in ``group_id`` in failed or error state."""

    client = CbrainClient(base_url, token)

    tasks = list_tasks_by_group(
        client,
        group_id,
        task_type=task_type,
        per_page=per_page,
        timeout=timeout,
    )

    recoverable = [t for t in tasks if _is_recoverable(str(t.get("status", "")))]
    logger.info("Found %d recoverable task(s)", len(recoverable))

    for task in recoverable:
        tid = task.get("id")
        if tid is None:
            continue
        error_recover_task(
            base_url,
            token,
            int(tid),
            timeout=timeout,
            current_status=str(task.get("status", "")),
        )
