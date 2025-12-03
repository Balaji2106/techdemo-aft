# ADF Auto-Remediation with Logic Apps

Clean implementation of Azure Data Factory pipeline auto-remediation using Logic Apps.

## Setup

```bash
cd genai_rca_assistant
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Logic App webhook URL
```

## Usage

```python
from adf_auto_remediation import remediate_adf_pipeline

result = remediate_adf_pipeline(
    pipeline_name="your_pipeline",
    factory_name="your-adf",
    resource_group="your-rg",
    error_message="UserErrorSourceBlobNotExists",
    error_code="UserErrorSourceBlobNotExists",
    ticket_id="TICKET-123"
)

print(result)
```

## Test

```bash
python adf_auto_remediation.py
```

## Flow

1. Check if error is auto-solvable
2. Trigger Logic App to create pipeline run
3. Monitor pipeline status
4. If fails again after retries: mark ticket as "auto-remediation applied still problem"
5. If succeeds: mark ticket as resolved
