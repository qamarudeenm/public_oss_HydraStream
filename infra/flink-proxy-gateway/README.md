# Flink Gateway Proxy

A translation proxy that accepts requests in the Confluent Cloud Flink SQL API format and translates them to the open-source Apache Flink SQL Gateway REST API.

This enables `confluent-sql` and `dbt-confluent` to work against OSS Flink without modification.

## Architecture

```
confluent-sql / dbt-confluent (unchanged)
    |
    | HTTP (Confluent Cloud API format)
    |
    v
+-------------------------------------------+
| flink-gateway-proxy (Python/FastAPI)      |
|                                           |
| 1. Accept Confluent-format requests       |
| 2. Manage Flink SQL Gateway sessions      |
| 3. Translate to SQL Gateway API calls     |
| 4. Map statement names <-> op handles     |
| 5. Synthesize traits/schema metadata      |
| 6. Return Confluent-format responses      |
+-------------------------------------------+
    |
    | HTTP (Flink SQL Gateway REST API)
    |
    v
Apache Flink SQL Gateway (OSS)
```

## Features

- **API Translation**: Converts Confluent Cloud API requests to Flink SQL Gateway format
- **Session Management**: Manages long-lived Flink sessions with automatic heartbeats
- **Statement Tracking**: Maps Confluent statement names to Flink operation handles
- **Traits Synthesis**: Infers statement traits (SQL kind, bounded, append-only)
- **Result Translation**: Converts Flink results to Confluent changelog format
- **Zero Client Changes**: Works with existing `confluent-sql` and `dbt-confluent` code

## Quick Start

### Prerequisites

- Python 3.11+
- Running Flink SQL Gateway instance

### Installation

```bash
# Install dependencies
make install

# Or using uv directly
uv sync
```

### Configuration

Set environment variables or create a `.env` file:

```bash
PROXY_FLINK_GATEWAY_URL=http://localhost:8083
PROXY_LISTEN_HOST=0.0.0.0
PROXY_LISTEN_PORT=8080
PROXY_LOG_LEVEL=info
```

### Running Locally

```bash
make run

# Or using uvicorn directly
uv run uvicorn flink_gateway_proxy.main:app --reload --host 0.0.0.0 --port 8080
```

### Using with dbt-confluent

Configure `profiles.yml` to point at the proxy:

```yaml
demo:
  outputs:
    dev:
      type: confluent
      host: http://localhost:8080   # Proxy URL instead of Confluent Cloud
      cloud_provider: kubernetes     # Arbitrary (required field)
      cloud_region: local            # Arbitrary (required field)
      compute_pool_id: default       # Arbitrary (stored but not used)
      organization_id: my-org        # Namespace for statement isolation
      environment_id: default_catalog  # Maps to Flink catalog
      flink_api_key: "any"           # Passthrough auth
      flink_api_secret: "any"
      dbname: my_database            # Flink database
      threads: 1
  target: dev
```

Then run dbt as normal:

```bash
cd your-dbt-project
dbt run
```

## Development

### Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests
make test-integration
```

### Linting and Formatting

```bash
# Run linters
make lint

# Format code
make format
```

## Docker

### Build Image

```bash
make docker-build
```

### Run Container

```bash
make docker-run
```

Or with custom settings:

```bash
docker run -p 8080:8080 \
  -e PROXY_FLINK_GATEWAY_URL=http://flink-gateway:8083 \
  flink-gateway-proxy:latest
```

## Kubernetes Deployment

### Deploy to Kubernetes

```bash
kubectl apply -f deploy/kubernetes/
```

### Configuration

Edit `deploy/kubernetes/configmap.yaml` to customize settings.

Update `deploy/kubernetes/deployment.yaml` to set the Flink Gateway URL:

```yaml
env:
  - name: PROXY_FLINK_GATEWAY_URL
    value: "http://flink-sql-gateway:8083"
```

## API Endpoints

### Health and Readiness

- `GET /health` - Health check
- `GET /ready` - Readiness check

### Statement Management

- `POST /sql/v1/organizations/{org}/environments/{env}/statements` - Create statement
- `GET /sql/v1/organizations/{org}/environments/{env}/statements/{name}` - Get statement status
- `GET /sql/v1/organizations/{org}/environments/{env}/statements/{name}/results` - Get results
- `DELETE /sql/v1/organizations/{org}/environments/{env}/statements/{name}` - Delete statement
- `GET /sql/v1/organizations/{org}/environments/{env}/statements` - List statements

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `PROXY_FLINK_GATEWAY_URL` | (required) | URL of Flink SQL Gateway |
| `PROXY_LISTEN_HOST` | `0.0.0.0` | Host to bind the server |
| `PROXY_LISTEN_PORT` | `8080` | Port to bind the server |
| `PROXY_SESSION_HEARTBEAT_INTERVAL` | `30` | Seconds between session heartbeats |
| `PROXY_SESSION_IDLE_TIMEOUT` | `600` | Seconds before idle sessions are cleaned up |
| `PROXY_AUTH_MODE` | `passthrough` | Authentication mode |
| `PROXY_DEFAULT_PRINCIPAL` | `proxy-user` | Default principal name |
| `PROXY_LOG_LEVEL` | `info` | Logging level |

## Limitations

- **In-memory state**: Statement records are stored in memory and lost on restart
- **Single instance**: Not designed for horizontal scaling (sessions are per-instance)
- **Schema extraction**: Currently limited; full schema metadata extraction is TODO
- **Pagination**: Basic implementation; token-based pagination could be improved

## Future Enhancements

- Persistent state store (Redis, PostgreSQL)
- Distributed session management
- Full schema extraction from Flink metadata
- Enhanced error handling and retry logic
- Metrics and observability (Prometheus)
- Authentication and authorization
- CMF integration

## License

See parent repository for license information.
