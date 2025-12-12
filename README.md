# EAI MCP Demo - Enterprise Architecture Integration

A demonstration project for Enterprise Architecture Integration (EAI) using:
- **ArchiMate** for visual modeling
- **MCP (Model Context Protocol)** for service communication
- **RDF/JSON-LD** for semantic interoperability
- **Docker** for containerization
- **JSON-RPC** for remote procedure calls

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              HTML Dashboard (ArchiMate View)            │
│  ┌─────────────┐           ┌─────────────┐             │
│  │  Customer   │ ─────────→│   Order     │             │
│  │  Service    │  RDF Flow │   Service   │             │
│  └─────────────┘           └─────────────┘             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
            ┌────────────────┐
            │   MCP Client   │
            │  (Orchestrator)│
            └────────────────┘
                     │
        ┌────────────┴────────────┐
        ↓                         ↓
┌──────────────┐          ┌──────────────┐
│ MCP Server   │          │ MCP Server   │
│ (Customer)   │          │ (Order)      │
│ + RDF Store  │          │ + RDF Store  │
└──────────────┘          └──────────────┘
   Docker Container         Docker Container
```

## Project Structure

```
eai-mcp-demo/
├── ontology/
│   └── ecommerce.ttl          # Shared RDF ontology
├── mcp-servers/
│   ├── customer-service/
│   │   ├── server.py          # MCP server with RDF store
│   │   └── Dockerfile
│   └── order-service/
│       ├── server.py          # MCP server with RDF store
│       └── Dockerfile
├── client/
│   ├── orchestrator.py        # Backend orchestrator (MCP client)
│   └── requirements.txt
└── dashboard/
    └── index.html             # ArchiMate visualization
```

## Features

### 1. Shared RDF Ontology
- Defined in Turtle format (`ecommerce.ttl`)
- Common vocabulary for e-commerce domain
- Classes: Customer, Order, Product, OrderItem
- Properties: customerId, customerName, orderDate, orderTotal, placedBy, etc.

### 2. MCP Servers
Two independent microservices, each:
- Exposes JSON-RPC 2.0 endpoints via MCP protocol
- Maintains in-memory RDF graph using rdflib
- Returns data in JSON-LD format
- Containerized with Docker

**Customer Service Tools:**
- `list_customers`: Get all customers
- `get_customer`: Get specific customer by ID

**Order Service Tools:**
- `list_orders`: Get all orders
- `get_order`: Get specific order by ID
- `get_customer_orders`: Get all orders for a customer

### 3. MCP Client (Orchestrator)
- Flask-based REST API
- Manages Docker containers
- Acts as MCP client to query multiple services
- Combines results from different services

### 4. ArchiMate Dashboard
- Visual representation of Application Cooperation viewpoint
- Real-time service status (running/stopped)
- Start/stop containers with one click
- Query multiple services
- Display RDF data flows

## Prerequisites

- Docker installed and running
- Python 3.11+
- Modern web browser

## Setup Instructions

### 1. Install Python Dependencies

```bash
cd client
pip install -r requirements.txt
```

### 2. Build Docker Images

The orchestrator will automatically build Docker images on first run, but you can build them manually:

```bash
# From project root
cd mcp-servers/customer-service
docker build -t eai-customer-service .

cd ../order-service
docker build -t eai-order-service .
```

### 3. Start the Orchestrator

```bash
cd client
python orchestrator.py
```

The orchestrator will start on `http://localhost:5000`

### 4. Open the Dashboard

Open `dashboard/index.html` in your web browser, or serve it with a simple HTTP server:

```bash
cd dashboard
python -m http.server 8080
```

Then navigate to `http://localhost:8080`

## Usage

### Starting Services

1. Open the dashboard in your browser
2. Click the "Start" button on any service box
3. Wait for the service to start (status will change to "running")
4. The connection line will become active (green) when both services are running

### Querying Services

1. Select a service from the dropdown (e.g., "Customer Service")
2. Select a tool (e.g., "get_customer")
3. Enter arguments in JSON format: `{"customer_id": "CUST001"}`
4. Click "Execute Query"
5. View the RDF data returned in JSON-LD format

### Example Queries

