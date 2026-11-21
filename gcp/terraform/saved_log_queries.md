# HydraStream — Saved Cloud Logging Queries

## All ERROR logs from HydraStream pods
```
resource.type="k8s_container"
resource.labels.cluster_name="hydrastream-cluster"
severity="ERROR"
```

## Flink checkpoint failures
```
resource.type="k8s_container"
resource.labels.cluster_name="hydrastream-cluster"
textPayload=~"(?i)(checkpoint.*fail|fail.*checkpoint)"
```

## Pod OOM kills
```
resource.type="k8s_node"
jsonPayload.reason="OOMKilling"
```

## Cloud SQL slow queries (> 1s)
```
resource.type="cloudsql_database"
textPayload=~"duration: [1-9][0-9]{3,}"
```

## Flink Proxy Gateway 5xx errors
```
resource.type="cloud_run_revision"
resource.labels.service_name="flink-proxy-gateway"
httpRequest.status>=500
```

## Control plane auth failures
```
resource.type="k8s_container"
resource.labels.cluster_name="hydrastream-cluster"
textPayload=~"(?i)(unauthorized|forbidden|auth.*fail|invalid.*token)"
```

## Kafka consumer group lag
```
resource.type="k8s_container"
resource.labels.cluster_name="hydrastream-cluster"
textPayload=~"(?i)(consumer.*lag|lag.*consumer)"
```
