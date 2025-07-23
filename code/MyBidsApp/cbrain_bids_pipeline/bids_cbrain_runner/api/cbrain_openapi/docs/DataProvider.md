# DataProvider


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | Unique ID for the Data Provider. | [optional] 
**name** | **str** | Name of the Data Provider. | [optional] 
**type** | **str** | Type of Data Provider, which usually indicates whether it is a local Data Provider, has a flat internal directory structure, or is meant for file uploading to CBRAIN. | [optional] 
**user_id** | **int** | Creator and owner of the Data Provider. | [optional] 
**group_id** | **int** | ID of the group that has access to this Data Provider. | [optional] 
**online** | **bool** | Boolean variable that indicates whether the system hosting the Data Provider is accessible. | [optional] 
**read_only** | **bool** | Boolean variable that indicates whether the Data Provider can be written to. | [optional] 
**description** | **str** | Description of the Data Provider. | [optional] 
**is_browsable** | **bool** |  | [optional] 
**is_fast_syncing** | **bool** |  | [optional] 
**allow_file_owner_change** | **bool** |  | [optional] 
**content_storage_shared_between_users** | **bool** |  | [optional] 

## Example

```python
from openapi_client.models.data_provider import DataProvider

# TODO update the JSON string below
json = "{}"
# create an instance of DataProvider from a JSON string
data_provider_instance = DataProvider.from_json(json)
# print the JSON string representation of the object
print(DataProvider.to_json())

# convert the object into a dict
data_provider_dict = data_provider_instance.to_dict()
# create an instance of DataProvider from a dict
data_provider_from_dict = DataProvider.from_dict(data_provider_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


