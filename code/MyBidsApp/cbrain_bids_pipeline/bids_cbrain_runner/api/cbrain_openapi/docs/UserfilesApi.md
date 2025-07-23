# openapi_client.UserfilesApi

All URIs are relative to *http://localhost:3000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**userfiles_change_provider_post**](UserfilesApi.md#userfiles_change_provider_post) | **POST** /userfiles/change_provider | Moves the Userfiles from their current Data Provider to a new one.
[**userfiles_compress_post**](UserfilesApi.md#userfiles_compress_post) | **POST** /userfiles/compress | Compresses many Userfiles each into their own GZIP archive.
[**userfiles_delete_files_delete**](UserfilesApi.md#userfiles_delete_files_delete) | **DELETE** /userfiles/delete_files | Delete several files that have been registered as Userfiles
[**userfiles_download_post**](UserfilesApi.md#userfiles_download_post) | **POST** /userfiles/download | Download several files
[**userfiles_get**](UserfilesApi.md#userfiles_get) | **GET** /userfiles | List of the Userfiles accessible to the current user.
[**userfiles_id_content_get**](UserfilesApi.md#userfiles_id_content_get) | **GET** /userfiles/{id}/content | Get the content of a Userfile
[**userfiles_id_get**](UserfilesApi.md#userfiles_id_get) | **GET** /userfiles/{id} | Get information on a Userfile.
[**userfiles_id_put**](UserfilesApi.md#userfiles_id_put) | **PUT** /userfiles/{id} | Update information on a Userfile.
[**userfiles_post**](UserfilesApi.md#userfiles_post) | **POST** /userfiles | Creates a new Userfile and upload its content.
[**userfiles_sync_multiple_post**](UserfilesApi.md#userfiles_sync_multiple_post) | **POST** /userfiles/sync_multiple | Syncs Userfiles to the local Data Providers cache.
[**userfiles_uncompress_post**](UserfilesApi.md#userfiles_uncompress_post) | **POST** /userfiles/uncompress | Uncompresses many Userfiles.


# **userfiles_change_provider_post**
> userfiles_change_provider_post(multi_userfile_mod_req)

Moves the Userfiles from their current Data Provider to a new one.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to move.

    try:
        # Moves the Userfiles from their current Data Provider to a new one.
        api_instance.userfiles_change_provider_post(multi_userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_change_provider_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to move. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that the files are being moved or copied in the background. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_compress_post**
> userfiles_compress_post(multi_userfile_mod_req)

Compresses many Userfiles each into their own GZIP archive.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to compress.

    try:
        # Compresses many Userfiles each into their own GZIP archive.
        api_instance.userfiles_compress_post(multi_userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_compress_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to compress. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that the compression is starting in the background. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_delete_files_delete**
> userfiles_delete_files_delete(multi_userfile_mod_req)

Delete several files that have been registered as Userfiles

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to destroy.

    try:
        # Delete several files that have been registered as Userfiles
        api_instance.userfiles_delete_files_delete(multi_userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_delete_files_delete: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to destroy. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that the files are being deleted. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_download_post**
> bytearray userfiles_download_post(multi_userfile_mod_req)

Download several files

This method compresses several Userfiles in .gz format and prepares them to be downloaded.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to be downloaded. If more than one file is specified, they will be zipped into a gzip archive.

    try:
        # Download several files
        api_response = api_instance.userfiles_download_post(multi_userfile_mod_req)
        print("The response of UserfilesApi->userfiles_download_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_download_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to be downloaded. If more than one file is specified, they will be zipped into a gzip archive. | 

### Return type

**bytearray**

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: application/*, text/*

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that the files are being compressed and downloaded. |  -  |
**403** | Forbidden |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_get**
> List[Userfile] userfiles_get(page=page, per_page=per_page)

List of the Userfiles accessible to the current user.

This method returns a list of Userfiles that are available to the current User.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.userfile import Userfile
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    page = 56 # int | Page number when paginating. See also the per_page parameter (optional)
    per_page = 56 # int | Size of each page when paginating. See also the page parameter (optional)

    try:
        # List of the Userfiles accessible to the current user.
        api_response = api_instance.userfiles_get(page=page, per_page=per_page)
        print("The response of UserfilesApi->userfiles_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page** | **int**| Page number when paginating. See also the per_page parameter | [optional] 
 **per_page** | **int**| Size of each page when paginating. See also the page parameter | [optional] 

### Return type

[**List[Userfile]**](Userfile.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | List of accessible Userfiles. |  -  |
**401** | No Session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_id_content_get**
> bytearray userfiles_id_content_get(id)

Get the content of a Userfile

This method allows you to download the content of a userfile.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    id = 56 # int | The ID number of the Userfile to download

    try:
        # Get the content of a Userfile
        api_response = api_instance.userfiles_id_content_get(id)
        print("The response of UserfilesApi->userfiles_id_content_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_id_content_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| The ID number of the Userfile to download | 

### Return type

**bytearray**

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/*, text/*

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | The contents of the file |  -  |
**403** | Forbidden |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_id_get**
> Userfile userfiles_id_get(id)

Get information on a Userfile.

This method returns information about a single Userfile, specified by
its ID. Information returned includes the ID of the owner, the Group
(project) it is a part of, a description, information about where the
acutal copy of the file currently is, and what the status is of any
synhronization operations that may have been requested.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.userfile import Userfile
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    id = 56 # int | The ID number of the Userfile to get information on.

    try:
        # Get information on a Userfile.
        api_response = api_instance.userfiles_id_get(id)
        print("The response of UserfilesApi->userfiles_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_id_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| The ID number of the Userfile to get information on. | 

### Return type

[**Userfile**](Userfile.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns the information about the Userfile. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_id_put**
> userfiles_id_put(id, userfile_mod_req)

Update information on a Userfile.

This method allows a User to update information on a userfile.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.userfile_mod_req import UserfileModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    id = 56 # int | The ID number of the Userfile to update.
    userfile_mod_req = openapi_client.UserfileModReq() # UserfileModReq | 

    try:
        # Update information on a Userfile.
        api_instance.userfiles_id_put(id, userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_id_put: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| The ID number of the Userfile to update. | 
 **userfile_mod_req** | [**UserfileModReq**](UserfileModReq.md)|  | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Userfile updated successfully. |  -  |
**401** | No session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_post**
> object userfiles_post(upload_file, data_provider_id, userfile_group_id, file_type, do_extract=do_extract, up_ex_mode=up_ex_mode)

Creates a new Userfile and upload its content.

This method creates a new Userfile in CBRAIN, with the current user
as the owner of the file.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    upload_file = None # bytearray | File content to upload to CBRAIN
    data_provider_id = 56 # int | The ID of the Data Provider to upload the file to.
    userfile_group_id = 56 # int | ID of the group that will have access to the Userfile
    file_type = 'SingleFile' # str | The type of the file (default to 'SingleFile')
    do_extract = 'do_extract_example' # str | set to the string 'on' to indicate that the uploaded content is a tar.gz or .zip archive that need to be extracted. See also the parameter _up_ex_mode (optional)
    up_ex_mode = 'up_ex_mode_example' # str | if '_do_extract' is set to 'on', set this to 'collection' to create a single collection, or 'multiple' to create one file per entry in the uploaded content (optional)

    try:
        # Creates a new Userfile and upload its content.
        api_response = api_instance.userfiles_post(upload_file, data_provider_id, userfile_group_id, file_type, do_extract=do_extract, up_ex_mode=up_ex_mode)
        print("The response of UserfilesApi->userfiles_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **upload_file** | **bytearray**| File content to upload to CBRAIN | 
 **data_provider_id** | **int**| The ID of the Data Provider to upload the file to. | 
 **userfile_group_id** | **int**| ID of the group that will have access to the Userfile | 
 **file_type** | **str**| The type of the file | [default to &#39;SingleFile&#39;]
 **do_extract** | **str**| set to the string &#39;on&#39; to indicate that the uploaded content is a tar.gz or .zip archive that need to be extracted. See also the parameter _up_ex_mode | [optional] 
 **up_ex_mode** | **str**| if &#39;_do_extract&#39; is set to &#39;on&#39;, set this to &#39;collection&#39; to create a single collection, or &#39;multiple&#39; to create one file per entry in the uploaded content | [optional] 

### Return type

**object**

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: multipart/form-data
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Userfile successfully created. |  -  |
**401** | No Session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_sync_multiple_post**
> userfiles_sync_multiple_post(multi_userfile_mod_req)

Syncs Userfiles to the local Data Providers cache.

Synchronizing files to their the local cache allows you to download, visualize and do processing on them that is not available if not synced. CBRAIN operations will sync files automatically, and this is only necessary if a file is changed on its host Data Provdier by an external process.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to synchronize.

    try:
        # Syncs Userfiles to the local Data Providers cache.
        api_instance.userfiles_sync_multiple_post(multi_userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_sync_multiple_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to synchronize. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that synchronization is starting in the background |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **userfiles_uncompress_post**
> userfiles_uncompress_post(multi_userfile_mod_req)

Uncompresses many Userfiles.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.multi_userfiles_mod_req import MultiUserfilesModReq
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: BrainPortalSession
configuration.api_key['BrainPortalSession'] = os.environ["API_KEY"]

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['BrainPortalSession'] = 'Bearer'

# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.UserfilesApi(api_client)
    multi_userfile_mod_req = openapi_client.MultiUserfilesModReq() # MultiUserfilesModReq | The IDs of the files to uncompress.

    try:
        # Uncompresses many Userfiles.
        api_instance.userfiles_uncompress_post(multi_userfile_mod_req)
    except Exception as e:
        print("Exception when calling UserfilesApi->userfiles_uncompress_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **multi_userfile_mod_req** | [**MultiUserfilesModReq**](MultiUserfilesModReq.md)| The IDs of the files to uncompress. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Indicates that files are being uncompressed in the background. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

