# coding: utf-8

"""
    CBRAIN API

    API for interacting with the CBRAIN Platform

    The version of the OpenAPI document: 6.2.0.1
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from typing import Any, ClassVar, Dict, List, Optional
from typing import Optional, Set
from typing_extensions import Self

class MultiRegistrationModReq(BaseModel):
    """
    MultiRegistrationModReq
    """ # noqa: E501
    basenames: Optional[List[StrictStr]] = None
    filetypes: Optional[List[StrictStr]] = Field(default=None, description="An array containing the filetypes associated with the files to register; each element must be a string containing the cbrain file type, a single dash, and then a repeat of the basename found in the basenames parameters. For example, \"TextFile-abc.txt\"")
    as_user_id: Optional[StrictInt] = Field(default=None, description="The ID of the user to register files as.")
    browse_path: Optional[StrictStr] = Field(default=None, description="A relative path such as \"abcd/efgh\" that can be provided when registering basenames deeper under the root of the DataProvider. This parameter only works for DataProvider types that have a 'multi-level' capability. Otherwise the string is ignored. The relative path will be used for all basenames in the current request.")
    other_group_id: Optional[StrictInt] = Field(default=None, description="The ID of the project controlling access to the registered files.")
    delete: Optional[StrictBool] = Field(default=False, description="Specifies to delete the file contents. This is only used during an \"unregister\" action.")
    __properties: ClassVar[List[str]] = ["basenames", "filetypes", "as_user_id", "browse_path", "other_group_id", "delete"]

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        protected_namespaces=(),
    )


    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        # TODO: pydantic v2: use .model_dump_json(by_alias=True, exclude_unset=True) instead
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> Optional[Self]:
        """Create an instance of MultiRegistrationModReq from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        This has the following differences from calling pydantic's
        `self.model_dump(by_alias=True)`:

        * `None` is only added to the output dict for nullable fields that
          were set at model initialization. Other fields with value `None`
          are ignored.
        """
        excluded_fields: Set[str] = set([
        ])

        _dict = self.model_dump(
            by_alias=True,
            exclude=excluded_fields,
            exclude_none=True,
        )
        return _dict

    @classmethod
    def from_dict(cls, obj: Optional[Dict[str, Any]]) -> Optional[Self]:
        """Create an instance of MultiRegistrationModReq from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "basenames": obj.get("basenames"),
            "filetypes": obj.get("filetypes"),
            "as_user_id": obj.get("as_user_id"),
            "browse_path": obj.get("browse_path"),
            "other_group_id": obj.get("other_group_id"),
            "delete": obj.get("delete") if obj.get("delete") is not None else False
        })
        return _obj


