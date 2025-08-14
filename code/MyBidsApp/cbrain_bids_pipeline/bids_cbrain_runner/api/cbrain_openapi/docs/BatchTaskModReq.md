# BatchTaskModReq


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**tasklist** | **List[int]** |  | [optional] 
**batch_ids** | **List[int]** |  | [optional] 

## Example

```python
from openapi_client.models.batch_task_mod_req import BatchTaskModReq

# TODO update the JSON string below
json = "{}"
# create an instance of BatchTaskModReq from a JSON string
batch_task_mod_req_instance = BatchTaskModReq.from_json(json)
# print the JSON string representation of the object
print(BatchTaskModReq.to_json())

# convert the object into a dict
batch_task_mod_req_dict = batch_task_mod_req_instance.to_dict()
# create an instance of BatchTaskModReq from a dict
batch_task_mod_req_from_dict = BatchTaskModReq.from_dict(batch_task_mod_req_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


