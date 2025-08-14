# MultiRegistrationModReq


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**basenames** | **List[str]** |  | [optional] 
**filetypes** | **List[str]** | An array containing the filetypes associated with the files to register; each element must be a string containing the cbrain file type, a single dash, and then a repeat of the basename found in the basenames parameters. For example, \&quot;TextFile-abc.txt\&quot; | [optional] 
**as_user_id** | **int** | The ID of the user to register files as. | [optional] 
**other_group_id** | **int** | The ID of the project controlling access to the registered files. | [optional] 
**delete** | **bool** | Specifies to delete the file contents. This is only used during an \&quot;unregister\&quot; action. | [optional] [default to False]

## Example

```python
from openapi_client.models.multi_registration_mod_req import MultiRegistrationModReq

# TODO update the JSON string below
json = "{}"
# create an instance of MultiRegistrationModReq from a JSON string
multi_registration_mod_req_instance = MultiRegistrationModReq.from_json(json)
# print the JSON string representation of the object
print(MultiRegistrationModReq.to_json())

# convert the object into a dict
multi_registration_mod_req_dict = multi_registration_mod_req_instance.to_dict()
# create an instance of MultiRegistrationModReq from a dict
multi_registration_mod_req_from_dict = MultiRegistrationModReq.from_dict(multi_registration_mod_req_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


