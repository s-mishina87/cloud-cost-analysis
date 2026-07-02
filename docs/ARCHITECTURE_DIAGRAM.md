# Cloud Cost Analysis Prototype - Code-Aligned Data Flow Diagram

```mermaid
flowchart TD
    M0[src/main.py\nRun local pipeline]

    M1[src/data_generator.py\nGenerate synthetic data]
    S1[projects]
    S2[clusters]
    S3[namespaces]
    S4[namespace_costs\ncost_date, usage_cost, overhead_cost=0, total_cost=usage]
    S5[cluster_overheads\ncluster_overhead_cost per day]

    M2[src/allocation.py\nApply overhead allocation]
    S6[allocated_costs\nusage_cost + overhead_cost = total_cost]

    M3[src/anomaly_detection.py\nDetect anomalies on total_cost]
    S7[anomalies\nactual_value, baseline_value, threshold_value, anomaly_ref_key]

    M4[src/alerting.py\nGenerate notifications]
    S8[notifications\nseverity, status, message, anomaly_ref_key]

    M5[src/storage.py\nPersist pipeline data]
    DB[(SQLite: data/cloud_costs.db)]

    T1[Project]
    T2[Cluster]
    T3[Namespace]
    T4[NamespaceCost]
    T5[Anomaly]
    T6[Notification]

    M0 --> M1

    M1 --> S1
    M1 --> S2
    M1 --> S3
    M1 --> S4
    M1 --> S5

    S4 --> M2
    S5 --> M2
    M2 --> S6

    S6 --> M3
    M3 --> S7

    S7 --> M4
    M4 --> S8

    S1 --> M5
    S2 --> M5
    S3 --> M5
    S6 --> M5
    S7 --> M5
    S8 --> M5

    M5 --> DB
    DB --> T1
    DB --> T2
    DB --> T3
    DB --> T4
    DB --> T5
    DB --> T6
```

## End-to-End Model

Project -> Cluster -> Namespace -> NamespaceCost (usage + overhead = total) -> Anomaly -> Notification

Teams delivery was considered, but the final demo uses email notifications because no suitable Teams webhook was available.
