"""Results format translation between Flink and Confluent."""

from typing import Any

from ..models.confluent import ChangelogRow, ResultsMetadata, StatementResults
from ..models.flink import FetchResultsResponse, RowData


def flink_row_kind_to_op(row_kind: str) -> int:
    """Convert Flink row kind to Confluent op code.

    Args:
        row_kind: Flink row kind (INSERT, UPDATE_BEFORE, UPDATE_AFTER, DELETE)

    Returns:
        Op code (0=INSERT, 1=UPDATE_BEFORE, 2=UPDATE_AFTER, 3=DELETE)
    """
    mapping = {
        "INSERT": 0,
        "+I": 0,
        "UPDATE_BEFORE": 1,
        "-U": 1,
        "UPDATE_AFTER": 2,
        "+U": 2,
        "DELETE": 3,
        "-D": 3,
    }

    return mapping.get(row_kind.upper(), 0)


def translate_flink_results_to_confluent(
    flink_response: FetchResultsResponse,
    statement_name: str,
    current_token: int,
) -> tuple[StatementResults, ResultsMetadata]:
    """Translate Flink results to Confluent format.

    Args:
        flink_response: Flink fetch results response
        statement_name: Statement name for generating next URL
        current_token: Current pagination token

    Returns:
        Tuple of (results, metadata)
    """
    results_data: list[ChangelogRow] = []

    if flink_response.results.data:
        for row_data in flink_response.results.data:
            op = flink_row_kind_to_op(row_data.kind)
            changelog_row = ChangelogRow(op=op, row=row_data.fields)
            results_data.append(changelog_row)

    results = StatementResults(data=results_data)

    # Construct next URL if there are more results
    next_url = None
    if flink_response.next_result_uri or flink_response.results.result_type != "EOS":
        # Increment token for next page
        next_token = current_token + 1
        # Construct relative URL (will be turned into full URL by response handler)
        next_url = f"/statements/{statement_name}/results?token={next_token}"

    metadata = ResultsMetadata(next=next_url)

    return results, metadata
