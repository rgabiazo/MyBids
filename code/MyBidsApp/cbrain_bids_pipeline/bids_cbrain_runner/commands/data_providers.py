"""
Helpers for the **CBRAIN** ``/data_providers`` API endpoints.

These thin wrappers simplify the most common interactions—listing
providers, browsing their file trees, and registering new files—so the
rest of the CLI does not repeat HTTP boilerplate.
"""

from __future__ import annotations
from typing import List
from ..api.client import cbrain_get, cbrain_post


def list_data_providers(
    base_url: str, token: str, *, timeout: float | None = None
) -> None:
    """Print every Data Provider accessible to the authenticated account.

    Args:
        base_url: Base CBRAIN portal URL, e.g. ``"https://portal.cbrain.mcgill.ca"``.
        token:    Valid ``cbrain_api_token`` with *read* access.

    Returns:
        ``None``.  Results are sent to ``stdout`` for immediate inspection.
    """
    resp = cbrain_get(base_url, "data_providers", token, timeout=timeout)
    if resp.status_code != 200:
        print("Could not list data providers:", resp.status_code, resp.text)
        return

    try:
        dps: List[dict] = resp.json()
    except Exception:  # JSON parsing failure
        print("Response could not be parsed as JSON:", resp.text)
        return

    print("Accessible data providers:")
    for dp in dps:
        print(f" - ID: {dp['id']}, Name: {dp['name']}")


def browse_provider(
    base_url: str,
    token: str,
    provider_id: int,
    path: str | None = None,
    *,
    timeout: float | None = None,
) -> List[dict]:
    """List the contents of a Data Provider path (similar to ``ls``).

    Args:
        base_url:    CBRAIN base URL.
        token:       API token.
        provider_id: Numeric Data Provider ID.
        path:        Optional sub-directory on the provider.  If ``None``,
                     the provider root is listed.

    Returns:
        A list of **FileInfo** dictionaries.  If an error occurs, an empty
        list is returned and a message is printed to ``stderr``-level
        output.
    """
    endpoint = f"data_providers/{provider_id}/browse"
    params: dict = {}
    if path:
        params["browse_path"] = path

    resp = cbrain_get(base_url, endpoint, token, params=params, timeout=timeout)
    if resp.status_code != 200:
        print(f"[ERROR] Could not browse provider {provider_id}: "
              f"{resp.status_code} {resp.text}")
        return []

    try:
        return resp.json()
    except Exception:
        print("[ERROR] Could not parse JSON from browse endpoint:", resp.text)
        return []


def register_files_on_provider(
    base_url: str,
    token: str,
    provider_id: int,
    basenames: List[str],
    types: List[str],
    browse_path: str | None = None,
    as_user_id: int | None = None,
    other_group_id: int | None = None,
    *,
    timeout: float | None = None,
) -> None:
    """Register new files as CBRAIN *Userfiles* on a Data Provider.

    Args:
        base_url:      CBRAIN base URL.
        token:         API token.
        provider_id:   Numeric Data Provider ID.
        basenames:     List of file or directory names on the provider.
        types:         List of CBRAIN short file-type names (e.g. ``"BidsSubject"``).
        browse_path:   Remote sub-directory containing the *basenames*.
        as_user_id:    Admin-only override to register files on behalf of another account.
        other_group_id:Project (group) ID to associate with the new Userfiles.

    Raises:
        ValueError: If *basenames* and *types* length mismatch.

    Notes:
        * CBRAIN expects the ``filetypes`` parameter in the form
          ``"<Type>-<basename>"`` for each file being registered.
        * The function prints summaries of newly and previously registered
          userfiles for easy verification.
    """
    if len(basenames) != len(types):
        raise ValueError("Number of basenames and filetypes must match.")

    # Construct the combined strings required by the CBRAIN API.
    combined_filetypes = [f"{ft}-{bn}" for ft, bn in zip(types, basenames)]

    payload: dict = {
        "basenames": basenames,
        "filetypes": combined_filetypes,
    }
    if browse_path:
        payload["browse_path"] = browse_path
    if as_user_id is not None:
        payload["as_user_id"] = as_user_id
    if other_group_id is not None:
        payload["other_group_id"] = other_group_id

    endpoint = f"data_providers/{provider_id}/register"
    resp = cbrain_post(base_url, endpoint, token, json=payload, timeout=timeout)

    if resp.status_code != 200:
        print(f"[ERROR] Could not register files on provider {provider_id}: "
              f"{resp.status_code} {resp.text}")
        return

    data = resp.json()  # *RegistrationInfo* object
    newly = data.get("newly_registered_userfiles", [])
    prev  = data.get("previously_registered_userfiles", [])
    notice = data.get("notice", "")

    print(f"[SUCCESS] Files registered on provider {provider_id}")
    if notice:
        print("NOTICE:", notice)
    if newly:
        print("Newly registered userfiles:")
        for uf in newly:
            print(f" - ID={uf['id']}, name={uf['name']}, type={uf['type']}")
    if prev:
        print("Previously registered (already in CBRAIN):")
        for uf in prev:
            print(f" - ID={uf['id']}, name={uf['name']}, type={uf['type']}")
