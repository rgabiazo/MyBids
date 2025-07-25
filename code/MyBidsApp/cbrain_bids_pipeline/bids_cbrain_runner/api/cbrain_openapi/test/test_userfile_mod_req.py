# coding: utf-8

"""
    CBRAIN API

    API for interacting with the CBRAIN Platform

    The version of the OpenAPI document: 6.2.0.1
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest

from openapi_client.models.userfile_mod_req import UserfileModReq

class TestUserfileModReq(unittest.TestCase):
    """UserfileModReq unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional) -> UserfileModReq:
        """Test UserfileModReq
            include_optional is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # uncomment below to create an instance of `UserfileModReq`
        """
        model = UserfileModReq()
        if include_optional:
            return UserfileModReq(
                userfile = openapi_client.models.userfile.Userfile(
                    id = 56, 
                    name = '', 
                    size = 56, 
                    user_id = 56, 
                    parent_id = 56, 
                    type = '', 
                    group_id = 56, 
                    data_provider_id = 56, 
                    group_writable = '', 
                    num_files = 56, 
                    hidden = '', 
                    immutable = '', 
                    archived = '', 
                    description = '', )
            )
        else:
            return UserfileModReq(
        )
        """

    def testUserfileModReq(self):
        """Test UserfileModReq"""
        # inst_req_only = self.make_instance(include_optional=False)
        # inst_req_and_optional = self.make_instance(include_optional=True)

if __name__ == '__main__':
    unittest.main()
