# openapi_client.ToolsApi

All URIs are relative to *http://localhost:3000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**tools_get**](ToolsApi.md#tools_get) | **GET** /tools | Get the list of Tools.


# **tools_get**
> List[Tool] tools_get(page=page, per_page=per_page)

Get the list of Tools.

This method returns a list of all of the Tools that exist in CBRAIN.
Tools encapsulate a scientific program designed to extract information
from an input Userfile.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.tool import Tool
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
    api_instance = openapi_client.ToolsApi(api_client)
    page = 56 # int | Page number when paginating. See also the per_page parameter (optional)
    per_page = 56 # int | Size of each page when paginating. See also the page parameter (optional)

    try:
        # Get the list of Tools.
        api_response = api_instance.tools_get(page=page, per_page=per_page)
        print("The response of ToolsApi->tools_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling ToolsApi->tools_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page** | **int**| Page number when paginating. See also the per_page parameter | [optional] 
 **per_page** | **int**| Size of each page when paginating. See also the page parameter | [optional] 

### Return type

[**List[Tool]**](Tool.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | List of Tools. |  -  |
**401** | No Session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

