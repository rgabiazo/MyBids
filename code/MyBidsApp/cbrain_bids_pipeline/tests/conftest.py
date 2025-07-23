import sys
import types
import json
import os

if 'yaml' not in sys.modules:
    yaml_mod = types.ModuleType('yaml')
    yaml_mod.safe_dump = lambda data, stream, **kw: json.dump(data, stream)
    yaml_mod.safe_load = lambda stream: json.load(stream)
    sys.modules['yaml'] = yaml_mod

if 'paramiko' not in sys.modules:
    pmod = types.ModuleType('paramiko')
    class SSHClient:  # minimal stub
        pass
    class SFTPClient:
        pass
    pmod.SSHClient = SSHClient
    pmod.SFTPClient = SFTPClient
    sys.modules['paramiko'] = pmod

if 'requests' not in sys.modules:
    req_mod = types.ModuleType('requests')
    class Response:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json = json_data or {}
        def json(self):
            return self._json
    req_mod.Response = Response
    def dummy(*a, **k):
        return Response()
    req_mod.get = dummy
    req_mod.post = dummy
    req_mod.put = dummy
    sys.modules['requests'] = req_mod

if 'pydantic' not in sys.modules:
    pyd_mod = types.ModuleType('pydantic')
    class ValidationError(Exception):
        pass
    pyd_mod.ValidationError = ValidationError
    sys.modules['pydantic'] = pyd_mod

if 'openapi_client' not in sys.modules:
    oc_mod = types.ModuleType('openapi_client')
    oc_mod.__path__ = []
    oc_sub = types.ModuleType('openapi_client.openapi_client')
    oc_sub.__path__ = []
    oc_api = types.ModuleType('openapi_client.openapi_client.api')
    oc_api.__path__ = []
    oc_ex = types.ModuleType('openapi_client.openapi_client.exceptions')
    oc_conf = types.ModuleType('openapi_client.openapi_client.configuration')
    oc_client = types.ModuleType('openapi_client.openapi_client.api_client')
    oc_api_pkg = types.ModuleType('openapi_client.api')
    oc_api_pkg.__path__ = []
    oc_api_bourreaux = types.ModuleType('openapi_client.api.bourreaux_api')
    oc_api_tools = types.ModuleType('openapi_client.api.tools_api')
    oc_api_tool_configs = types.ModuleType('openapi_client.api.tool_configs_api')
    oc_api_tasks = types.ModuleType('openapi_client.api.tasks_api')
    oc_api_dp = types.ModuleType('openapi_client.api.data_providers_api')
    oc_api_groups = types.ModuleType('openapi_client.api.groups_api')
    oc_api_sessions = types.ModuleType('openapi_client.api.sessions_api')
    oc_api_tags = types.ModuleType('openapi_client.api.tags_api')
    oc_api_userfiles = types.ModuleType('openapi_client.api.userfiles_api')
    oc_api_users = types.ModuleType('openapi_client.api.users_api')
    oc_api_response = types.ModuleType('openapi_client.api_response')
    oc_api_client = types.ModuleType('openapi_client.api_client')
    oc_config = types.ModuleType('openapi_client.configuration')
    oc_exceptions = types.ModuleType('openapi_client.exceptions')

    class Dummy:
        pass
    oc_api_bourreaux.BourreauxApi = Dummy
    oc_api_tools.ToolsApi = Dummy
    oc_api_tool_configs.ToolConfigsApi = Dummy
    oc_api_tasks.TasksApi = Dummy
    oc_api_dp.DataProvidersApi = Dummy
    oc_api_groups.GroupsApi = Dummy
    oc_api_sessions.SessionsApi = Dummy
    oc_api_tags.TagsApi = Dummy
    oc_api_userfiles.UserfilesApi = Dummy
    oc_api_users.UsersApi = Dummy
    oc_api_response.ApiResponse = Dummy
    oc_api_client.ApiClient = Dummy
    oc_config.Configuration = Dummy
    oc_exceptions.OpenApiException = Dummy
    def _exc_getattr(name):
        return Dummy
    oc_exceptions.__getattr__ = _exc_getattr

    class ApiClient:
        pass

    class Configuration:
        pass

    class ToolsApi:
        pass

    class ToolConfigsApi:
        pass

    class BourreauxApi:
        pass

    class TasksApi:
        pass

    class ApiException(Exception):
        pass

    oc_client.ApiClient = ApiClient
    oc_conf.Configuration = Configuration
    oc_api.ToolsApi = ToolsApi
    oc_api.ToolConfigsApi = ToolConfigsApi
    oc_api.BourreauxApi = BourreauxApi
    oc_api.TasksApi = TasksApi
    oc_ex.ApiException = ApiException


    sys.modules['openapi_client'] = oc_mod
    sys.modules['openapi_client.openapi_client'] = oc_sub
    sys.modules['openapi_client.openapi_client.api'] = oc_api
    sys.modules['openapi_client.openapi_client.api.tools_api'] = oc_api
    sys.modules['openapi_client.openapi_client.api.tool_configs_api'] = oc_api
    sys.modules['openapi_client.openapi_client.api.bourreaux_api'] = oc_api
    sys.modules['openapi_client.openapi_client.api.tasks_api'] = oc_api
    sys.modules['openapi_client.openapi_client.configuration'] = oc_conf
    sys.modules['openapi_client.openapi_client.api_client'] = oc_client
    sys.modules['openapi_client.openapi_client.exceptions'] = oc_ex
    sys.modules['openapi_client.api'] = oc_api_pkg
    sys.modules['openapi_client.api.bourreaux_api'] = oc_api_bourreaux
    sys.modules['openapi_client.api.tools_api'] = oc_api_tools
    sys.modules['openapi_client.api.tool_configs_api'] = oc_api_tool_configs
    sys.modules['openapi_client.api.tasks_api'] = oc_api_tasks
    sys.modules['openapi_client.api.data_providers_api'] = oc_api_dp
    sys.modules['openapi_client.api.groups_api'] = oc_api_groups
    sys.modules['openapi_client.api.sessions_api'] = oc_api_sessions
    sys.modules['openapi_client.api.tags_api'] = oc_api_tags
    sys.modules['openapi_client.api.userfiles_api'] = oc_api_userfiles
    sys.modules['openapi_client.api.users_api'] = oc_api_users
    sys.modules['openapi_client.api_response'] = oc_api_response
    sys.modules['openapi_client.api_client'] = oc_api_client
    sys.modules['openapi_client.configuration'] = oc_config
    sys.modules['openapi_client.exceptions'] = oc_exceptions

# Ensure the bids_cbrain_runner package is importable
pkg_root = os.path.abspath(os.path.join(__file__, "..", ".."))
pkg_root = os.path.normpath(pkg_root)
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)
