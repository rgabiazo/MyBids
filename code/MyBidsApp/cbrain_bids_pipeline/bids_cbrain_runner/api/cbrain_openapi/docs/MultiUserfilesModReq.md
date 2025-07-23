# MultiUserfilesModReq


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**file_ids** | **List[str]** |  | [optional] 
**data_provider_id_for_mv_cp** | **int** |  | [optional] 
**specified_filename** | **str** | The name of the archive file that the Userfiles will be compressed into when downloading. | [optional] 
**operation** | **str** | Used when affecting the synchronization status of files. Either \&quot;sync_local\&quot; or \&quot;all_newer\&quot;. \&quot;sync_local\&quot; will ensure that the version of the file in the CBRAIN portal cache is the most recent version that exists on the Data Provider. \&quot;all_newer\&quot; will ensure that ALL caches known to CBRAIN are updated with the most recent version of the files in the host Data Provider. | [optional] 

## Example

```python
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq

# TODO update the JSON string below
json = "{}"
# create an instance of MultiUserfilesModReq from a JSON string
multi_userfiles_mod_req_instance = MultiUserfilesModReq.from_json(json)
# print the JSON string representation of the object
print(MultiUserfilesModReq.to_json())

# convert the object into a dict
multi_userfiles_mod_req_dict = multi_userfiles_mod_req_instance.to_dict()
# create an instance of MultiUserfilesModReq from a dict
multi_userfiles_mod_req_from_dict = MultiUserfilesModReq.from_dict(multi_userfiles_mod_req_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


