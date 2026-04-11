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

"""Status translation between Flink Gateway and Confluent API."""


def flink_status_to_confluent_phase(flink_status: str) -> str:
    """Translate Flink SQL Gateway status to Confluent phase.

    Args:
        flink_status: Flink status (INITIALIZED, PENDING, RUNNING, FINISHED, CANCELED, CLOSED, ERROR)

    Returns:
        Confluent phase (PENDING, RUNNING, COMPLETED, STOPPED, FAILED)
    """
    mapping = {
        "INITIALIZED": "PENDING",
        "PENDING": "PENDING",
        "RUNNING": "RUNNING",
        "FINISHED": "COMPLETED",
        "CANCELED": "STOPPED",
        "CLOSED": "STOPPED",
        "ERROR": "FAILED",
    }

    return mapping.get(flink_status, "FAILED")


def confluent_phase_to_flink_status(confluent_phase: str) -> str:
    """Translate Confluent phase to Flink SQL Gateway status.

    Args:
        confluent_phase: Confluent phase

    Returns:
        Flink status
    """
    mapping = {
        "PENDING": "PENDING",
        "RUNNING": "RUNNING",
        "COMPLETED": "FINISHED",
        "STOPPED": "CANCELED",
        "FAILED": "ERROR",
    }

    return mapping.get(confluent_phase, "ERROR")
