# FileInfo


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**userfile_id** | **int** | id of the userfile | [optional] 
**name** | **str** | the base filename | [optional] 
**group** | **str** | string representation of gid, the name of the group | [optional] 
**gid** | **int** | numeric group id of the file | [optional] 
**owner** | **str** | string representation of uid, the name of the owner | [optional] 
**uid** | **int** | numeric uid of owner | [optional] 
**permissions** | **int** | an int interpreted in octal, e.g. 0640 | [optional] 
**size** | **int** | size of file in bytes | [optional] 
**state_ok** | **bool** | flag that tell whether or not it is OK to register/unregister | [optional] 
**message** | **str** | a message to give more information about the state_ok flag | [optional] 
**symbolic_type** | **str** | one of :regular, :symlink, :directory | [optional] 
**atime** | **int** | access time (an int, since Epoch) | [optional] 
**mtime** | **int** | modification time (an int, since Epoch) | [optional] 

## Example

```python
from openapi_client.models.file_info import FileInfo

# TODO update the JSON string below
json = "{}"
# create an instance of FileInfo from a JSON string
file_info_instance = FileInfo.from_json(json)
# print the JSON string representation of the object
print(FileInfo.to_json())

# convert the object into a dict
file_info_dict = file_info_instance.to_dict()
# create an instance of FileInfo from a dict
file_info_from_dict = FileInfo.from_dict(file_info_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


