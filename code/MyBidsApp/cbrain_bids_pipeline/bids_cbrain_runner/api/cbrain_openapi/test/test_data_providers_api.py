# coding: utf-8

"""
    CBRAIN API

    API for interacting with the CBRAIN Platform

    The version of the OpenAPI document: 6.2.0.1
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest

from openapi_client.api.data_providers_api import DataProvidersApi


class TestDataProvidersApi(unittest.TestCase):
    """DataProvidersApi unit test stubs"""

    def setUp(self) -> None:
        self.api = DataProvidersApi()

    def tearDown(self) -> None:
        pass

    def test_data_providers_get(self) -> None:
        """Test case for data_providers_get

        Get a list of the Data Providers available to the current user.
        """
        pass

    def test_data_providers_id_browse_get(self) -> None:
        """Test case for data_providers_id_browse_get

        List the files on a Data Provider.
        """
        pass

    def test_data_providers_id_delete_post(self) -> None:
        """Test case for data_providers_id_delete_post

        Deletes unregistered files from a CBRAIN Data provider.
        """
        pass

    def test_data_providers_id_get(self) -> None:
        """Test case for data_providers_id_get

        Get information on a particular Data Provider.
        """
        pass

    def test_data_providers_id_is_alive_get(self) -> None:
        """Test case for data_providers_id_is_alive_get

        Pings a Data Provider to check if it is running.
        """
        pass

    def test_data_providers_id_register_post(self) -> None:
        """Test case for data_providers_id_register_post

        Registers a file as a Userfile in CBRAIN.
        """
        pass

    def test_data_providers_id_unregister_post(self) -> None:
        """Test case for data_providers_id_unregister_post

        Unregisters files as Userfile in CBRAIN.
        """
        pass


if __name__ == '__main__':
    unittest.main()
