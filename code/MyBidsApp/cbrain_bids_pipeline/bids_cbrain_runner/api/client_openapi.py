"""Typed façade around the auto-generated *openapi_client* package.

The generated client (under :pyfile:`api/cbrain_openapi/`) is convenient but
exposes thousands of untyped attributes and requires a non-trivial amount of
boilerplate (e.g. manual token injection).  This wrapper provides three
improvements that simplify usage throughout *bids_cbrain_runner*:

1.  **Single entry point** – :class:`CbrainClient` bundles together the few
    API objects that are actually required (``ToolsApi``, ``TasksApi`` …).
2.  **Error handling** – Helper methods catch the most common failure modes
    (e.g. mixed JSON / plain-text responses, invalid Pydantic coercions) and
    raise consistent Python exceptions.
3.  **Light type-hints** – Return types are declared when practical, reducing
    the need for ``# type: ignore`` at call-sites.

Only CBRAIN-specific terminology is used; no project-specific business logic
belongs here.  The class is intentionally thin so that any new endpoints can be
added with minimal boilerplate.

Functions
---------
get_api_client
    Construct a token-authenticated :class:`openapi_client.ApiClient`.

Classes
-------
CbrainTaskError
    Raised when the API returns *success = False* or a non-2xx HTTP status.
CbrainClient
    Convenience wrapper that groups together the few OpenAPI endpoint objects
    needed by the CLI.
"""

from __future__ import annotations

import json
import logging
from typing import List, Tuple

from pydantic import ValidationError

from openapi_client.api.bourreaux_api import BourreauxApi
from openapi_client.api.groups_api import GroupsApi
from openapi_client.api.tasks_api import TasksApi
from openapi_client.api.userfiles_api import UserfilesApi
from openapi_client.api.tool_configs_api import ToolConfigsApi
from openapi_client.api.tools_api import ToolsApi
from openapi_client.api_client import ApiClient

# Auto-generated OpenAPI imports
from openapi_client.configuration import Configuration
from openapi_client.exceptions import ApiException
try:  # Actual OpenAPI models may be unavailable during tests
    from openapi_client.models.group import Group
    from openapi_client.models.group_mod_req import GroupModReq
    from openapi_client.models.multi_userfiles_mod_req import (
        MultiUserfilesModReq,
    )
    from openapi_client.models.batch_task_mod_req import BatchTaskModReq
except Exception:  # pragma: no cover - simplified stubs for unit tests
    class Group:
        """Lightweight stand-in for the OpenAPI ``Group`` model."""

        def __init__(self, **kwargs):
            """Store provided attributes without validation."""
            for k, v in kwargs.items():
                setattr(self, k, v)

        def to_dict(self) -> dict:
            """Return a dictionary representation of the instance."""
            return self.__dict__

    class GroupModReq:
        """Request payload for group modifications."""

        def __init__(self, group=None):
            """Initialize with an optional group value."""
            self.group = group

        def to_dict(self) -> dict:
            """Return a dictionary suitable for API calls."""
            return {"group": self.group}

    class MultiUserfilesModReq:
        """Request payload for multi-userfile operations."""

        def __init__(self, file_ids=None):
            """Initialize with an optional list of file identifiers."""
            self.file_ids = file_ids

        def to_dict(self) -> dict:
            """Return a dictionary representation for the API."""
            return {"file_ids": self.file_ids}

    class BatchTaskModReq:
        """Request payload for multi-task operations."""

        def __init__(self, tasklist=None, batch_ids=None):
            """Initialize with optional task and batch identifiers."""
            self.tasklist = tasklist
            self.batch_ids = batch_ids

        def to_dict(self) -> dict:
            """Return a dictionary representation for the API."""
            return {"tasklist": self.tasklist, "batch_ids": self.batch_ids}

# Low-level fallback helpers (pure ``requests``)
from .client import cbrain_get, cbrain_delete

logger = logging.getLogger(__name__)


class CbrainTaskError(Exception):
    """Raised when task creation fails or a task cannot be queried."""


