"""Detect cost anomalies for each namespace."""


def _avg_abs_change(rows):
    if len(rows) < 2:
        return 0.0
    changes = [abs(float(rows[i]["total_cost"]) - float(rows[i - 1]["total_cost"])) for i in range(1, len(rows))]
    return sum(changes) / len(changes)


def severity_from_ratio(actual, threshold):
    if threshold <= 0:
        return "MEDIUM"
    ratio = actual / threshold
    if ratio >= 2.0:
        return "HIGH"
    if ratio >= 1.3:
        return "MEDIUM"
    return "LOW"


def detect_anomalies(records, window_size: int = 7, deviation_factor: float = 1.5, change_factor: float = 2.0):
    """Detect anomalies using a moving average threshold."""
    if not records:
        return []
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if change_factor <= 0:
        raise ValueError("change_factor must be > 0")

    grouped = {}
    for row in records:
        ns_key = (row["project_name"], row["cluster_name"], row["namespace_name"])
        grouped.setdefault(ns_key, []).append(row)

    anomalies = []
    for _, ns_rows in grouped.items():
        sort_rows = sorted(ns_rows, key=lambda r: r["cost_date"])

        for i in range(window_size, len(sort_rows)):
            history = sort_rows[i - window_size:i]
            baseline = sum(float(r["total_cost"]) for r in history) / window_size
            threshold = baseline * deviation_factor
            actual = float(sort_rows[i]["total_cost"])

            if actual > threshold:
                source = sort_rows[i]
                d_change = actual - float(sort_rows[i - 1]["total_cost"])
                avg_change = _avg_abs_change(history)
                chg_thr = avg_change * change_factor
                is_fast = abs(d_change) > chg_thr

                if d_change == 0:
                    chg_type = "NO_SIGNIFICANT_CHANGE"
                elif is_fast:
                    chg_type = "FAST_CHANGE"
                else:
                    chg_type = "GRADUAL_CHANGE"

                anomalies.append({
                    "cost_date": source["cost_date"],
                    "project_name": source["project_name"],
                    "cluster_name": source["cluster_name"],
                    "namespace_name": source["namespace_name"],
                    "anomaly_ref_key": (
                        f"{source['cost_date']}|{source['project_name']}|"
                        f"{source['cluster_name']}|{source['namespace_name']}|moving_average_threshold"
                    ),
                    "method": "moving_average_threshold",
                    "actual_value": round(actual, 2),
                    "moving_average": round(baseline, 2),
                    "threshold_value": round(threshold, 2),
                    "severity": severity_from_ratio(actual, threshold),
                    "is_anomaly": 1,
                    "daily_change": round(d_change, 2),
                    "average_absolute_change": round(avg_change, 2),
                    "change_threshold": round(chg_thr, 2),
                    "is_fast_change": is_fast,
                    "change_type": chg_type,
                })

    return anomalies
