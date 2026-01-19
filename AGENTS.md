# AGENTS.md

Guidance for working on the Dutch Geospatial Data Integration project.

## Project Overview

This is a Model Context Protocol (MCP) demonstration project showcasing Enterprise Architecture Integration using Dutch government data sources. The system consists of:

- **Three MCP server services** (Kadaster, CBS, Rijkswaterstaat) providing geospatial data via RDF/JSON-LD
- **AI Agent service** powered by Azure OpenAI for natural language querying
- **Flask orchestrator** (MCP client) coordinating service communication
- **HTML dashboard** for visualization and interaction

All MCP servers communicate via stdio using JSON-RPC 2.0 protocol and run in isolated Docker containers.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User / Dashboard                      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
                         ↓
               ┌──────────────────┐
               │   Orchestrator   │  Flask (port 5000)
               │   (MCP Client)   │
               └────────┬─────────┘
                        │ MCP Protocol (stdio)
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
  ┌─────────┐     ┌─────────┐     ┌──────────────┐
  │Kadaster │     │   CBS   │     │Rijkswaterstaat│
  │Property │     │ Stats   │     │Infrastructure│
  └─────────┘     └─────────┘     └──────────────┘
                        │
                        ↓
              ┌──────────────────┐
              │   Agent Service  │  ← Also an MCP Server
              │   (Meta-Agent)   │  ← Queries other services
              └──────────────────┘
