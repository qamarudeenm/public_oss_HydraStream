# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Statement request/response translation."""

import uuid
from datetime import datetime, timezone

from ..models.confluent import (
    ScalingStatus,
    StatementMetadata,
    StatementResponse,
    StatementSpec,
    StatementStatus,
    StatementTraits,
)
from ..state.store import StatementRecord


def build_statement_response(
    record: StatementRecord,
    base_url: str,
) -> StatementResponse:
    """Build a Confluent statement response from a statement record.

    Args:
        record: Statement record from state store
        base_url: Base URL for constructing self link

    Returns:
        Confluent statement response
    """
    # Build metadata
    metadata = StatementMetadata(
        uid=str(uuid.uuid4()),  # Generate a UID
        created_at=record.created_at,
        updated_at=datetime.now(timezone.utc),
        labels=record.labels,
        self=f"{base_url}/sql/v1/organizations/{record.org_id}/environments/{record.env_id}/statements/{record.name}",
        resource_version="1",
    )

    # Build spec
    spec = StatementSpec(
        statement=record.sql,
        properties=record.properties,
        compute_pool_id=record.compute_pool_id,
        stopped=record.stopped,
        principal=record.principal,
    )

    # Build traits (if available)
    traits = None
    if record.traits:
        traits = StatementTraits(**record.traits)

    # Build scaling status
    scaling_status = ScalingStatus(
        scaling_state="OK",
        last_updated=datetime.now(timezone.utc),
    )

    # Build status
    status = StatementStatus(
        phase=record.phase,
        detail=record.detail,
        traits=traits,
        network_kind="PUBLIC",
        scaling_status=scaling_status,
    )

    # Build full response
    return StatementResponse(
        api_version="sql/v1",
        kind="Statement",
        name=record.name,
        organization_id=record.org_id,
        environment_id=record.env_id,
        metadata=metadata,
        spec=spec,
        status=status,
    )
