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

"""Unit tests for state store."""

from datetime import datetime, timezone

import pytest

from flink_gateway_proxy.state.store import StatementRecord, StateStore


@pytest.mark.asyncio
async def test_state_store_add_get():
    """Test adding and getting records."""
    store = StateStore()

    record = StatementRecord(
        name="test-stmt",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-1",
        sql="SELECT 1",
        properties={},
        labels={},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    await store.add(record)

    retrieved = await store.get("test-stmt")
    assert retrieved is not None
    assert retrieved.name == "test-stmt"
    assert retrieved.org_id == "org-1"
    assert retrieved.phase == "PENDING"


@pytest.mark.asyncio
async def test_state_store_update():
    """Test updating records."""
    store = StateStore()

    record = StatementRecord(
        name="test-stmt",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-1",
        sql="SELECT 1",
        properties={},
        labels={},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    await store.add(record)
    await store.update("test-stmt", phase="RUNNING")

    retrieved = await store.get("test-stmt")
    assert retrieved is not None
    assert retrieved.phase == "RUNNING"


@pytest.mark.asyncio
async def test_state_store_delete():
    """Test deleting records."""
    store = StateStore()

    record = StatementRecord(
        name="test-stmt",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-1",
        sql="SELECT 1",
        properties={},
        labels={},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    await store.add(record)
    await store.delete("test-stmt")

    retrieved = await store.get("test-stmt")
    assert retrieved is None


@pytest.mark.asyncio
async def test_state_store_list_by_labels():
    """Test listing by labels."""
    store = StateStore()

    record1 = StatementRecord(
        name="stmt-1",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-1",
        sql="SELECT 1",
        properties={},
        labels={"user.confluent.io/batch": "true"},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    record2 = StatementRecord(
        name="stmt-2",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-2",
        sql="SELECT 2",
        properties={},
        labels={"user.confluent.io/batch": "true"},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    record3 = StatementRecord(
        name="stmt-3",
        org_id="org-1",
        env_id="env-1",
        session_handle="session-1",
        operation_handle="op-3",
        sql="SELECT 3",
        properties={},
        labels={"user.confluent.io/other": "true"},
        phase="PENDING",
        traits=None,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id="pool-1",
        principal="user-1",
    )

    await store.add(record1)
    await store.add(record2)
    await store.add(record3)

    results = await store.list_by_labels({"user.confluent.io/batch": "true"})
    assert len(results) == 2
    assert all(r.labels.get("user.confluent.io/batch") == "true" for r in results)
