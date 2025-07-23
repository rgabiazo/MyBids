# RegistrationInfo


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**notice** | **str** |  | [optional] 
**error** | **str** |  | [optional] 
**newly_registered_userfiles** | [**List[Userfile]**](Userfile.md) |  | [optional] 
**previously_registered_userfiles** | [**List[Userfile]**](Userfile.md) |  | [optional] 
**userfiles_in_transit** | [**List[Userfile]**](Userfile.md) |  | [optional] 
**num_unregistered** | **int** |  | [optional] 
**num_erased** | **int** |  | [optional] 

## Example

```python
from openapi_client.models.registration_info import RegistrationInfo

# TODO update the JSON string below
json = "{}"
# create an instance of RegistrationInfo from a JSON string
registration_info_instance = RegistrationInfo.from_json(json)
# print the JSON string representation of the object
print(RegistrationInfo.to_json())

# convert the object into a dict
registration_info_dict = registration_info_instance.to_dict()
# create an instance of RegistrationInfo from a dict
registration_info_from_dict = RegistrationInfo.from_dict(registration_info_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


