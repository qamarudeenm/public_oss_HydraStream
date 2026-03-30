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
