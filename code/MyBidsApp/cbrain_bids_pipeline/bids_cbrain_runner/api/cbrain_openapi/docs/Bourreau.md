# Bourreau


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | Unique numerical ID for the bourreau. | [optional] 
**name** | **str** | Name given by the creator to the bourreau. | [optional] 
**user_id** | **int** | ID of the creator of the bourreau. | [optional] 
**group_id** | **int** | ID of the group allowed to use the bourreau. | [optional] 
**online** | **bool** | online | [optional] 
**read_only** | **bool** | Specifies whether the bourreau is read-only or can be modified. | [optional] 
**description** | **str** | Description of the bourreau. | [optional] 

## Example

```python
from openapi_client.models.bourreau import Bourreau

# TODO update the JSON string below
json = "{}"
# create an instance of Bourreau from a JSON string
bourreau_instance = Bourreau.from_json(json)
# print the JSON string representation of the object
print(Bourreau.to_json())

# convert the object into a dict
bourreau_dict = bourreau_instance.to_dict()
# create an instance of Bourreau from a dict
bourreau_from_dict = Bourreau.from_dict(bourreau_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


