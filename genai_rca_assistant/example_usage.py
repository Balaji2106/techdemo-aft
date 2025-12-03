"""
Example usage of ADF Auto-Remediation
"""
from adf_auto_remediation import remediate_adf_pipeline, is_auto_solvable

# Example 1: Check if error is auto-solvable
error_message = "UserErrorSourceBlobNotExists: The specified blob does not exist"
error_code = "UserErrorSourceBlobNotExists"

if is_auto_solvable(error_message, error_code):
    print("Error is auto-solvable, triggering remediation...")

    # Example 2: Remediate pipeline
    result = remediate_adf_pipeline(
        pipeline_name="my_data_pipeline",
        factory_name="my-adf-factory",
        resource_group="my-resource-group",
        error_message=error_message,
        error_code=error_code,
        ticket_id="TICKET-12345"
    )

    print(f"Remediation result: {result}")
    print(f"Success: {result['success']}")
    print(f"Final status: {result['final_status']}")
    print(f"Message: {result['message']}")
    print(f"Run IDs: {result['run_ids']}")
    print(f"Ticket updated: {result['ticket_updated']}")
else:
    print("Error is not auto-solvable, manual intervention required")