def _stringify_api_error(data: object) -> str:
    """Return a human-friendly string from an API error payload.

    CBRAIN may return validation errors as a mapping of field names to lists
    of issues.  This helper flattens such structures into a readable message
    like ``"field is invalid"``.  Non-dictionary payloads are converted to
    ``str`` unchanged.
    """

    if isinstance(data, dict):
        parts = []
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                joined = ", ".join(str(v) for v in value)
            else:
                joined = str(value)
            parts.append(f"{key} {joined}".strip())
        if parts:
            return "; ".join(parts)
    return str(data)


def get_api_client(base_url: str, token: str) -> ApiClient:
    """Return a token-authenticated *ApiClient* instance.

    Args:
        base_url: Root of the CBRAIN portal, without trailing slash.
        token:    ``cbrain_api_token`` obtained from a session.

    Returns:
        A configured :class:`openapi_client.ApiClient`.
    """
    cfg = Configuration()
    cfg.host = base_url.rstrip("/")
    cfg.api_key["BrainPortalSession"] = token  # API expects this key name
    return ApiClient(configuration=cfg)


class CbrainClient:
    """Typed façade exposing a subset of CBRAIN endpoints.

    Only the calls required by the CLI are wrapped. New helpers can be added as
    needed.

    Attributes:
        base_url: Portal root URL without a trailing slash.
        token: ``cbrain_api_token`` supplied in every request.
        tools_api: Instance of :class:`openapi_client.ToolsApi`.
        toolconfigs_api: Instance of :class:`openapi_client.ToolConfigsApi`.
        bourreaux_api: Instance of :class:`openapi_client.BourreauxApi`.
        tasks_api: Instance of :class:`openapi_client.TasksApi`.
    """

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def __init__(self, base_url: str, token: str) -> None:
        """Initialise the client with a base URL and API token."""
        self.base_url = base_url.rstrip("/")
        self.token = token

        api_client = get_api_client(self.base_url, token)

        # Single instances are cheaper than constructing on every call.
        self.tools_api: ToolsApi = ToolsApi(api_client)
        self.toolconfigs_api: ToolConfigsApi = ToolConfigsApi(api_client)
        self.bourreaux_api: BourreauxApi = BourreauxApi(api_client)
        self.tasks_api: TasksApi = TasksApi(api_client)
        self.groups_api: GroupsApi = GroupsApi(api_client)
        self.userfiles_api: UserfilesApi = UserfilesApi(api_client)

    # ------------------------------------------------------------------
    # Thin wrappers around common OpenAPI calls
    # ------------------------------------------------------------------
    def list_tools(self) -> List:  # noqa: D401 (imperative mood)
        """Return every tool visible to the authenticated user."""
        return self.tools_api.tools_get()

    def list_tool_configs(self, per_page: int = 500) -> List:
        """Return every *ToolConfig* (up to ``per_page`` records)."""
        return self.toolconfigs_api.tool_configs_get(per_page=per_page)

    def list_bourreaus(self) -> List[dict]:
        """Return raw JSON describing all execution servers (bourreaux).

        The bourreaux endpoint contains fields that violate the strict typing
        expected by *pydantic*.  A plain ``requests`` fallback avoids those
        issues while still returning the full response body.
        """
        resp = cbrain_get(self.base_url, "bourreaux", self.token)
        resp.raise_for_status()
        return resp.json()

    def list_tasks(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        timeout: float | None = None,
    ) -> List:
        """Return tasks visible to the authenticated account.

        The generated OpenAPI models expect certain boolean fields as strings.
        To avoid validation errors, this method fetches the raw JSON payload and
        parses it directly, falling back to a plain ``GET`` request on failure.
        """
        try:
            raw = self.tasks_api.tasks_get_without_preload_content(
                page=page,
                per_page=per_page,
                _request_timeout=timeout,
            )
            return json.loads(raw.data)
        except ApiException as exc:
            logger.error("Failed to list tasks: %s", exc)
            raise
        except Exception as exc:  # noqa: broad-except -- network/JSON errors
            logger.warning("Falling back to raw JSON for list_tasks: %s", exc)
            resp = cbrain_get(
                self.base_url,
                "tasks",
                self.token,
                params={"page": page, "per_page": per_page},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    def list_groups(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        timeout: float | None = None,
    ) -> List[Group]:
        """Return groups visible to the authenticated account."""
        try:
            return self.groups_api.groups_get(
                page=page,
                per_page=per_page,
                _request_timeout=timeout,
            )
        except ApiException as exc:
            logger.error("Failed to list groups: %s", exc)
            raise

    def create_group(
        self,
        name: str,
        description: str | None = None,
        *,
        timeout: float | None = None,
    ) -> Group:
        """Create a new group on CBRAIN."""
        # ``GroupModReq`` expects the nested *Group* as a raw dictionary.
        # Passing a model instance triggers a validation error under
        # Pydantic 2.x, hence the explicit ``dict``.
        body = GroupModReq(group={"name": name, "description": description})
        try:
            return self.groups_api.groups_post(
                group_mod_req=body,
                _request_timeout=timeout,
            )
        except ApiException as exc:
            logger.error("Failed to create group %r: %s", name, exc)
            raise

    def list_userfiles(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        timeout: float | None = None,
    ) -> List:
        """Return userfiles visible to the authenticated account.

        The generated OpenAPI models expect certain boolean fields as strings.
        This helper bypasses the Pydantic deserialization by retrieving the raw
        JSON payload and parsing it directly.  If anything goes wrong, a
        secondary plain ``GET`` request is attempted as a final fallback.
        """
        try:
            raw = self.userfiles_api.userfiles_get_without_preload_content(
                page=page,
                per_page=per_page,
                _request_timeout=timeout,
            )
            return json.loads(raw.data)
        except ApiException as exc:
            logger.error("Failed to list userfiles: %s", exc)
            raise
        except Exception as exc:  # noqa: broad-except -- network/JSON errors
            logger.warning("Falling back to raw JSON for list_userfiles: %s", exc)
            resp = cbrain_get(
                self.base_url,
                "userfiles",
                self.token,
                params={"page": page, "per_page": per_page},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    def get_userfile(self, userfile_id: int, *, timeout: float | None = None):
        """Return the *Userfile* record for ``userfile_id``."""
        try:
            raw = self.userfiles_api.userfiles_id_get_without_preload_content(
                userfile_id, _request_timeout=timeout
            )
            return json.loads(raw.data)
        except ApiException as exc:
            logger.error("Failed to fetch userfile %s: %s", userfile_id, exc)
            raise
        except Exception as exc:  # noqa: broad-except -- network/JSON errors
            logger.warning(
                "Falling back to raw JSON for get_userfile %s: %s",
                userfile_id,
                exc,
            )
            resp = cbrain_get(
                self.base_url,
                f"userfiles/{userfile_id}",
                self.token,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    def delete_userfiles(self, ids: List[int], *, timeout: float | None = None) -> None:
        """Delete the userfiles with the specified IDs."""
        body = MultiUserfilesModReq(file_ids=[str(i) for i in ids])

        resp = cbrain_delete(
            self.base_url,
            "userfiles/delete_files",
            self.token,
            json=body.to_dict(),
            timeout=timeout,
            allow_redirects=False,
        )
        if resp.status_code not in (200, 302):
            resp.raise_for_status()

    def operate_tasks(
        self,
        operation: str,
        task_ids: List[int],
        *,
        timeout: float | None = None,
    ) -> object:
        """Apply *operation* to the tasks identified by *task_ids*.

        Args:
            operation: One of the operations supported by the
                ``/tasks/operation`` endpoint (e.g. ``"delete"``,
                ``"restart_cluster"``).
            task_ids: Iterable of task identifiers to operate on.
            timeout: Optional request timeout forwarded to the API client.

        Returns:
            The raw object returned by the underlying OpenAPI call.

        Raises:
            CbrainTaskError: If the API call fails.
        """
        body = BatchTaskModReq(tasklist=[int(t) for t in task_ids])
        try:
            return self.tasks_api.tasks_operation_post(
                operation=operation,
                tasklist=body,
                _request_timeout=timeout,
            )
        except ApiException as exc:  # pragma: no cover - network failure
            raise CbrainTaskError(
                f"Could not apply operation '{operation}' to tasks {task_ids}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Convenience helpers that combine multiple API calls
    # ------------------------------------------------------------------
    def get_task_status(self, task_id: int) -> str:
        """Return the status string for the specified task.

        A task may have been created by a previous CLI invocation or via the
        CBRAIN web interface.  The call falls back to raw JSON parsing if the
        Pydantic model fails (e.g. uncommon status strings).

        Args:
            task_id: Numeric task identifier.

        Returns:
            One of the CBRAIN status strings, such as ``"New"``, ``"Running"``,
            ``"Completed"``, ``"Failed"`` …
        """
        try:
            task = self.tasks_api.tasks_id_get(task_id)
            return task.status  # type: ignore[attr-defined]
        except (ApiException, ValidationError, TypeError):
            # Fall back to *without_preload_content* when strict typing fails.
            raw = self.tasks_api.tasks_id_get_without_preload_content(task_id)
            try:
                data = json.loads(raw.data)
                return data["status"]
            except (ValueError, KeyError) as parse_err:
                raise CbrainTaskError(
                    f"Could not determine status for task {task_id}"
                ) from parse_err  # Preserve original traceback

    def list_tool_bourreaus_for_tool(
        self, tool_name: str, *, per_page: int = 500
    ) -> List[Tuple[int, int]]:
        """Return ``(tool_config_id, bourreau_id)`` pairs for *tool_name*.

        Args:
            tool_name: Exact (case-insensitive) tool name as reported by CBRAIN.
            per_page: Maximum items per page when querying ``/tool_configs``.

        Returns:
            List of tuples linking configuration IDs to bourreau IDs.

        Raises:
            ValueError: If no tool matches *tool_name*.
        """
        tools = self.list_tools()
        match = next((t for t in tools if t.name.lower() == tool_name.lower()), None)
        if match is None:
            raise ValueError(f"No CBRAIN tool named '{tool_name}'")

        tool_id = match.id
        configs = self.list_tool_configs(per_page=per_page)
        return [(cfg.id, cfg.bourreau_id) for cfg in configs if cfg.tool_id == tool_id]

    def fetch_boutiques_descriptor(self, tool_config_id: int) -> dict:
        """Return the Boutiques JSON descriptor for a *ToolConfig*.

        Args:
            tool_config_id: Numeric identifier of the *ToolConfig*.

        Returns:
            Parsed JSON dictionary exactly as returned by the API.
        """
        endpoint = f"tool_configs/{tool_config_id}/boutiques_descriptor"
        resp = cbrain_get(self.base_url, endpoint, self.token)
        resp.raise_for_status()
        return resp.json()

    def create_task(self, task_body: dict) -> dict:
        """Create a new CBRAIN task.

        Args:
            task_body: Payload matching the schema required by the ``/tasks``
                endpoint (without the outer ``{"cbrain_task": …}`` wrapper).

        Returns:
            Parsed JSON response from CBRAIN.

        Raises:
            CbrainTaskError: If the HTTP response code is not 2xx **or** the
                returned JSON contains an ``"error"`` or ``"errors"`` key.
        """
        wrapper = {"cbrain_task": task_body}
        try:
            # Use the *without_preload_content* variant to access raw bytes.
            raw = self.tasks_api.tasks_post_without_preload_content(cbrain_task=wrapper)
        except ApiException as exc:
            # Non-2xx status codes lead to an exception from the OpenAPI client.
            logger.error("Failed to create CBRAIN task (HTTP exception): %s", exc)
            raise CbrainTaskError(f"Could not create CBRAIN task: {exc}") from exc

        status_code = getattr(raw, "status", None) or getattr(raw, "status_code", None)

        try:
            data = json.loads(raw.data)
        except json.JSONDecodeError as err:
            raise CbrainTaskError("Invalid JSON in CBRAIN response") from err

        # Any explicit error key from CBRAIN counts as a failure even if the
        # HTTP code is superficially *200 OK*.
        if isinstance(data, dict) and ("errors" in data or "error" in data):
            err_msg = data.get("errors") or data.get("error")
            raise CbrainTaskError(f"CBRAIN API returned an error: {err_msg}")

        if status_code is not None and status_code >= 400:
            err_text = _stringify_api_error(data)
            raise CbrainTaskError(
                f"CBRAIN API HTTP {status_code}: {err_text}"
            )

        return data
