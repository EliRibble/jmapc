from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

import requests
import sseclient

from . import constants, errors
from .auth import BearerAuth
from .logging import log
from .methods import CustomResponse, Method, Response
from .models import Event
from .session import Session

MethodList = List[Tuple[str, Method]]
MethodResponseOrError = Union[errors.Error, Response]
MethodResponseList = List[Tuple[str, MethodResponseOrError]]
MethodCallResponseOrList = Union[
    MethodResponseOrError, List[MethodResponseOrError]
]
RequestsAuth = Union[requests.auth.AuthBase, Tuple[str, str]]


@dataclass
class EventSourceConfig:
    types: str = "*"
    closeafter: Literal["state", "no"] = "no"
    ping: int = 0


class Client:
    @classmethod
    def create_with_api_token(
        cls, host: str, api_token: str, *args: Any, **kwargs: Any
    ) -> Client:
        kwargs["auth"] = BearerAuth(api_token)
        return cls(host, *args, **kwargs)

    @classmethod
    def create_with_password(
        cls, host: str, user: str, password: str, *args: Any, **kwargs: Any
    ) -> Client:
        kwargs["auth"] = requests.auth.HTTPBasicAuth(
            username=user, password=password
        )
        return cls(host, *args, **kwargs)

    def __init__(
        self,
        host: str,
        auth: Optional[RequestsAuth] = None,
        last_event_id: Optional[str] = None,
        event_source_config: Optional[EventSourceConfig] = None,
    ) -> None:
        self._host: str = host
        self._auth: Optional[RequestsAuth] = auth
        self._last_event_id: Optional[str] = last_event_id
        self._event_source_config: EventSourceConfig = (
            event_source_config or EventSourceConfig()
        )
        self._jmap_session: Optional[Session] = None
        self._requests_session: Optional[requests.Session] = None
        self._events: Optional[sseclient.SSEClient] = None

    @property
    def events(self) -> Generator[Event, None, None]:
        if not self._events:
            self._events = sseclient.SSEClient(
                self.jmap_session.event_source_url.format(
                    **asdict(self._event_source_config)
                ),
                auth=self.requests_session.auth,
                last_id=self._last_event_id,
            )
        for event in self._events:
            if not event.id or event.event != "state":
                continue
            yield Event.load_from_sseclient_event(event)

    @property
    def requests_session(self) -> requests.Session:
        if not self._requests_session:
            self._requests_session = requests.Session()
            self._requests_session.auth = self._auth
        return self._requests_session

    @property
    def jmap_session(self) -> Session:
        if not self._jmap_session:
            r = self.requests_session.get(
                f"https://{self._host}/.well-known/jmap"
            )
            r.raise_for_status()
            self._jmap_session = Session.from_dict(r.json())
        return self._jmap_session

    @property
    def account_id(self) -> str:
        return self.jmap_session.primary_accounts.mail

    def method_call(
        self, method: Method, flatten_single_response: bool = True
    ) -> MethodCallResponseOrList:
        using = list(set([constants.JMAP_URN_CORE]).union(method.using))
        results = self._api_request(
            {
                "using": sorted(using),
                "methodCalls": [
                    [
                        method.name,
                        method.to_dict(account_id=self.account_id),
                        "uno",
                    ]
                ],
            },
        )
        # One method call may result in multiple responses for that call.
        # If there is a single response, return the response object.
        # Otherwise, return the list of responses.
        if len(results) == 1:
            return results[0][1]
        return [result[1] for result in results]

    def method_calls(
        self, calls: Union[list[Method], MethodList]
    ) -> MethodResponseList:
        if isinstance(calls[0], Method):
            just_calls = cast(List[Method], calls)
            calls = [(str(i), method) for i, method in enumerate(just_calls)]
        calls = cast(MethodList, calls)
        using = list(
            set([constants.JMAP_URN_CORE]).union(*[c[1].using for c in calls])
        )
        return self._api_request(
            {
                "using": sorted(using),
                "methodCalls": [
                    [
                        c[1].name,
                        c[1].to_dict(account_id=self.account_id),
                        c[0],
                    ]
                    for c in calls
                ],
            },
        )

    def _api_request(self, request: Dict[str, Any]) -> MethodResponseList:
        log.debug(f"Sending JMAP request {json.dumps(request)}")
        r = self.requests_session.post(
            self.jmap_session.api_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(request),
        )
        r.raise_for_status()
        log.debug(f"Received JMAP response {r.text}")
        return self._parse_responses(r.json())

    def _response_type(self, method_name: str) -> Type[MethodResponseOrError]:
        if method_name == "error":
            return errors.Error
        if method_name in Response.response_types:
            return Response.response_types[method_name]
        return CustomResponse

    def _parse_responses(self, data: dict[str, Any]) -> MethodResponseList:

        method_responses = cast(
            List[Tuple[str, Dict[str, Any], str]],
            data.get("methodResponses", []),
        )
        responses: MethodResponseList = []
        for name, response, method_id in method_responses:
            responses.append(
                (
                    method_id,
                    self._response_type(name).from_dict(response),
                )
            )
        return responses