**List all customers:**
```json
Service: Customer Service
Tool: list_customers
Arguments: {}
```

**Get specific customer:**
```json
Service: Customer Service
Tool: get_customer
Arguments: {"customer_id": "CUST001"}
```

**Get customer's orders:**
```json
Service: Order Service
Tool: get_customer_orders
Arguments: {"customer_id": "CUST001"}
```

**Get specific order:**
```json
Service: Order Service
Tool: get_order
Arguments: {"order_id": "ORD001"}
```

## Sample Data

### Customers
- CUST001: Alice Johnson (alice@example.com)
- CUST002: Bob Smith (bob@example.com)
- CUST003: Carol White (carol@example.com)

### Orders
- ORD001: CUST001, $149.99, 2024-12-01
- ORD002: CUST002, $299.50, 2024-12-05
- ORD003: CUST001, $89.99, 2024-12-10

## Technical Details

### MCP Protocol
Services communicate using the Model Context Protocol (MCP):
- JSON-RPC 2.0 transport
- Stdio-based communication within containers
- Standard tool/resource/prompt capabilities

### RDF/JSON-LD
All data is represented using RDF:
- JSON-LD serialization for easy parsing
- Shared namespace: `http://example.org/ecommerce#`
- Semantic interoperability between services

### Docker Integration
- Each service runs in isolated container
- Services can be started/stopped independently
- No ports exposed (stdio communication)

## API Endpoints

### Orchestrator REST API

**GET /api/services**
- Returns list of all services and their statuses

**POST /api/services/:name/start**
- Starts a service container

**POST /api/services/:name/stop**
- Stops a service container

**POST /api/query**
- Executes MCP queries across services
```json
{
  "queries": [
    {
      "service": "customer-service",
      "tool": "get_customer",
      "arguments": {"customer_id": "CUST001"}
    }
  ]
}
```

**GET /api/ontology**
- Returns the RDF ontology in Turtle format

## Extending the Demo

### Adding a New Service

1. Create a new directory in `mcp-servers/`
2. Implement `server.py` with MCP protocol handlers
3. Create a `Dockerfile`
4. Add service definition to `orchestrator.py` SERVICES dict
5. Update the dashboard to position the new service

### Adding New RDF Classes/Properties

1. Edit `ontology/ecommerce.ttl`
2. Update service implementations to use new properties
3. Restart services

### Adding New Tools

1. Implement the tool function in the appropriate service
2. Add tool definition to `tools/list` response
3. Handle tool call in `tools/call` method
4. Update dashboard with new tool in `serviceTools`

## Troubleshooting

For detailed troubleshooting information, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

**Quick Fixes:**

**Services won't start:**
- Ensure Docker is running
- Check Docker logs: `docker logs eai-customer-service`
- Rebuild images: The orchestrator automatically rebuilds on startup

**Query returns error:**
- Ensure service is running (status should be green)
- Check JSON arguments are valid
- Verify customer/order IDs exist in sample data
- Check orchestrator logs: `tail -f /tmp/orchestrator.log`

**Dashboard not connecting to orchestrator:**
- Ensure orchestrator is running on port 5000
- Check browser console for CORS errors
- Verify `API_BASE` URL in `index.html`

**UTF-8 decode errors:**
- This is caused by Docker socket multiplexing headers
- The orchestrator automatically handles this - see TROUBLESHOOTING.md for details

## ArchiMate Modeling

This demo illustrates key ArchiMate concepts:

- **Application Service**: Customer Service, Order Service
- **Data Object**: Customer (RDF), Order (RDF)
- **Flow Relationship**: Data flows between services via RDF/JSON-LD
- **Technology**: Docker containers, MCP protocol, HTTP/JSON-RPC

## Course Integration

This project demonstrates:
1. ✅ Service-oriented architecture
2. ✅ Semantic interoperability (RDF)
3. ✅ Modern integration patterns (MCP)
4. ✅ Containerization (Docker)
5. ✅ Enterprise architecture visualization (ArchiMate)
6. ✅ RESTful orchestration

Perfect for an EAI course final project!

## License

MIT License - Free to use for educational purposes.

## Author

Created for Enterprise Architecture Integration (EAI) course demonstration.
