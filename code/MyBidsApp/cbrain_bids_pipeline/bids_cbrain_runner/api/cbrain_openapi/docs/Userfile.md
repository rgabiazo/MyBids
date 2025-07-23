# Userfile


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** | ID number of the file. | [optional] 
**name** | **str** | Name of the file that the Userfile represents | [optional] 
**size** | **int** | Number of bytes used to store the file. | [optional] 
**user_id** | **int** | ID of the owner of the file. | [optional] 
**parent_id** | **int** | ID of the parent Userfile, if any exists, or null otherwise. | [optional] 
**type** | **str** | Type of the file. This is important in determining what tools can be run on the file. The most generic file types, are the Single File, which represents one file, and the File Collection, which represents a directory full of files. | [optional] 
**group_id** | **int** | ID of the group that owns the file, which determines its visibility status. | [optional] 
**data_provider_id** | **int** | ID of the Data Provider that is hosting the persistent copy of the file. It may exist in caches across the systems that make up CBRAIN, as copies of the file are made in order to run scientific programs on them on remote systems. | [optional] 
**group_writable** | **bool** | Boolean variable that specifies whether members of the owner group have access to modify or overwrite the file. | [optional] 
**num_files** | **int** | Number of files that the Userfiles represents. For Single Files, this is always 1. | [optional] 
**hidden** | **bool** | Boolean variable that specifies whether this file is hidden or not in the user interface. | [optional] 
**immutable** | **bool** | Boolean variable that specifies whether any user can modify the contents of the file. | [optional] 
**archived** | **bool** | Boolean variable that specifies whether the file is available, uncompressed, or has been archived. | [optional] 
**description** | **str** | Description of the file. | [optional] 

## Example

```python
from openapi_client.models.userfile import Userfile

# TODO update the JSON string below
json = "{}"
# create an instance of Userfile from a JSON string
userfile_instance = Userfile.from_json(json)
# print the JSON string representation of the object
print(Userfile.to_json())

# convert the object into a dict
userfile_dict = userfile_instance.to_dict()
# create an instance of Userfile from a dict
userfile_from_dict = Userfile.from_dict(userfile_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


