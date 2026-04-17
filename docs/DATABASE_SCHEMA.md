# Cloud Costs Analysis - Datenbankschema

## Übersicht aller Tabellen und Verbindungen

Das SQLite-System basiert auf 6 Tabellen, die in einer hierarchischen Struktur verbunden sind:

```
Project (oben)
   ↓ (1:N)
Cluster
   ↓ (1:N)
Namespace
   ↓ (1:N)
NamespaceCost
   ↓ (1:N)
Anomaly
   ↓ (1:N)
Notification (unten)
```

---

## Tabelle 1: Project

**Zweck:** Speichert die Top-Level Cloud-Projekte

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Projekt-ID |
| `project_name` | TEXT | NOT NULL, UNIQUE | Name des Projekts (z.B. "retail-prod") |

**Beispielzeile:**
```
id=1, project_name="retail-prod"
id=2, project_name="platform-prod"
```

**Key:**
- Primary Key: `id`
- Unique Constraint: `project_name` (ein Projektname darf nicht zweimal vorkommen)

---

## Tabelle 2: Cluster

**Zweck:** Speichert Kubernetes-Cluster, die zu Projekten gehören

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Cluster-ID |
| `cluster_name` | TEXT | NOT NULL | Name des Clusters (z.B. "main") |
| `project_id` | INTEGER | NOT NULL, FOREIGN KEY | Verweis auf Project.id |
| - | - | UNIQUE(cluster_name, project_id) | Pro Projekt darf ein Cluster nur einmal vorkommen |

**Beispielzeile:**
```
id=1, cluster_name="main", project_id=1
id=2, cluster_name="shared", project_id=1
id=3, cluster_name="main", project_id=2
```

**Keys:**
- Primary Key: `id`
- Foreign Key: `project_id` → `Project.id`
- Unique Constraint: Kombination `(cluster_name, project_id)`

**Verbindung zu Project:**
- `cluster_id=1` gehört zu `project_id=1` ("retail-prod")
- `cluster_id=2` gehört zu `project_id=1` ("retail-prod")
- `cluster_id=3` gehört zu `project_id=2` ("platform-prod")

---

## Tabelle 3: Namespace

**Zweck:** Speichert Kubernetes Namespaces innerhalb von Clustern

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Namespace-ID |
| `namespace_name` | TEXT | NOT NULL | Name (z.B. "payments", "monitoring") |
| `cluster_id` | INTEGER | NOT NULL, FOREIGN KEY | Verweis auf Cluster.id |
| - | - | UNIQUE(namespace_name, cluster_id) | Pro Cluster darf ein Namespace nur einmal vorkommen |

**Beispielzeile:**
```
id=1, namespace_name="payments", cluster_id=1
id=2, namespace_name="checkout", cluster_id=1
id=3, namespace_name="monitoring", cluster_id=1
id=4, namespace_name="payments", cluster_id=2
```

**Keys:**
- Primary Key: `id`
- Foreign Key: `cluster_id` → `Cluster.id`
- Unique Constraint: Kombination `(namespace_name, cluster_id)`

**Verbindung zu Cluster:**
- `namespace_id=1,2,3` gehören zu `cluster_id=1` ("main" in "retail-prod")
- `namespace_id=4` gehört zu `cluster_id=2` ("shared" in "retail-prod")

---

## Tabelle 4: NamespaceCost

**Zweck:** Speichert tägliche Kosten für jeden Namespace (mit Allocation)

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Cost-Record-ID |
| `cost_date` | TEXT | NOT NULL | Datum (ISO format, z.B. "2026-04-01") |
| `namespace_id` | INTEGER | NOT NULL, FOREIGN KEY | Verweis auf Namespace.id |
| `usage_cost` | REAL | NOT NULL | Direkte Kosten des Namespace |
| `overhead_cost` | REAL | NOT NULL | Zugeordneter Anteil Cluster Overhead |
| `total_cost` | REAL | NOT NULL | usage_cost + overhead_cost |

**Beispielzeile:**
```
id=101, cost_date="2026-04-01", namespace_id=1, usage_cost=80.00, overhead_cost=16.00, total_cost=96.00
id=102, cost_date="2026-04-01", namespace_id=2, usage_cost=40.00, overhead_cost=8.00, total_cost=48.00
id=103, cost_date="2026-04-02", namespace_id=1, usage_cost=75.00, overhead_cost=15.00, total_cost=90.00
```

**Keys:**
- Primary Key: `id`
- Foreign Key: `namespace_id` → `Namespace.id`

**Wichtig:**
- Hier findet die **Allocation statt**: `overhead_cost` ist das Ergebnis von `allocation.py`
- `total_cost` ist das, was `anomaly_detection.py` analysiert (nicht nur `usage_cost`)

**Verbindung zu Namespace:**
- `namespace_id=1` sind alle Kosten für "payments" in "main"/"retail-prod"
- `namespace_id=2` sind alle Kosten für "checkout" in "main"/"retail-prod"

---

## Tabelle 5: Anomaly

