# Tool


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | Unique identifier for the Tool. | [optional] 
**name** | **str** | Name of the Tool. | [optional] 
**user_id** | **int** | Creator of the Tool. | [optional] 
**group_id** | **int** | Group that has access to the Tool. | [optional] 
**category** | **str** | Category of the Tool | [optional] 
**cbrain_task_class_name** | **str** | The name of the Task class that will be created when jobs are launched using the Tool. | [optional] 
**select_menu_text** | **str** | Text that appears for Tool selection. | [optional] 
**description** | **str** | Description of the Tool. | [optional] 
**url** | **str** | URL of the website that describes the Tool and possibly has code for the Tool. | [optional] 

## Example

```python
from openapi_client.models.tool import Tool

# TODO update the JSON string below
json = "{}"
# create an instance of Tool from a JSON string
tool_instance = Tool.from_json(json)
# print the JSON string representation of the object
print(Tool.to_json())

# convert the object into a dict
tool_dict = tool_instance.to_dict()
# create an instance of Tool from a dict
tool_from_dict = Tool.from_dict(tool_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


