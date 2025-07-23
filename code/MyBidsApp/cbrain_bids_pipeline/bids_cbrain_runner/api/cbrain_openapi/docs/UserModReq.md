# UserModReq


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**user** | [**User**](User.md) |  | [optional] 
**no_password_reset_needed** | **int** | For new user accounts, the user must reset the password at first login | [optional] 
**force_password_reset** | **bool** | For existing accounts, boolean to force a password change | [optional] 

## Example

```python
from openapi_client.models.user_mod_req import UserModReq

# TODO update the JSON string below
json = "{}"
# create an instance of UserModReq from a JSON string
user_mod_req_instance = UserModReq.from_json(json)
# print the JSON string representation of the object
print(UserModReq.to_json())

# convert the object into a dict
user_mod_req_dict = user_mod_req_instance.to_dict()
# create an instance of UserModReq from a dict
user_mod_req_from_dict = UserModReq.from_dict(user_mod_req_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


