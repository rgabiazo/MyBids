"""

Command-line interface (CLI) entry point for interacting with CBRAIN and
managing BIDS-formatted datasets.

This module defines **only** the CLI front-end; the implementation logic
lives in dedicated submodules (e.g., ``commands.*``).  Keeping the parsing
layer thin reduces cognitive load and helps unit-testing individual command
handlers in isolation.

The CLI follows these conventions:

* One top-level ``argparse.ArgumentParser`` with *flat* flag names so that
  shell completion remains simple (e.g., ``--list-groups`` rather than a
  nested sub-parser hierarchy).
* A single ``main()`` entry point that is exposed via
  ``console_scripts`` in ``setup.py``.
* All console logging is delegated to helper functions that accept a
  ``logging.Logger`` instance; the CLI only configures global log level
  and formatting.

The module refrains from mutating global state except for logging
configuration and reading environment variables required for authentication.
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict

import requests
import yaml

from bids_cbrain_runner import __version__
from bids_cbrain_runner.commands.download import download_tool_outputs
from bids_cbrain_runner.utils.logging_config import setup_logging

from .api.client_openapi import CbrainClient
from .api.config_loaders import (
    get_sftp_provider_config,
    load_cbrain_config,
    load_tools_config,
)
from .api.session import CBRAINAuthError, ensure_token
from .commands.bids_sftp_checker import (
    check_bids_and_sftp_files,
    check_bids_and_sftp_files_with_group,
)
from .commands.bids_validator import bids_validator_cli

# ---------------------------------------------------------------------
# Command handlers: imported only for their side-effects (registering
# functions) or for direct invocation by this file.
# ---------------------------------------------------------------------
from .commands.data_providers import (
    browse_provider,
    list_data_providers,
    register_files_on_provider,
)
from .commands.groups import (
    create_group,
    describe_group,
    describe_group_userfiles,
    list_groups,
    resolve_group_id,
)
from .commands.sftp import sftp_cd_steps, sftp_cd_steps_with_group
from .commands.tool_launcher import (
    launch_tool,
    launch_tool_batch_for_group,
)
from .commands.tools import (
    describe_tool_config_and_server,
    fetch_boutiques_descriptor,
    list_bourreaus,
    list_execution_servers,
    list_tool_bourreaus_for_tool,
    list_tool_configs,
    list_tools,
    show_group_tasks_status,
    show_task_status,
    test_openapi_tools,
)
from .commands.upload import upload_bids_and_sftp_files
from .commands.userfiles import (
    delete_userfile,
    delete_userfiles_by_group_and_type,
    describe_userfile,
    find_userfile_id_by_name_and_provider,
    list_userfiles,
    list_userfiles_by_group,
    list_userfiles_by_group_and_provider,
    list_userfiles_by_provider,
    update_userfile_group_and_move,
)
from .utils.cli_utils import parse_kv_pair
from .utils.progress import run_with_spinner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------
def main() -> None:
    """Entry point for the ``cbrain-cli`` command (also available as ``bids-cbrain-cli``).

    The function builds an :class:`argparse.ArgumentParser`, parses the
    command-line flags, performs authentication (token refresh if requested),
    merges run-time configuration and dispatches to the corresponding command
    handler.

    The CLI supports four broad task categories:

    1. **Data providers and userfiles** – CRUD operations on SFTP or CBRAIN
       resources.
    2. **BIDS validation and comparison** – Validate dataset integrity and
       compare local vs. remote file structures.
    3. **CBRAIN tool operations** – List or launch CBRAIN tools and monitor
       task status.
    4. **Download / upload helpers** – Synchronise derivative outputs.

    Args:
        None – arguments are read from :pydata:`sys.argv`.

    Returns:
        None.  The function exits the process with ``sys.exit`` on fatal
        errors or after executing terminal commands that naturally terminate
        the program (e.g., download sub-command).

    Raises:
        SystemExit: propagated from ``argparse`` or explicit ``sys.exit``.
    """
    # -----------------------------------------------------------------
    # Argument parser definition
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="CLI for interacting with CBRAIN via Python",
        allow_abbrev=False,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Sub-parsers (only used for *download*, to keep backwards compatibility
    # with legacy flat flags while allowing positional arguments specific to
    # that sub-command).
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available sub-commands",
    )


    # -----------------------------------------------------------------
    # Argument groups
    # -----------------------------------------------------------------
    global_grp = parser.add_argument_group("global")
    dp_grp = parser.add_argument_group("data provider")
    group_grp = parser.add_argument_group("group")
    userfile_grp = parser.add_argument_group("userfile")
    sftp_grp = parser.add_argument_group("sftp")
    validation_grp = parser.add_argument_group("validation")
    file_reg_grp = parser.add_argument_group("file registration")
    upload_grp = parser.add_argument_group("upload")
    tool_list_grp = parser.add_argument_group("tool listing")
    tool_launch_grp = parser.add_argument_group("tool launch")

    # -----------------------------------------------------------------
    # Global flags
    # -----------------------------------------------------------------
    global_grp.add_argument(
        "--refresh-token",
        action="store_true",
        help="Ignore the cached token and force a fresh CBRAIN login session.",
    )
    global_grp.add_argument(
        "--debug-logs",
        action="store_true",
        help="Increase console verbosity to DEBUG.",
    )
    global_grp.add_argument(
        "--per-page",
        type=int,
        metavar="N",
        default=100,
        help="Pagination size for list endpoints.",
    )
    global_grp.add_argument(
        "--timeout",
        type=float,
        metavar="SEC",
        help=(
            "HTTP request timeout in seconds. Overrides the CBRAIN_TIMEOUT "
            "environment variable."
        ),
    )

    # -----------------------------------------------------------------
    # Data provider flags
    # -----------------------------------------------------------------
    dp_grp.add_argument("--list-dps", action="store_true", help="List data providers.")
    dp_grp.add_argument(
        "--browse-provider",
        type=int,
        metavar="PROVIDER_ID",
        help="Browse files on a Data Provider by numeric ID.",
    )
    dp_grp.add_argument(
        "--browse-path",
        type=str,
        metavar="PATH",
        default=None,
        help="Sub-directory path used with --browse-provider.",
    )

    # -----------------------------------------------------------------
    # Group flags
    # -----------------------------------------------------------------
    group_grp.add_argument("--list-groups", action="store_true", help="List groups.")
    group_grp.add_argument(
        "--describe-group",
        type=str,
        metavar="GROUP",
        help="Describe a single group by ID or name.",
    )
    group_grp.add_argument(
        "--describe-group-userfiles",
        type=str,
        metavar="GROUP",
        help="List userfiles belonging to a group (ID or name).",
    )
    group_grp.add_argument(
        "--create-group",
        metavar="NAME",
        dest="create_group",
        type=str,
        help="Create a new group (project) with NAME.",
    )
    group_grp.add_argument(
        "--group-description",
        dest="group_description",
        type=str,
        metavar="DESC",
        help="Optional description used with --create-group.",
    )

    # -----------------------------------------------------------------
    # Userfile flags
    # -----------------------------------------------------------------
    userfile_grp.add_argument("--list-userfiles", action="store_true", help="List userfiles.")
    userfile_grp.add_argument(
        "--list-userfiles-provider",
        type=int,
        metavar="PROVIDER_ID",
        help="Filter userfiles by provider ID.",
    )
    userfile_grp.add_argument(
        "--list-userfiles-group",
        type=str,
        metavar="GROUP",
        help="Filter userfiles by group ID or name.",
    )
    userfile_grp.add_argument(
        "--group-and-provider",
        nargs=2,
        type=str,
        metavar=("GROUP", "PROVIDER"),
        help="List userfiles that match BOTH <group> and <provider_id>.",
    )
    userfile_grp.add_argument(
        "--describe-userfile",
        type=int,
        metavar="USERFILE_ID",
        help="Describe a single userfile by numeric ID.",
    )
    userfile_grp.add_argument(
        "--delete-userfile",
        type=int,
        metavar="USERFILE_ID",
        help="Delete a userfile by numeric ID.",
    )
    userfile_grp.add_argument(
        "--delete-group",
        dest="delete_group",
        type=str,
        metavar="GROUP",
        help="Project (group) ID or name for deletion.",
    )
    userfile_grp.add_argument(
        "--delete-filetype",
        dest="delete_filetype",
        nargs="+",
        help="Filetype(s) to delete within --delete-group.",
    )
    userfile_grp.add_argument(
        "--delete-group-filetype",
        dest="delete_group_filetype",
        nargs=2,
        metavar=("GROUP", "TYPE"),
        help=argparse.SUPPRESS,
    )
    userfile_grp.add_argument(
        "--dry-delete",
        action="store_true",
        help="Show deletion actions without removing files.",
    )

    # -----------------------------------------------------------------
    # SFTP flags
    # -----------------------------------------------------------------
    sftp_grp.add_argument(
        "--sftp-steps",
        nargs="*",
        help="Perform an SFTP sequence of wildcard steps.",
    )
    sftp_grp.add_argument(
        "--sftp-provider",
        type=str,
        metavar="PROVIDER",
        default="sftp_1",
        help="Which provider from servers.yaml to use for SFTP.",
    )
    sftp_grp.add_argument(
        "--sftp-username",
        type=str,
        metavar="USERNAME",
        help="Override SFTP username (rarely needed).",
    )
    sftp_grp.add_argument(
        "--sftp-password",
        type=str,
        metavar="PASSWORD",
        help="Override SFTP password (rarely needed).",
    )
    sftp_grp.add_argument(
        "--sftp-group-steps",
        nargs="+",
        help="First arg is <group_id>, subsequent wildcard steps "
        "(e.g., sub-* ses-* anat).",
    )

    # -----------------------------------------------------------------
    # BIDS validation
    # -----------------------------------------------------------------
    validation_grp.add_argument(
        "--bids-validator",
        nargs="*",
        help="Validate local BIDS dataset using the Node-based bids-validator.",
    )

    # -----------------------------------------------------------------
    # BIDS + SFTP comparison
    # -----------------------------------------------------------------
    validation_grp.add_argument(
        "--check-bids-and-sftp-files",
        nargs="*",
        help="Compare local BIDS files with those on SFTP.",
    )
    validation_grp.add_argument(
        "--check-bids-sftp-group",
        nargs="+",
        help="Same as --check-bids-and-sftp-files, "
        "but restrict to userfiles in a specific CBRAIN group.",
    )

    # -----------------------------------------------------------------
    # File registration / modification
    # -----------------------------------------------------------------
    file_reg_grp.add_argument(
        "--register-files",
        action="store_true",
        help="Register existing files from a provider into CBRAIN.",
    )
    file_reg_grp.add_argument(
        "--dp-id",
        type=int,
        metavar="PROVIDER_ID",
        help="Data Provider ID.",
    )
    file_reg_grp.add_argument(
        "--basenames",
        nargs="+",
        help="Basenames on the provider (e.g., sub-XXX).",
    )
    file_reg_grp.add_argument(
        "--filetypes",
        nargs="+",
        help="CBRAIN filetypes (e.g., BidsSubject).",
    )
    file_reg_grp.add_argument(
        "--as-user-id",
        type=int,
        metavar="USER_ID",
        default=None,
        help="Admin-only: register files as another user.",
    )
    file_reg_grp.add_argument(
        "--other-group-id",
        type=int,
        metavar="GROUP_ID",
        default=None,
        help="Project (group) ID for newly registered files.",
    )
    file_reg_grp.add_argument(
        "--find-userfile-id",
        action="store_true",
        help="Lookup a userfile ID by name and provider.",
    )
    file_reg_grp.add_argument(
        "--uf-filename",
        type=str,
        metavar="FILENAME",
        help="Name field of the userfile (e.g., sub-001).",
    )
    file_reg_grp.add_argument(
        "--uf-provider",
        type=int,
        metavar="PROVIDER_ID",
        help="Provider ID associated with that userfile.",
    )
    file_reg_grp.add_argument(
        "--modify-file",
        action="store_true",
        help="Update a userfile’s group or move it to another provider.",
    )
    file_reg_grp.add_argument(
        "--userfile-id",
        type=int,
        metavar="USERFILE_ID",
        help="Numeric userfile ID.",
    )
    file_reg_grp.add_argument(
        "--new-group-id",
        type=str,
        metavar="GROUP",
        help="New group ID or name.",
    )
    file_reg_grp.add_argument(
        "--move-to-provider",
        type=int,
        metavar="PROVIDER_ID",
        help="Move userfile to another provider ID.",
    )

    # -----------------------------------------------------------------
    # Upload helpers
    # -----------------------------------------------------------------
    upload_grp.add_argument(
        "--upload-bids-and-sftp-files",
        nargs="*",
        help="Validate BIDS, compare local vs. remote, "
        "upload missing files to SFTP.",
    )
    upload_grp.add_argument(
        "--upload-register",
        action="store_true",
        help="Register files after upload.",
    )
    upload_grp.add_argument(
        "--upload-dp-id",
        type=int,
        metavar="PROVIDER_ID",
        help="Provider ID for upload.",
    )
    upload_grp.add_argument(
        "--upload-filetypes",
        nargs="+",
        help="Filetypes for each top-level folder.",
    )
    upload_grp.add_argument(
        "--upload-group-id",
        type=str,
        metavar="GROUP",
        help="Project ID or name for upload.",
    )
    upload_grp.add_argument(
        "--upload-move-provider",
        type=int,
        metavar="PROVIDER_ID",
        help="Move newly registered userfiles to this provider.",
    )

    # -----------------------------------------------------------------
    # Tool listing / metadata
    # -----------------------------------------------------------------
    tool_list_grp.add_argument(
        "--list-tool-configs",
        action="store_true",
        help="List CBRAIN tool configurations.",
    )
    tool_list_grp.add_argument("--list-tools", action="store_true", help="List CBRAIN tools.")
    tool_list_grp.add_argument(
        "--fetch-boutiques-descriptor",
        type=int,
        metavar="CONFIG_ID",
        help="Fetch the Boutiques descriptor for a tool config ID.",
    )
    tool_list_grp.add_argument(
        "--list-exec-servers",
        action="store_true",
        help="List CBRAIN execution servers.",
    )
    tool_list_grp.add_argument(
        "--list-bourreaus",
        action="store_true",
        help="List bourreau (HPC) IDs from tool configurations.",
    )
    tool_list_grp.add_argument(
        "--list-tool-bourreaus",
        metavar="TOOL_NAME",
        type=str,
        help="List bourreau IDs for a given tool.",
    )
    tool_list_grp.add_argument(
        "--describe-tool-config-server",
        nargs=2,
        type=int,
        metavar=("CONFIG_ID", "BOURREAU_ID"),
        help="Show server name and tool version for a given config and bourreau.",
    )
    tool_list_grp.add_argument(
        "--test-openapi-tools",
        action="store_true",
        help="Verify that the OpenAPI /tools endpoint works.",
    )

    # -----------------------------------------------------------------
    # Tool launch flags
    # -----------------------------------------------------------------
    tool_launch_grp.add_argument(
        "--launch-tool",
        type=str,
        metavar="TOOL_NAME",
        help="Launch any CBRAIN tool by name (e.g., hippunfold).",
    )
    tool_launch_grp.add_argument(
        "--tool-param",
        action="append",
        type=parse_kv_pair,
        metavar="KEY=VALUE",
        help="Override a tool parameter (Python literal syntax).",
    )
    tool_launch_grp.add_argument(
        "--override-tool-config-id",
        type=int,
        metavar="CONFIG_ID",
        help="Force a specific numeric tool_config_id.",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-results-dp-id",
        "--results-dp-id",
        dest="launch_tool_results_dp_id",
        type=int,
        metavar="PROVIDER_ID",
        help="Provider ID for tool results.",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-bourreau-id",
        "--launch-tool-bourreau",
        dest="launch_tool_bourreau_id",
        type=int,
        metavar="BOURREAU_ID",
        help="Bourreau (HPC) ID for tool execution.",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-dry-run",
        action="store_true",
        help="Print payload instead of creating a task.",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-group-id",
        "--group-id",
        dest="launch_tool_group_id",
        type=str,
        metavar="GROUP",
        help="CBRAIN project ID or name for the task.",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-batch-group",
        dest="launch_tool_batch_group",
        type=str,
        metavar="GROUP",
        help="Launch one task per userfile in this project (ID or name).",
    )
    tool_launch_grp.add_argument(
        "--launch-tool-batch-type",
        dest="launch_tool_batch_type",
        type=str,
        metavar="TYPE",
        help="Restrict batch launch to userfiles of this type.",
    )

    # -----------------------------------------------------------------
    # Task status
    # -----------------------------------------------------------------
    parser.add_argument(
        "--task-status",
        type=str,
        metavar="IDENT",
        help=(
            "Task ID or project name/ID. When a project is given, all its "
            "tasks are listed."
        ),
    )
    parser.add_argument(
        "--task-type",
        type=str,
        metavar="TYPE",
        help="Optional tool type filter used with --task-status on a project.",
    )

    # -----------------------------------------------------------------
    # Download sub-command (uses sub-parser for clarity)
    # -----------------------------------------------------------------
    dl = subparsers.add_parser(
        "download",
        help="Download CBRAIN tool outputs (e.g., hippunfold, recon-all).",
        allow_abbrev=False,
    )
    dl.add_argument(
        "--tool",
        required=True,
        help="Name of the tool whose outputs to fetch.",
    )
    dl.add_argument(
        "--output-type",
        dest="output_type",
        type=str,
        metavar="TYPE",
        help="Override the CBRAIN userfile type (if required).",
    )
    dl.add_argument(
        "--id",
        type=int,
        dest="userfile_id",
        metavar="USERFILE_ID",
        help="Download a single CBRAIN userfile by ID.",
    )
    dl.add_argument(
        "--group",
        type=str,
        dest="group_id",
        metavar="GROUP",
        help="Download all userfile outputs belonging to this project (ID or name).",
    )
    dl.add_argument(
        "--config",
        type=str,
        dest="local_config_path",
        metavar="PATH",
        help="Path to config.yaml for output directories and metadata.",
    )
    dl.add_argument(
        "--flatten",
        action="store_true",
        help="Flatten the output directory structure.",
    )
    dl.add_argument(
        "--skip-dirs",
        nargs="+",
        default=[],
        help="Top-level directories to skip (e.g., config logs).",
    )
    dl.add_argument(
        "--force",
        "--force-download",
        dest="force_download",
        action="store_true",
        help="Overwrite existing files.",
    )
    dl.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files.",
    )
    dl.set_defaults(func=download_tool_outputs)

    # Parse command-line arguments
    args = parser.parse_args()

    # Backwards compatibility for deprecated --delete-group-filetype
    if args.delete_group_filetype and not (args.delete_group or args.delete_filetype):
        args.delete_group = args.delete_group_filetype[0]
        args.delete_filetype = [args.delete_group_filetype[1]]

    # -----------------------------------------------------------------
    # Authentication and configuration
    # -----------------------------------------------------------------
    if args.refresh_token:
        # Purge cached token before loading configuration so that
        # ``ensure_token`` performs a fresh login.
        os.environ.pop("CBRAIN_API_TOKEN", None)
        cfg_path = os.path.join(
            os.path.dirname(__file__),
            "api",
            "config",
            "cbrain.yaml",
        )
        try:
            with open(cfg_path) as fh:
                stored = yaml.safe_load(fh) or {}
            stored.pop("cbrain_api_token", None)
            with open(cfg_path, "w") as fh:
                yaml.safe_dump(stored, fh)
        except Exception:
            # Swallow errors silently—token will be refreshed anyway.
            pass

    # Configure root logger after potential --debug-logs flag is known.
    setup_logging(verbose=args.debug_logs)

    # Load SFTP provider, CBRAIN user settings, and tool metadata.
    sftp_cfg: Dict[str, Any] = get_sftp_provider_config(provider_name=args.sftp_provider)
    user_cfg: Dict[str, Any] = load_cbrain_config()
    tools_cfg: Dict[str, Any] = load_tools_config()

    # Path where authentication token is persisted on disk.
    cfg_path = os.path.join(os.path.dirname(__file__), "api", "config", "cbrain.yaml")

    # Retrieve or refresh token.
    try:
        auth_cfg = ensure_token(
            base_url=sftp_cfg.get("cbrain_base_url", "https://portal.cbrain.mcgill.ca"),
            cfg_path=cfg_path,
            cfg=user_cfg,
            force_refresh=args.refresh_token,
            timeout=args.timeout,
        )
    except CBRAINAuthError as err:
        logger.error("Authentication failed – %s", err)
        sys.exit(1)
    except requests.exceptions.HTTPError as err:
        logger.error("CBRAIN server replied with an HTTP error: %s", err)
        sys.exit(1)
    except requests.exceptions.RequestException as err:
        logger.error("Network problem while contacting CBRAIN: %s", err)
        sys.exit(1)

    base_url: str = auth_cfg["cbrain_base_url"]
    token: str = auth_cfg["cbrain_api_token"]
    cfg: Dict[str, Any] = {**sftp_cfg, **auth_cfg}

    # -----------------------------------------------------------------
    # Command dispatch (flat flags evaluated in order of appearance
    # in the source file for readability).
    # -----------------------------------------------------------------
    # Data provider operations
    if args.list_dps:
        list_data_providers(base_url, token)

    if args.browse_provider:
        listing = browse_provider(
            base_url, token, args.browse_provider, args.browse_path
        )
        print(f"Raw listing from provider={args.browse_provider}:")
        for fi in listing:
            print(f" - {fi['name']}  {fi['size']} bytes")

    # Group operations
    if args.list_groups:
        grps = list_groups(
            base_url, token, per_page=args.per_page, timeout=args.timeout
        )
        if not isinstance(grps, list):
            grps = []
        print(f"Found {len(grps)} groups:")
        for g in grps:
            print(f" - ID={g['id']} name={g['name']} desc={g.get('description','')}")

    if args.describe_group:
        gid = resolve_group_id(
            base_url,
            token,
            args.describe_group,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None:
            print(f"Group '{args.describe_group}' not found")
            sys.exit(1)
        describe_group(base_url, token, gid)

    if args.describe_group_userfiles:
        gid = resolve_group_id(
            base_url,
            token,
            args.describe_group_userfiles,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None:
            print(f"Group '{args.describe_group_userfiles}' not found")
            sys.exit(1)
        ufs = describe_group_userfiles(
            base_url, token, gid, timeout=args.timeout
        )
        print(f"Found {len(ufs)} userfile(s) in group {gid}:")
        for uf in ufs:
            print(
                f" - ID={uf['id']}  name={uf['name']}  "
                f"type={uf['type']} provider={uf.get('data_provider_id')}"
            )

    if args.create_group:
        created = create_group(
            base_url,
            token,
            args.create_group,
            description=args.group_description,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if created is None:
            sys.exit(1)
        print(
            f"Created group ID={created['id']} name={created['name']}"
        )

    # Userfile listing / description
    if args.list_userfiles:
        client = CbrainClient(base_url, token)
        files = run_with_spinner(
            lambda: list_userfiles(client, per_page=args.per_page),
            "Retrieving userfiles",
            show=not args.debug_logs,
        )
        print(f"Found {len(files)} userfile(s).")
        for uf in files:
            print(f" - ID={uf['id']} {uf['name']} provider={uf['data_provider_id']}")

    if args.list_userfiles_provider:
        client = CbrainClient(base_url, token)
        tmp = run_with_spinner(
            lambda: list_userfiles_by_provider(
                client,
                args.list_userfiles_provider,
                per_page=args.per_page,
                timeout=args.timeout,
            ),
            "Retrieving userfiles",
            show=not args.debug_logs,
        )

        print(f"Found {len(tmp)} userfile(s) on provider {args.list_userfiles_provider}.")
        for uf in tmp:
            print(
                f" - ID={uf['id']}  name={uf['name']}  type={uf['type']} group={uf['group_id']}"
            )

    if args.list_userfiles_group:
        gid = resolve_group_id(
            base_url,
            token,
            args.list_userfiles_group,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None:
            print(f"Group '{args.list_userfiles_group}' not found")
            sys.exit(1)
        client = CbrainClient(base_url, token)
        tmp = run_with_spinner(
            lambda: list_userfiles_by_group(
                client,
                gid,
                per_page=args.per_page,
                timeout=args.timeout,
            ),
            "Retrieving userfiles",
            show=not args.debug_logs,
        )
        print(
            f"Found {len(tmp)} userfile(s) in group {args.list_userfiles_group}."
        )
        for uf in tmp:
            print(
                f" - ID={uf['id']}  name={uf['name']}  "
                f"type={uf['type']} provider={uf.get('data_provider_id')}"
            )

    if args.group_and_provider:
        gid_str, pid_str = args.group_and_provider
        gid = resolve_group_id(
            base_url, token, gid_str, per_page=args.per_page, timeout=args.timeout
        )
        if gid is None:
            print(f"Group '{gid_str}' not found")
            sys.exit(1)
        pid = int(pid_str)
        client = CbrainClient(base_url, token)
        tmp = run_with_spinner(
            lambda: list_userfiles_by_group_and_provider(
                client,
                gid,
                pid,
                per_page=args.per_page,
                timeout=args.timeout,
            ),
            "Retrieving userfiles",
            show=not args.debug_logs,
        )
        print(
            f"Found {len(tmp)} userfile(s) in group {gid_str} on provider {pid}."
        )
        for uf in tmp:
            print(
                f" - ID={uf['id']}  name={uf['name']}  "
                f"type={uf['type']} provider={uf.get('data_provider_id')}"
            )

    if args.describe_userfile:
        client = CbrainClient(base_url, token)
        describe_userfile(client, args.describe_userfile, timeout=args.timeout)

    if args.delete_userfile:
        client = CbrainClient(base_url, token)
        delete_userfile(
            client,
            args.delete_userfile,
            dry_run=args.dry_delete,
            timeout=args.timeout,
        )

    if args.delete_group and args.delete_filetype:
        gid = resolve_group_id(
            base_url,
            token,
            args.delete_group,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None:
            print(f"Group '{args.delete_group}' not found")
            sys.exit(1)
        client = CbrainClient(base_url, token)
        delete_userfiles_by_group_and_type(
            client,
            gid,
            args.delete_filetype,
            per_page=args.per_page,
            dry_run=args.dry_delete,
            timeout=args.timeout,
        )

    # SFTP browsing helpers
    if args.sftp_steps:
        sftp_cd_steps(cfg, args.sftp_steps)

    if args.sftp_group_steps:
        try:
            group_id = int(args.sftp_group_steps[0])
            steps = args.sftp_group_steps[1:]
        except (ValueError, IndexError):
            print("[ERROR] --sftp-group-steps requires <group_id> plus patterns.")
            sys.exit(1)
        sftp_cd_steps_with_group(cfg, base_url, token, group_id, steps)

    # BIDS validation and comparison
    if args.bids_validator:
        bids_validator_cli(args.bids_validator)

    if args.check_bids_and_sftp_files:
        check_bids_and_sftp_files(cfg, args.check_bids_and_sftp_files)

    if args.check_bids_sftp_group:
        try:
            group_id = int(args.check_bids_sftp_group[0])
            steps = args.check_bids_sftp_group[1:]
        except (ValueError, IndexError):
            print("[ERROR] --check-bids-sftp-group requires <group_id> plus "
                  "wildcard steps.")
            sys.exit(1)
        check_bids_and_sftp_files_with_group(
            cfg, base_url, token, group_id, steps
        )

    # Registration / modification helpers
    if args.register_files:
        if not args.dp_id or not args.basenames or not args.filetypes:
            print("[ERROR] For --register-files, provide --dp-id, --basenames "
                  "and --filetypes.")
            sys.exit(1)
        if len(args.basenames) != len(args.filetypes):
            print("[ERROR] The number of basenames must match filetypes.")
            sys.exit(1)
        register_files_on_provider(
            base_url,
            token,
            args.dp_id,
            args.basenames,
            args.filetypes,
            browse_path=args.browse_path,
            as_user_id=args.as_user_id,
            other_group_id=args.other_group_id,
            timeout=args.timeout,
        )

    if args.find_userfile_id:
        if not args.uf_filename or not args.uf_provider:
            print("[ERROR] Require --uf-filename and --uf-provider.")
            sys.exit(1)
        client = CbrainClient(base_url, token)
        ufid = find_userfile_id_by_name_and_provider(
            client,
            args.uf_filename,
            args.uf_provider,
            timeout=args.timeout,
        )
        print("Userfile found: ID" if ufid is not None else "Not found.", ufid)

    if args.modify_file:
        if not args.userfile_id:
            print("[ERROR] Need --userfile-id for --modify-file.")
            sys.exit(1)
        if (args.new_group_id is None) and (args.move_to_provider is None):
            print("[ERROR] Specify --new-group-id or --move-to-provider.")
            sys.exit(1)

        gid = resolve_group_id(
            base_url,
            token,
            args.new_group_id,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None and args.new_group_id is not None:
            print(f"Group '{args.new_group_id}' not found")
            sys.exit(1)

        update_userfile_group_and_move(
            base_url,
            token,
            args.userfile_id,
            new_group_id=gid,
            new_provider_id=args.move_to_provider,
            timeout=args.timeout,
        )

    # Upload helper
    if args.upload_bids_and_sftp_files:
        gid = resolve_group_id(
            base_url,
            token,
            args.upload_group_id,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is None and args.upload_group_id is not None:
            print(f"Group '{args.upload_group_id}' not found")
            sys.exit(1)
        upload_bids_and_sftp_files(
            cfg,
            base_url,
            token,
            args.upload_bids_and_sftp_files,
            do_register=args.upload_register,
            dp_id=args.upload_dp_id,
            filetypes=args.upload_filetypes,
            group_id=gid,
            move_provider=args.upload_move_provider,
            timeout=args.timeout,
        )

    # Tool metadata operations
    if args.list_tool_configs:
        list_tool_configs(base_url, token)

    if args.list_tools:
        list_tools(base_url, token)

    if args.list_exec_servers:
        list_execution_servers(base_url, token)
        sys.exit(0)

    if args.describe_tool_config_server:
        cfg_id, bourreau_id = args.describe_tool_config_server
        describe_tool_config_and_server(base_url, token, cfg_id, bourreau_id)
        sys.exit(0)

    if args.list_bourreaus:
        list_bourreaus(base_url, token)

    if args.list_tool_bourreaus:
        list_tool_bourreaus_for_tool(
            base_url=base_url,
            token=token,
            tool_name=args.list_tool_bourreaus,
        )
        sys.exit(0)

    if args.test_openapi_tools:
        test_openapi_tools(base_url, token)

    if args.fetch_boutiques_descriptor:
        fetch_boutiques_descriptor(base_url, token, args.fetch_boutiques_descriptor)

    # Task status lookup
    if args.task_status:
        gid = resolve_group_id(
            base_url,
            token,
            args.task_status,
            per_page=args.per_page,
            timeout=args.timeout,
        )
        if gid is not None:
            show_group_tasks_status(
                base_url,
                token,
                gid,
                task_type=args.task_type,
                per_page=args.per_page,
                timeout=args.timeout,
            )
        else:
            try:
                tid = int(args.task_status)
            except (TypeError, ValueError):
                print(f"[ERROR] Invalid task identifier '{args.task_status}'")
                sys.exit(1)
            show_task_status(base_url, token, tid)

    # Tool launch (single or batch)
    if args.launch_tool:
        extra_params: Dict[str, Any] = dict(args.tool_param or [])

        if args.launch_tool_batch_group:
            batch_gid = resolve_group_id(
                base_url,
                token,
                args.launch_tool_batch_group,
                per_page=args.per_page,
                timeout=args.timeout,
            )
            if batch_gid is None:
                print(f"Group '{args.launch_tool_batch_group}' not found")
                sys.exit(1)
            # ``launch_tool_batch_for_group`` logs progress for each user-file.
            # Running it inside ``run_with_spinner`` interleaves log messages
            # with the spinner characters leaving stray output on the console.
            # Execute the helper directly to keep the log lines tidy.
            launch_tool_batch_for_group(
                base_url=base_url,
                token=token,
                tools_cfg=tools_cfg,
                tool_name=args.launch_tool,
                group_id=batch_gid,
                batch_type=args.launch_tool_batch_type,
                extra_params=extra_params,
                results_dp_id=args.launch_tool_results_dp_id,
                bourreau_id=args.launch_tool_bourreau_id,
                override_tool_config_id=args.override_tool_config_id,
                dry_run=args.launch_tool_dry_run,
            )
        else:
            single_gid = resolve_group_id(
                base_url,
                token,
                args.launch_tool_group_id,
                per_page=args.per_page,
                timeout=args.timeout,
            )
            if single_gid is None:
                print(f"Group '{args.launch_tool_group_id}' not found")
                sys.exit(1)
            # ``launch_tool`` emits its own INFO messages.  Avoid wrapping it in
            # ``run_with_spinner`` to prevent console artefacts caused by the
            # spinner thread overwriting log output.
            launch_tool(
                base_url=base_url,
                token=token,
                tools_cfg=tools_cfg,
                tool_name=args.launch_tool,
                extra_params=extra_params,
                group_id=single_gid,
                results_dp_id=args.launch_tool_results_dp_id,
                bourreau_id=args.launch_tool_bourreau_id,
                override_tool_config_id=args.override_tool_config_id,
                dry_run=args.launch_tool_dry_run,
            )

        sys.exit(0)

    # Download sub-command dispatch
    if args.command == "download":
        # Merge runtime configuration and pass through.
        full_cfg = {**sftp_cfg, **user_cfg, "local_config_path": args.local_config_path}
        try:
            gid = None
            if args.group_id is not None:
                gid = resolve_group_id(
                    base_url,
                    token,
                    args.group_id,
                    per_page=args.per_page,
                    timeout=args.timeout,
                )
                if gid is None:
                    print(f"Group '{args.group_id}' not found")
                    sys.exit(1)
            args.func(
                base_url=base_url,
                token=token,
                cfg=full_cfg,
                tool_name=args.tool,
                output_type=args.output_type,
                userfile_id=args.userfile_id,
                group_id=gid,
                flatten=args.flatten,
                skip_dirs=args.skip_dirs,
                dry_run=args.dry_run,
                force=args.force_download,
                timeout=args.timeout,
                show_spinner=not args.debug_logs,
            )
        except FileNotFoundError as err:
            logger.error(str(err))
            sys.exit(1)
        except RuntimeError as err:
            logger.error(str(err))
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()
