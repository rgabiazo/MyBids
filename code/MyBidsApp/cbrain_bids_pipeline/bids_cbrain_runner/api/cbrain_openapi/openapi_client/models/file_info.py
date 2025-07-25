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

class FileInfo(BaseModel):
    """
    FileInfo
    """ # noqa: E501
    userfile_id: Optional[StrictInt] = Field(default=None, description="id of the userfile")
    name: Optional[StrictStr] = Field(default=None, description="the base filename")
    group: Optional[StrictStr] = Field(default=None, description="string representation of gid, the name of the group")
    gid: Optional[StrictInt] = Field(default=None, description="numeric group id of the file")
    owner: Optional[StrictStr] = Field(default=None, description="string representation of uid, the name of the owner")
    uid: Optional[StrictInt] = Field(default=None, description="numeric uid of owner")
    permissions: Optional[StrictInt] = Field(default=None, description="an int interpreted in octal, e.g. 0640")
    size: Optional[StrictInt] = Field(default=None, description="size of file in bytes")
    state_ok: Optional[StrictBool] = Field(default=None, description="flag that tell whether or not it is OK to register/unregister")
    message: Optional[StrictStr] = Field(default=None, description="a message to give more information about the state_ok flag")
    symbolic_type: Optional[StrictStr] = Field(default=None, description="one of :regular, :symlink, :directory")
    atime: Optional[StrictInt] = Field(default=None, description="access time (an int, since Epoch)")
    mtime: Optional[StrictInt] = Field(default=None, description="modification time (an int, since Epoch)")
    __properties: ClassVar[List[str]] = ["userfile_id", "name", "group", "gid", "owner", "uid", "permissions", "size", "state_ok", "message", "symbolic_type", "atime", "mtime"]

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
        """Create an instance of FileInfo from a JSON string"""
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
        """Create an instance of FileInfo from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "userfile_id": obj.get("userfile_id"),
            "name": obj.get("name"),
            "group": obj.get("group"),
            "gid": obj.get("gid"),
            "owner": obj.get("owner"),
            "uid": obj.get("uid"),
            "permissions": obj.get("permissions"),
            "size": obj.get("size"),
            "state_ok": obj.get("state_ok"),
            "message": obj.get("message"),
            "symbolic_type": obj.get("symbolic_type"),
            "atime": obj.get("atime"),
            "mtime": obj.get("mtime")
        })
        return _obj


