# ToolConfig


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | Unique numerical ID for the ToolConfig. | [optional] 
**version_name** | **str** | the version name of the configuration | [optional] 
**description** | **str** | a description of the configuration | [optional] 
**tool_id** | **int** | the ID of the tool associated with this configuration | [optional] 
**bourreau_id** | **int** | The ID of the execution server where this tool configuration is available.  | [optional] 
**group_id** | **int** | the ID of the project controlling access to this ToolConfig | [optional] 
**ncpus** | **int** | A hint at how many CPUs the CBRAIN task will allocate to run this tool configuration  | [optional] 

## Example

```python
from openapi_client.models.tool_config import ToolConfig

# TODO update the JSON string below
json = "{}"
# create an instance of ToolConfig from a JSON string
tool_config_instance = ToolConfig.from_json(json)
# print the JSON string representation of the object
print(ToolConfig.to_json())

# convert the object into a dict
tool_config_dict = tool_config_instance.to_dict()
# create an instance of ToolConfig from a dict
tool_config_from_dict = ToolConfig.from_dict(tool_config_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


