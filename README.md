# Cloud Costs Analysis (Prototype)

This project is a local prototype for cloud cost analysis and anomaly detection.

It uses synthetic data, stores results in SQLite, and shows them in a Streamlit dashboard.
Email is optional and used only for one summary after the pipeline run.

## What this project does

The pipeline simulates cloud costs for projects, clusters, and namespaces.
Then it splits overhead, detects anomalies, creates notifications, stores everything in SQLite, and shows results.

It is not connected to real cloud billing APIs, and it is not real-time monitoring.

## Features

- Synthetic cloud cost generation with a fixed random seed, so demos and tests give the same results
- Cluster overhead split across namespaces
- Anomaly detection with moving average and threshold
- Notification generation for important anomalies
- Local SQLite storage for all pipeline data
- Streamlit dashboard for cost and anomaly visualization
- Optional summary email delivery via SMTP

## Project structure

```text
.
|- src/
|  |- alerting.py
|  |- allocation.py
|  |- anomaly_detection.py
|  |- dashboard.py
|  |- data_generator.py
|  |- email_notifier.py
|  |- main.py
|  |- paths.py
|  \- storage.py
\- tests/
```

## Pipeline overview

main.py starts the pipeline and calls these modules in order.

1. data_generator.py  
	Creates synthetic project, cluster, namespace, cost, and overhead data.

2. allocation.py  
	Splits cluster overhead costs across namespaces.

3. anomaly_detection.py  
	Detects anomalies using a moving average and a threshold.

4. alerting.py  
	Creates notifications from important anomalies.

5. storage.py  
	Stores projects, clusters, namespaces, costs, anomalies, and notifications in SQLite.

6. email_notifier.py  
	Sends one email summary if SMTP is configured.

7. dashboard.py  
	Reads SQLite data and shows costs and anomalies in Streamlit.

## Data model

Project -> Cluster -> Namespace -> NamespaceCost -> Anomaly -> Notification

Why namespace is the smallest analysis level:
- Namespace gives a clear boundary between workloads in one cluster.
- It is detailed enough to find spikes, but still simple to understand.

## Data generator notes

data_generator.py creates synthetic cloud cost data for local testing and demo.

It creates:
- Projects
- Clusters
- Namespaces
- Daily namespace costs (usage_cost)
- Daily cluster overhead values (allocated later by allocation.py)

Important behavior:
- A fixed seed is used, so tests and demos stay consistent.
- Includes system namespaces and application namespaces.
- System namespaces are more stable.
- Application namespaces fluctuate more.
- Includes intentional anomaly scenarios:
  - payments spike
  - monitoring gradual increase
  - checkout temporary jump

## Anomaly detection method

Each namespace is checked separately day by day.

For each day, the script:
1. Looks at the previous 7 days.
2. Calculates a moving average as the normal level.
3. Calculates threshold = moving_average * 1.5.
4. Detects anomaly if actual_value > threshold.

Severity (How strong is the anomaly?):
- HIGH if actual_value / threshold >= 2.0
- MEDIUM if actual_value / threshold >= 1.3
- LOW otherwise

Extra change info:
- daily_change
- average_absolute_change
- change_threshold
- is_fast_change

This can later be shown as change type:
- FAST_CHANGE
- GRADUAL_CHANGE

Change type answers this question: How did the anomaly develop?

## Notification and email behavior

alerting.py:
- Creates notification records from anomaly results.
- Does not send emails.

email_notifier.py:
- Is optional.
- Does not detect anomalies.
- Does not create notifications.
- Does not read notifications from SQLite.
- Gets the prepared notifications list from the pipeline.
- If SMTP is configured, sends one summary email.
- If SMTP is not configured, pipeline still works and email is skipped.

## Installation

1. Create and activate a virtual environment.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

## Run the pipeline

```powershell
python -m src.main
```

This generates synthetic data, runs the full pipeline, and stores results in:

data/cloud_costs.db

## Run the dashboard

```powershell
python -m streamlit run src/dashboard.py
```

## Optional email setup

Create a local .env file in the project root (do not push it to GitHub):

I removed my real SMTP password from this project for safety.

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=YOUR_SMTP_PASSWORD_HERE
SMTP_FROM=your-email@example.com
SMTP_TO=recipient1@example.com,recipient2@example.com
```

If these values are missing, email is skipped and the pipeline still finishes.

