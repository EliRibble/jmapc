from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .. import constants
from .base import Method, Response
from ..serializer import null_omitted_field


class CoreBase:
    method_namespace: Optional[str] = "Core"
    using = {constants.JMAP_URN_CORE}


class EchoMethod:
    method_type: Optional[str] = "echo"


@dataclass
class CoreEcho(CoreBase, EchoMethod, Method):
    def to_dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self.data or dict()

    data: Optional[Dict[str, Any]] = null_omitted_field()


@dataclass
class CoreEchoResponse(CoreBase, EchoMethod, Response):
    data: Optional[Dict[str, Any]] = null_omitted_field()

    @classmethod
    def from_dict(
        cls, kvs: Any, *args: Any, **kwargs: Any
    ) -> CoreEchoResponse:
        return CoreEchoResponse(data=kvs)