**Zweck:** Speichert erkannte Kostenanomalien

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Anomaly-ID |
| `namespace_cost_id` | INTEGER | NOT NULL, FOREIGN KEY | Verweis auf NamespaceCost.id |
| `anomaly_date` | TEXT | NOT NULL | Datum der Anomalie (ISO format) |
| `method` | TEXT | NOT NULL | Erkennungsmethode (z.B. "moving_average_threshold") |
| `actual_value` | REAL | NOT NULL | Tatsächliche total_cost an diesem Tag |
| `baseline_value` | REAL | NOT NULL | Normales Niveau (7-Tage-Durchschnitt) |
| `threshold_value` | REAL | NOT NULL | Schwelle (baseline × 1.5) |
| `is_anomaly` | INTEGER | NOT NULL | Flag (1 = Ja, 0 = Nein) |

**Beispielzeile:**
```
id=501, namespace_cost_id=101, anomaly_date="2026-04-01", method="moving_average_threshold",
        actual_value=96.00, baseline_value=60.43, threshold_value=90.65, is_anomaly=1
```

**Keys:**
- Primary Key: `id`
- Foreign Key: `namespace_cost_id` → `NamespaceCost.id`

**Bedeutung der Felder:**
- `actual_value`: Was real passiert ist (96.00)
- `baseline_value`: Was normalerweise ist (60.43, der 7-Tage-Durchschnitt)
- `threshold_value`: Ab wann wird es als Problem klassifiziert (90.65)
- `is_anomaly`: 1 = ja, das ist eine Anomalie (weil 96 > 90.65)

**Verbindung zu NamespaceCost:**
- `namespace_cost_id=101` verweist auf die Cost-Zeile für payments am 2026-04-01

---

## Tabelle 6: Notification

**Zweck:** Speichert Benachrichtigungen zu erkannten Anomalien

| Spalte | Typ | Constraint | Bedeutung |
|--------|-----|-----------|----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Eindeutige Notification-ID |
| `anomaly_id` | INTEGER | NOT NULL, FOREIGN KEY | Verweis auf Anomaly.id |
| `notification_date` | TEXT | NOT NULL | Zeitstempel der Benachrichtigung |
| `severity` | TEXT | NOT NULL | Schweregrad (LOW, MEDIUM, HIGH) |
| `status` | TEXT | NOT NULL | Status (NEW, ACKNOWLEDGED, RESOLVED) |
| `message` | TEXT | NOT NULL | Ausführliche Nachricht für den Benutzer |

**Beispielzeile:**
```
id=601, anomaly_id=501, notification_date="2026-04-01T10:30:00+00:00",
        severity="MEDIUM", status="NEW",
        message="Cost anomaly in payments (retail-prod/main) on 2026-04-01: actual=96.00, baseline=60.43, threshold=90.65"
```

**Keys:**
- Primary Key: `id`
- Foreign Key: `anomaly_id` → `Anomaly.id`

**Verbindung zu Anomaly:**
- `anomaly_id=501` verweist auf die Anomalie, die erkannt wurde

---

## Vollständige Verbindungskette

Wenn du eine Notification ab- verfolgen möchtest:

```
Notification (id=601)
  ↓ (anomaly_id=501)
Anomaly (id=501)
  ↓ (namespace_cost_id=101)
NamespaceCost (id=101)
  ↓ (namespace_id=1)
Namespace (id=1, name="payments")
  ↓ (cluster_id=1)
Cluster (id=1, name="main")
  ↓ (project_id=1)
Project (id=1, name="retail-prod")
```

Diese Kette zeigt:
- Welche Notification (601) 
- Auf welche Anomalie (501)
- Bezüglich welcher Cost-Zeile (101)
- Für welchen Namespace (1 = "payments")
- In welchem Cluster (1 = "main")
- In welchem Projekt (1 = "retail-prod")

---

## Foreign Key Constraints (Beziehungen)

Alle Foreign Keys sind im System aktiviert (`PRAGMA foreign_keys = ON`).

Das bedeutet:
- Daten können nicht inkonsistent sein
- Du kannst ein Project nicht löschen, solange noch Clusters darauf verweisen
- Du kannst einen Cluster nicht löschen, solange noch Namespaces darauf verweisen
- usw.

**Foreign Key Pyramid:**
```
Project.id ← Cluster.project_id
Cluster.id ← Namespace.cluster_id
Namespace.id ← NamespaceCost.namespace_id
NamespaceCost.id ← Anomaly.namespace_cost_id
Anomaly.id ← Notification.anomaly_id
```

---

## Unique Constraints (Eindeutigkeit)

| Tabelle | Unique Constraint | Bedeutung |
|---------|---|----------|
| Project | `project_name` | Ein Projektname kommt nur einmal vor |
| Cluster | `(cluster_name, project_id)` | Ein Clustername kommt pro Projekt nur einmal vor |
| Namespace | `(namespace_name, cluster_id)` | Ein Namespace-Name kommt pro Cluster nur einmal vor |
| NamespaceCost | (keiner) | Mehrfache Einträge für denselben Namespace am selben Tag sind möglich (aber nicht gewünscht) |
| Anomaly | (keiner) | Pro Anomalie kann es mehrere Zeilen geben |
| Notification | (keiner) | Pro Anomalie können mehrere Notifications geben |

