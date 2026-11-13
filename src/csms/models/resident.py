"""Resident domain model."""

from dataclasses import dataclass


@dataclass
class Resident:
    """Represent a resident registered within the community."""

    first_name: str
    last_name: str
    address: str
    contact_number: str
    email: str
    status: str = "Active"
    id: int | None = None