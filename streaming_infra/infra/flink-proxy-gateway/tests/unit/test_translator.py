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

"""Unit tests for translator modules."""

import pytest

from flink_gateway_proxy.translator.status import (
    confluent_phase_to_flink_status,
    flink_status_to_confluent_phase,
)
from flink_gateway_proxy.translator.traits import infer_is_bounded, infer_sql_kind


def test_flink_status_to_confluent_phase():
    """Test Flink status to Confluent phase translation."""
    assert flink_status_to_confluent_phase("INITIALIZED") == "PENDING"
    assert flink_status_to_confluent_phase("PENDING") == "PENDING"
    assert flink_status_to_confluent_phase("RUNNING") == "RUNNING"
    assert flink_status_to_confluent_phase("FINISHED") == "COMPLETED"
    assert flink_status_to_confluent_phase("CANCELED") == "STOPPED"
    assert flink_status_to_confluent_phase("CLOSED") == "STOPPED"
    assert flink_status_to_confluent_phase("ERROR") == "FAILED"
    assert flink_status_to_confluent_phase("UNKNOWN") == "FAILED"


def test_confluent_phase_to_flink_status():
    """Test Confluent phase to Flink status translation."""
    assert confluent_phase_to_flink_status("PENDING") == "PENDING"
    assert confluent_phase_to_flink_status("RUNNING") == "RUNNING"
    assert confluent_phase_to_flink_status("COMPLETED") == "FINISHED"
    assert confluent_phase_to_flink_status("STOPPED") == "CANCELED"
    assert confluent_phase_to_flink_status("FAILED") == "ERROR"


def test_infer_sql_kind():
    """Test SQL kind inference."""
    assert infer_sql_kind("SELECT * FROM users") == "SELECT"
    assert infer_sql_kind("select * from users") == "SELECT"
    assert infer_sql_kind("CREATE TABLE foo (id INT)") == "CREATE_TABLE"
    assert infer_sql_kind("DROP TABLE foo") == "DROP_TABLE"
    assert infer_sql_kind("INSERT INTO foo VALUES (1)") == "INSERT"
    assert infer_sql_kind("SHOW TABLES") == "SHOW"
    assert infer_sql_kind("DESCRIBE foo") == "DESCRIBE"
    assert infer_sql_kind("CREATE VIEW bar AS SELECT *") == "CREATE_VIEW"
    assert infer_sql_kind("ALTER TABLE foo ADD COLUMN bar INT") == "ALTER_TABLE"


def test_infer_is_bounded():
    """Test bounded inference."""
    # Snapshot mode is bounded
    assert infer_is_bounded({"sql.snapshot.mode": "now"}, "SELECT") is True

    # DDL is bounded
    assert infer_is_bounded({}, "CREATE_TABLE") is True
    assert infer_is_bounded({}, "DROP_TABLE") is True
    assert infer_is_bounded({}, "INSERT") is True

    # SHOW/DESCRIBE is bounded
    assert infer_is_bounded({}, "SHOW") is True
    assert infer_is_bounded({}, "DESCRIBE") is True

    # Streaming SELECT is unbounded
    assert infer_is_bounded({}, "SELECT") is False
