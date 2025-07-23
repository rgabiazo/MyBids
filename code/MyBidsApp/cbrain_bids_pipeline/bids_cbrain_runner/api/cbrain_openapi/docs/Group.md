# Group


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | ID number of the group. | [optional] 
**name** | **str** | Name of the group. | [optional] 
**description** | **str** | Description of the group. | [optional] 
**type** | **str** | Type of group. | [optional] 
**site_id** | **int** | ID of the site associated with the group. | [optional] 
**creator_id** | **int** | ID of the User who created the group.  | [optional] 
**invisible** | **bool** | Specifies whether or not the group is visible to Normal Users. Invisible groups exist to specify levels of access to Userfiles, DataProviders and Bourreaux.  | [optional] 

## Example

```python
from openapi_client.models.group import Group

# TODO update the JSON string below
json = "{}"
# create an instance of Group from a JSON string
group_instance = Group.from_json(json)
# print the JSON string representation of the object
print(Group.to_json())

# convert the object into a dict
group_dict = group_instance.to_dict()
# create an instance of Group from a dict
group_from_dict = Group.from_dict(group_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


