# openapi_client.TagsApi

All URIs are relative to *http://localhost:3000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**tags_get**](TagsApi.md#tags_get) | **GET** /tags | Get a list of the tags currently in CBRAIN.
[**tags_id_delete**](TagsApi.md#tags_id_delete) | **DELETE** /tags/{id} | Delete a tag.
[**tags_id_get**](TagsApi.md#tags_id_get) | **GET** /tags/{id} | Get one tag.
[**tags_id_put**](TagsApi.md#tags_id_put) | **PUT** /tags/{id} | Update a tag.
[**tags_post**](TagsApi.md#tags_post) | **POST** /tags | Create a new tag.


# **tags_get**
> List[Tag] tags_get()

Get a list of the tags currently in CBRAIN.

This method returns a list of tag objects.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.tag import Tag
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
    api_instance = openapi_client.TagsApi(api_client)

    try:
        # Get a list of the tags currently in CBRAIN.
        api_response = api_instance.tags_get()
        print("The response of TagsApi->tags_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling TagsApi->tags_get: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

[**List[Tag]**](Tag.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | An array of Tag objects that are used to group Tasks or Userfiles.  |  -  |
**401** | No session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **tags_id_delete**
> tags_id_delete(id)

Delete a tag.

Delete the tag specified by the ID parameter.

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
    api_instance = openapi_client.TagsApi(api_client)
    id = 56 # int | ID of the tag to delete.

    try:
        # Delete a tag.
        api_instance.tags_id_delete(id)
    except Exception as e:
        print("Exception when calling TagsApi->tags_id_delete: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| ID of the tag to delete. | 

### Return type

void (empty response body)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Tag was deleted. |  -  |
**401** | No session created yet. |  -  |
**422** | Tag could not be deleted. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **tags_id_get**
> Tag tags_id_get(id)

Get one tag.

Returns a single tag with the ID specified.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.tag import Tag
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
    api_instance = openapi_client.TagsApi(api_client)
    id = 56 # int | The ID of the tag to get.

    try:
        # Get one tag.
        api_response = api_instance.tags_id_get(id)
        print("The response of TagsApi->tags_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling TagsApi->tags_id_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| The ID of the tag to get. | 

### Return type

[**Tag**](Tag.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns the Tag object.  |  -  |
**401** | No session created yet.  |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **tags_id_put**
> tags_id_put(id, tag_mod_req)

Update a tag.

Update the tag specified by the ID parameter.

### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.tag_mod_req import TagModReq
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
    api_instance = openapi_client.TagsApi(api_client)
    id = 56 # int | ID of the tag to update.
    tag_mod_req = openapi_client.TagModReq() # TagModReq | 

    try:
        # Update a tag.
        api_instance.tags_id_put(id, tag_mod_req)
    except Exception as e:
        print("Exception when calling TagsApi->tags_id_put: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| ID of the tag to update. | 
 **tag_mod_req** | [**TagModReq**](TagModReq.md)|  | 

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
**200** | Tag was updated successfully. |  -  |
**401** | No session created yet. |  -  |
**422** | Could not update Tag. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **tags_post**
> Tag tags_post(tag_mod_req)

Create a new tag.

Create a new tag in CBRAIN.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.tag import Tag
from openapi_client.models.tag_mod_req import TagModReq
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
    api_instance = openapi_client.TagsApi(api_client)
    tag_mod_req = openapi_client.TagModReq() # TagModReq | 

    try:
        # Create a new tag.
        api_response = api_instance.tags_post(tag_mod_req)
        print("The response of TagsApi->tags_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling TagsApi->tags_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **tag_mod_req** | [**TagModReq**](TagModReq.md)|  | 

### Return type

[**Tag**](Tag.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Returns the created Tag object.  |  -  |
**401** | No session created yet.  |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

