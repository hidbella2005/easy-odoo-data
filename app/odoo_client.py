"""Small, typed XML-RPC client for Odoo integrations.

The client deliberately keeps transport concerns here. Mapping and validation
belong in later pipeline modules, which makes this module useful from both
FastAPI and Streamlit.
"""

from __future__ import annotations

import logging
import xmlrpc.client
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin

LOGGER = logging.getLogger(__name__)


class OdooError(RuntimeError):
    """Raised when Odoo rejects a request or cannot be reached."""


@dataclass(frozen=True)
class OdooConfig:
    """Connection settings for an Odoo XML-RPC endpoint."""

    url: str
    database: str
    username: str
    password: str
    timeout: int = 30


class OdooClient:
    """Authenticated Odoo client with schema, lookup, and batch operations."""

    def __init__(self, config: OdooConfig) -> None:
        self.config = config
        base_url = config.url.rstrip("/")
        if base_url.lower().endswith("/odoo"):
            base_url = base_url[:-5].rstrip("/")
        base_url += "/"
        transport = _TimeoutTransport(config.timeout)
        self._common = xmlrpc.client.ServerProxy(
            urljoin(base_url, "xmlrpc/2/common"), transport=transport, allow_none=True
        )
        self._object = xmlrpc.client.ServerProxy(
            urljoin(base_url, "xmlrpc/2/object"), transport=transport, allow_none=True
        )
        self.uid: int | None = None

    def authenticate(self) -> int:
        """Authenticate and cache the Odoo user id."""
        try:
            uid = self._common.authenticate(
                self.config.database, self.config.username, self.config.password, {}
            )
        except (OSError, xmlrpc.client.ProtocolError, xmlrpc.client.Fault) as exc:
            raise OdooError(f"Odoo authentication request failed: {exc}") from exc
        if not isinstance(uid, int) or uid <= 0:
            raise OdooError("Odoo rejected the supplied database or credentials")
        self.uid = uid
        return uid

    def _execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        if self.uid is None:
            raise OdooError("Authenticate the Odoo client before making model requests")
        try:
            return self._object.execute_kw(
                self.config.database,
                self.uid,
                self.config.password,
                model,
                method,
                list(args),
                kwargs,
            )
        except (OSError, xmlrpc.client.ProtocolError, xmlrpc.client.Fault) as exc:
            raise OdooError(f"Odoo {model}.{method} request failed: {exc}") from exc

    def fields_get(
        self,
        model: str,
        attributes: Iterable[str] = (
            "string",
            "type",
            "required",
            "relation",
            "readonly",
        ),
    ) -> dict[str, dict[str, Any]]:
        """Return field metadata for a model, including relational targets."""
        if not model.strip():
            raise ValueError("model must not be empty")
        metadata = self._execute(model, "fields_get", attributes=list(attributes))
        if not isinstance(metadata, dict):
            raise OdooError(f"Odoo returned invalid field metadata for {model}")
        return metadata

    def search_read(
        self,
        model: str,
        domain: list[list[Any]] | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read records, primarily for relational lookup and previews."""
        if limit < 1:
            raise ValueError("limit must be positive")
        result = self._execute(
            model,
            "search_read",
            domain or [],
            fields=fields or ["id", "display_name"],
            limit=limit,
        )
        if not isinstance(result, list):
            raise OdooError(f"Odoo returned invalid search results for {model}")
        return result

    def resolve_many2one(
        self,
        model: str,
        value: str | int,
        *,
        lookup_field: str = "name",
        create_if_missing: bool = False,
    ) -> int:
        """Resolve a relational label to an Odoo id, without guessing silently."""
        if isinstance(value, bool) or (not isinstance(value, (str, int))):
            raise ValueError("many2one values must be a non-boolean string or integer")
        if isinstance(value, int):
            return value
        label = value.strip()
        if not label:
            raise ValueError("many2one lookup value must not be empty")
        records = self.search_read(
            model, [[lookup_field, "=", label]], fields=["id"], limit=2
        )
        if len(records) > 1:
            raise OdooError(f"Multiple {model} records match {lookup_field}={label!r}")
        if records:
            return int(records[0]["id"])
        if create_if_missing:
            return self.create(model, {lookup_field: label})
        raise OdooError(f"No {model} record found where {lookup_field}={label!r}")

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Create one record and return its id."""
        if not values:
            raise ValueError("values must not be empty")
        record_id = self._execute(model, "create", values)
        if not isinstance(record_id, int):
            raise OdooError(f"Odoo returned an invalid id while creating {model}")
        return record_id

    def create_batch(self, model: str, values: list[dict[str, Any]]) -> list[int]:
        """Create records in one XML-RPC call."""
        if not values:
            return []
        result = self._execute(model, "create", values)
        if isinstance(result, int):
            return [result]
        if not isinstance(result, list) or not all(isinstance(item, int) for item in result):
            raise OdooError(f"Odoo returned invalid ids while creating {model}")
        return result

    def write_batch(self, model: str, record_ids: list[int], values: dict[str, Any]) -> bool:
        """Write the same values to a batch of records."""
        if not record_ids:
            return True
        if not values:
            raise ValueError("values must not be empty")
        result = self._execute(model, "write", record_ids, values)
        if not isinstance(result, bool):
            raise OdooError(f"Odoo returned an invalid write result for {model}")
        return result


class _TimeoutTransport(xmlrpc.client.Transport):
    """Apply a bounded socket timeout to stdlib XML-RPC connections."""

    def __init__(self, timeout: int) -> None:
        super().__init__()
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout

    def make_connection(self, host: str) -> xmlrpc.client.HTTPConnection:
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection

