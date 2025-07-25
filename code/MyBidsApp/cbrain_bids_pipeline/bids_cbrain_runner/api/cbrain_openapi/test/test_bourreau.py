# coding: utf-8

"""
    CBRAIN API

    API for interacting with the CBRAIN Platform

    The version of the OpenAPI document: 6.2.0.1
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest

from openapi_client.models.bourreau import Bourreau

class TestBourreau(unittest.TestCase):
    """Bourreau unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional) -> Bourreau:
        """Test Bourreau
            include_optional is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # uncomment below to create an instance of `Bourreau`
        """
        model = Bourreau()
        if include_optional:
            return Bourreau(
                id = 56,
                name = '',
                user_id = 56,
                group_id = 56,
                online = '',
                read_only = '',
                description = ''
            )
        else:
            return Bourreau(
        )
        """

    def testBourreau(self):
        """Test Bourreau"""
        # inst_req_only = self.make_instance(include_optional=False)
        # inst_req_and_optional = self.make_instance(include_optional=True)

if __name__ == '__main__':
    unittest.main()