---

## Wie werden die Tabellen beim Speichern gefüllt

Die [`src/storage.py`](../src/storage.py) Funktion `persist_pipeline_data` füllt sie in dieser Reihenfolge:

1. **Project** - direkt aus `dataset["projects"]`
2. **Cluster** - direkt aus `dataset["clusters"]`, speichert `project_id` von Project
3. **Namespace** - direkt aus `dataset["namespaces"]`, speichert `cluster_id` von Cluster
4. **NamespaceCost** - aus `allocated_costs` (Ergebnis nach Allocation), speichert `namespace_id` von Namespace
5. **Anomaly** - aus `anomalies` (Ergebnis nach Anomaly Detection), speichert `namespace_cost_id` von NamespaceCost
6. **Notification** - aus `notifications` (Ergebnis nach Alerting), speichert `anomaly_id` von Anomaly

Die Reihenfolge ist wichtig, weil die späteren Tabellen die `id` der früheren brauchen.

---

## SQL Befehle, um Daten zu abzufragen

**Alle Projekte sehen:**
```sql
SELECT * FROM Project;
```

**Alle Cluster eines Projekts:**
```sql
SELECT * FROM Cluster WHERE project_id = 1;
```

**Alle Namespaces eines Clusters:**
```sql
SELECT * FROM Namespace WHERE cluster_id = 1;
```

**Kosten für einen Namespace über Zeit:**
```sql
SELECT * FROM NamespaceCost WHERE namespace_id = 1 ORDER BY cost_date;
```

**Alle Anomalien mit Details:**
```sql
SELECT a.*, nc.cost_date, n.namespace_name, c.cluster_name, p.project_name
FROM Anomaly a
JOIN NamespaceCost nc ON a.namespace_cost_id = nc.id
JOIN Namespace n ON nc.namespace_id = n.id
JOIN Cluster c ON n.cluster_id = c.id
JOIN Project p ON c.project_id = p.id
ORDER BY a.anomaly_date DESC;
```

**Alle Notifications mit wichtigen Details:**
```sql
SELECT n.*, a.actual_value, a.threshold_value, ns.namespace_name
FROM Notification n
JOIN Anomaly a ON n.anomaly_id = a.id
JOIN NamespaceCost nc ON a.namespace_cost_id = nc.id
JOIN Namespace ns ON nc.namespace_id = ns.id
ORDER BY n.notification_date DESC;
```

---

## Visualisierung der Datenbank-Struktur

```
┌─────────────────────────────────────────────────────────┐
│                    PROJECT                              │
│  id (PK) | project_name (UNIQUE)                        │
│  1       | retail-prod                                  │
│  2       | platform-prod                                │
└──────────────────────┬──────────────────────────────────┘
                       │ (1:N)
                       │ Foreign Key: project_id
                       ↓
        ┌──────────────────────────────────────────┐
        │          CLUSTER                         │
        │  id (PK) | cluster_name | project_id(FK)│
        │  1       | main         | 1             │
        │  2       | shared       | 1             │
        │  3       | main         | 2             │
        └────────────────┬─────────────────────────┘
                         │ (1:N)
                         │ Foreign Key: cluster_id
                         ↓
             ┌────────────────────────────────────┐
             │      NAMESPACE                     │
             │  id | namespace_name | cluster_id │
             │  1  | payments       | 1          │
             │  2  | checkout       | 1          │
             │  3  | monitoring     | 1          │
             └──────────┬───────────────────────┘
                        │ (1:N)
                        │ Foreign Key: namespace_id
                        ↓
          ┌──────────────────────────────────────────────────┐
          │        NAMESPACECOST                             │
          │ id | cost_date | usage | overhead | total | ns_id│
          │101 | 2026-04-01 | 80   | 16       | 96    | 1   │
          │102 | 2026-04-01 | 40   | 8        | 48    | 2   │
          │103 | 2026-04-02 | 75   | 15       | 90    | 1   │
          └─────────────┬──────────────────────────────────┘
                        │ (1:N)
                        │ Foreign Key: namespace_cost_id
                        ↓
             ┌──────────────────────────────────────────────┐
             │        ANOMALY                               │
             │ id | actual | baseline | threshold | nc_id  │
             │501 | 96.00  | 60.43    | 90.65     | 101    │
             └──────────────┬─────────────────────────────┘
                            │ (1:N)
                            │ Foreign Key: anomaly_id
                            ↓
                   ┌──────────────────────────────┐
                   │    NOTIFICATION              │
                   │ id | severity | anomaly_id  │
                   │601 | MEDIUM   | 501         │
                   └──────────────────────────────┘
```

Diese Struktur stellt sicher, dass jede Benachrichtigung genau einer Anomalie entspricht, die genau einer Cost-Zeile entspricht, usw. Keine Daten werden ohne vollständige Verbindung gespeichert.
