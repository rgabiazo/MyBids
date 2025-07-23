# openapi_client.SessionsApi

All URIs are relative to *http://localhost:3000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**session_delete**](SessionsApi.md#session_delete) | **DELETE** /session | Destroy the current session
[**session_get**](SessionsApi.md#session_get) | **GET** /session | Get session information
[**session_post**](SessionsApi.md#session_post) | **POST** /session | Create a new session


# **session_delete**
> session_delete()

Destroy the current session

This destroys the current session, effectively terminating the
access to the service.


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
    api_instance = openapi_client.SessionsApi(api_client)

    try:
        # Destroy the current session
        api_instance.session_delete()
    except Exception as e:
        print("Exception when calling SessionsApi->session_delete: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

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
**200** | Session terminated |  -  |
**401** | No session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **session_get**
> SessionInfo session_get()

Get session information

This returns information about the current session.


### Example

* Api Key Authentication (BrainPortalSession):

```python
import openapi_client
from openapi_client.models.session_info import SessionInfo
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
    api_instance = openapi_client.SessionsApi(api_client)

    try:
        # Get session information
        api_response = api_instance.session_get()
        print("The response of SessionsApi->session_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling SessionsApi->session_get: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

[**SessionInfo**](SessionInfo.md)

### Authorization

[BrainPortalSession](../README.md#BrainPortalSession)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | An object with the API token and the CBRAIN user ID |  -  |
**401** | No session created yet. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **session_post**
> SessionInfo session_post(login, password)

Create a new session

This is the main entry point to create a CBRAIN session. Note that if
a user is currently logged in, a new session will not be created,
and the current session will be re-used.


### Example


```python
import openapi_client
from openapi_client.models.session_info import SessionInfo
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost:3000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://localhost:3000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.SessionsApi(api_client)
    login = 'login_example' # str | The username of the user trying to connect.
    password = 'password_example' # str | The password of the user

    try:
        # Create a new session
        api_response = api_instance.session_post(login, password)
        print("The response of SessionsApi->session_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling SessionsApi->session_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **login** | **str**| The username of the user trying to connect. | 
 **password** | **str**| The password of the user | 

### Return type

[**SessionInfo**](SessionInfo.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/x-www-form-urlencoded
 - **Accept**: application/json, application/xml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | An object with the API token and the CBRAIN user ID |  -  |
**401** | Password authentication failed. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

