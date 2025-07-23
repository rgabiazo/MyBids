# User


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | Unique numerical ID for the user. | [optional] 
**login** | **str** | UNIX-style username. | [optional] 
**password** | **str** | Password field | [optional] 
**password_confirmation** | **str** | Password field (generally same as &#39;password&#39;) | [optional] 
**full_name** | **str** | Full name of the user. | [optional] 
**email** | **str** | email address of the user. | [optional] 
**city** | **str** | city where the user is located | [optional] 
**country** | **str** | country where the user is located | [optional] 
**time_zone** | **str** | time-zone (should make it this an enum) | [optional] 
**type** | **str** | Classification of user permission level | [optional] [default to 'NormalUser']
**site_id** | **int** | ID of the site affiliation for the user. | [optional] 
**last_connected_at** | **str** | time of last connection by the user. (can be empty) | [optional] 
**account_locked** | **bool** | Whether or not the account is locked. | [optional] 

## Example

```python
from openapi_client.models.user import User

# TODO update the JSON string below
json = "{}"
# create an instance of User from a JSON string
user_instance = User.from_json(json)
# print the JSON string representation of the object
print(User.to_json())

# convert the object into a dict
user_dict = user_instance.to_dict()
# create an instance of User from a dict
user_from_dict = User.from_dict(user_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


