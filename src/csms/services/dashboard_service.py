"""CSMS Dashboard query service (T14).

This module provides :class:`DashboardService`, which composes and returns
dashboard summary information from existing persisted Resident and Service
Request data.

Responsibilities:

* Query persisted Resident aggregate data.
* Query persisted Service Request aggregate data.
* Derive Open Service Requests from persistent statuses.
* Retrieve recent Service Requests.
* Return a dashboard summary object.

What this service intentionally does NOT do:

* Modify any Resident or Service Request.
* Perform validation.
* Render HTML or views.
* Store dashboard data in a separate table.
* Generate or cache counters.
* Write SQL directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository


@dataclass
class ResidentSummary:
    """Summary statistics for Residents.

    Attributes:
        total:    Total number of Residents (Active + Inactive).
        active:   Number of Active Residents.
        inactive: Number of Inactive Residents.
    """

    total: int
    active: int
    inactive: int


@dataclass
class ServiceRequestSummary:
    """Summary statistics for Service Requests by status.

    Attributes:
        total:       Total number of Service Requests.
        pending:     Number of Pending requests.
        in_progress: Number of In Progress requests.
        completed:   Number of Completed requests.
        cancelled:   Number of Cancelled requests.
        open:        Number of Open requests (Pending + In Progress).
    """

    total: int
    pending: int
    in_progress: int
    completed: int
    cancelled: int
    open: int


@dataclass
class DashboardSummary:
    """Complete CSMS dashboard summary.

    Attributes:
        residents:           Resident aggregate statistics.
        service_requests:    Service Request aggregate statistics.
        recent_requests:     The five most recent Service Requests.
    """

    residents: ResidentSummary
    service_requests: ServiceRequestSummary
    recent_requests: list[ServiceRequest]


class DashboardService:
    """Compose CSMS dashboard information from persisted data.

    Args:
        resident_repository:       Repository for Resident queries.
        service_request_repository: Repository for Service Request queries.
    """

    def __init__(
        self,
        resident_repository: ResidentRepository,
        service_request_repository: ServiceRequestRepository,
    ) -> None:
        self._resident_repo = resident_repository
        self._sr_repo = service_request_repository

    def get_dashboard_summary(self) -> DashboardSummary:
        """Retrieve complete dashboard summary.

        Returns:
            A :class:`DashboardSummary` containing Resident metrics,
            Service Request metrics, and recent Service Requests.
        """
        # Resident metrics
        residents = self._get_resident_summary()

        # Service Request metrics
        service_requests = self._get_service_request_summary()

        # Recent Service Requests
        recent_requests = self._sr_repo.find_recent(limit=5)

        return DashboardSummary(
            residents=residents,
            service_requests=service_requests,
            recent_requests=recent_requests,
        )

    def _get_resident_summary(self) -> ResidentSummary:
        """Compose Resident aggregate statistics."""
        total = self._resident_repo.count_all()
        active = self._resident_repo.count_by_status("Active")
        inactive = self._resident_repo.count_by_status("Inactive")

        return ResidentSummary(
            total=total,
            active=active,
            inactive=inactive,
        )

    def _get_service_request_summary(self) -> ServiceRequestSummary:
        """Compose Service Request aggregate statistics."""
        total = self._sr_repo.count_all()
        pending = self._sr_repo.count_by_status("Pending")
        in_progress = self._sr_repo.count_by_status("In Progress")
        completed = self._sr_repo.count_by_status("Completed")
        cancelled = self._sr_repo.count_by_status("Cancelled")
        open_count = pending + in_progress

        return ServiceRequestSummary(
            total=total,
            pending=pending,
            in_progress=in_progress,
            completed=completed,
            cancelled=cancelled,
            open=open_count,
        )