```

### MCP Server Structure

Each MCP server (`mcp-servers/*/server.py`) follows this pattern:
- Implements `list_tools()` to expose available tools
- Implements `call_tool()` to handle tool invocations
- Uses RDFLib to store and query data in Turtle format
- Returns data as JSON-LD with `@context` for semantic interoperability
- All servers share the ontology defined in `ontology/geospatial.ttl`

### Docker Architecture

**Important**: The three data services (Kadaster, CBS, Rijkswaterstaat) share a single distroless Docker image:
- **Shared Dockerfile**: `mcp-servers/Dockerfile.shared` (multi-stage build)
- **Base image**: `gcr.io/distroless/python3-debian12` (no shell, minimal attack surface)
- **Build context**: Each service directory (contains only `server.py`)

The agent-service has its own separate Dockerfile due to different dependencies (Azure OpenAI SDK).

### Communication Flow

1. Dashboard/API sends request to orchestrator (Flask, port 5000)
2. Orchestrator starts Docker containers if needed
3. Orchestrator communicates with containers via Docker socket using stdio
4. MCP servers respond with JSON-RPC messages
5. Orchestrator aggregates responses and returns to client

## Setup and Development

### Prerequisites

- Docker must be running
- uv (Python package manager)
- Azure OpenAI credentials in `.env` file (for AI agent)

### Initial Setup

```bash
# Install all dependencies
uv sync

# Start the orchestrator (builds Docker images automatically)
cd client
python orchestrator.py

# Open dashboard
open ../dashboard/index.html
```

### Environment Variables

The AI agent requires Azure OpenAI configuration in `.env`:
```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

## Code Conventions

### Git Commits

- Do not add "Co-Authored-By: Claude" or similar AI attribution lines to commits
- Write clear, concise commit messages describing what changed and why

### Python Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Keep functions focused and single-purpose

### MCP Server Implementation

When modifying MCP servers:
1. **Tool Registration**: Add new tools to `list_tools()` with complete JSON schema
2. **Tool Implementation**: Handle in `call_tool()` switch statement
3. **RDF Data**: Store all data in the in-memory RDF graph using shared ontology
4. **Response Format**: Return JSON-LD with `@context` pointing to ontology namespace
5. **Error Handling**: Return proper JSON-RPC error responses

Example tool structure:
```python
{
    "name": "tool_name",
    "description": "Clear description of what the tool does",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param_name"]
    }
}
```

### Docker Guidelines

**DO NOT** create individual Dockerfiles for Kadaster, CBS, or Rijkswaterstaat services. They share `Dockerfile.shared`.

When modifying the shared Dockerfile:
- Changes affect all three services
- Test all three containers after modifications
- Keep the distroless approach (no shell utilities)

### RDF/Ontology Updates

When modifying the shared ontology (`ontology/geospatial.ttl`):
1. Use consistent namespace: `http://example.org/geospatial#`
2. Update all affected MCP servers to use new properties
3. Maintain backward compatibility with existing data

## AI Agent

The AI Agent acts as an orchestrating LLM that:
1. Understands natural language questions
2. Determines which MCP services need to be queried
3. Executes necessary tool calls in parallel
4. Synthesizes information from multiple sources
5. Provides comprehensive, natural language answers

### Usage

**Via Dashboard:**
1. Start all services including "AI Agent"
2. Use the "AI Agent" panel to ask questions

**Via API:**
```bash
curl -X POST http://localhost:5000/api/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the population of Utrecht?"}'
```

### Example Questions

- "What is the population of Amsterdam?"
- "Compare the population between Amsterdam and Rotterdam"
- "What infrastructure exists near the Erasmusbrug?"

### Agent Architecture

The agent service is a **Meta-Agent** - both an MCP server and MCP client:

**Exposes (as MCP Server):**
- `ask_question` tool for natural language queries

**Consumes (as MCP Client):**
- Kadaster tools: `get_property`, `list_properties`
- CBS tools: `get_statistics`, `list_locations`, `get_demographics`
- Rijkswaterstaat tools: `get_infrastructure`, `list_roads`, `get_water_level`

## Testing

### MCP Inspector

Use the MCP Inspector for interactive debugging of MCP servers:

```bash
# Inspect kadaster-service locally
./scripts/inspect-mcp.sh kadaster-service

# Inspect cbs-service locally
./scripts/inspect-mcp.sh cbs-service

# Inspect via Docker (container must be running)
./scripts/inspect-mcp.sh kadaster-service --docker

# Inspect agent-service (requires .env with Azure credentials)
./scripts/inspect-mcp.sh agent-service
```

The Inspector opens a web UI where you can:
- Browse available tools and their schemas
- Execute tools with custom arguments
- View server logs and notifications

### Manual Testing

```bash
# Test individual MCP server locally
cd mcp-servers/kadaster-service
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python server.py
```

### Integration Testing

```bash
# Test AI agent
python test_agent.py

# Test via orchestrator API
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"service":"kadaster-service","tool":"list_properties","arguments":{}}'
```

### Docker Testing

```bash
# Build and start services
docker-compose up -d kadaster-service cbs-service rijkswaterstaat-service

# Check logs
docker logs eai-kadaster-service

# Verify distroless (should fail - no shell)
docker exec eai-kadaster-service ls
```

## Debugging

### Orchestrator Logs

```bash
tail -f /tmp/orchestrator.log
```

### Docker Communication Issues

If services fail to respond:
1. Check container logs: `docker logs eai-[service-name]`
2. Verify container is running: `docker ps`
3. Check orchestrator logs for encoding errors
4. Restart container: `docker-compose restart [service-name]`

### Agent Issues

```bash
# Watch agent logs
docker logs -f eai-agent-service
```

Common causes:
- Azure OpenAI credentials not configured
- Backend services not running
- Docker socket not mounted

## Security Considerations

1. **No secrets in code**: Use `.env` file for API keys
2. **Docker socket access**: Orchestrator needs `/var/run/docker.sock` - be aware of security implications
3. **Distroless images**: Maintain distroless approach for production deployments
4. **Input validation**: All MCP tool inputs should be validated before processing

## Useful Commands

```bash
# Rebuild specific service
docker-compose build kadaster-service

# View all service logs
docker-compose logs -f

# Stop all services
docker-compose down

# Remove all containers and images
docker-compose down --rmi all

# Check image sizes
docker images | grep ais
```

## Resources

- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [RDFLib Documentation](https://rdflib.readthedocs.io/)
- [Distroless Images](https://github.com/GoogleContainerTools/distroless)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
