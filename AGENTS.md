# AGENTS.md

This file provides guidance for AI coding agents working on the Dutch Geospatial Data Integration project.

## Project Overview

This is a Model Context Protocol (MCP) demonstration project showcasing Enterprise Architecture Integration using Dutch government data sources. The system consists of:

- **Three MCP server services** (Kadaster, CBS, Rijkswaterstaat) providing geospatial data via RDF/JSON-LD
- **AI Agent service** powered by Azure OpenAI for natural language querying
- **Flask orchestrator** (MCP client) coordinating service communication
- **HTML dashboard** for visualization and interaction

All MCP servers communicate via stdio using JSON-RPC 2.0 protocol and run in isolated Docker containers.

## Architecture Patterns

### MCP Server Structure

Each MCP server (`mcp-servers/*/server.py`) follows this pattern:
- Implements `list_tools()` to expose available tools
- Implements `call_tool()` to handle tool invocations
- Uses RDFLib to store and query data in Turtle format
- Returns data as JSON-LD with `@context` for semantic interoperability
- All servers share the ontology defined in `ontology/geospatial.ttl`

### Docker Architecture

**IMPORTANT**: The three data services (Kadaster, CBS, Rijkswaterstaat) share a single distroless Docker image:
- **Shared Dockerfile**: `mcp-servers/Dockerfile.shared` (multi-stage build)
- **Base image**: `gcr.io/distroless/python3-debian12` (no shell, minimal attack surface)
- **Build context**: Each service directory (contains only `server.py`)
- **Configuration**: `docker-compose.yml` references `dockerfile: ../Dockerfile.shared`

The agent-service has its own separate Dockerfile due to different dependencies (Azure OpenAI SDK).

### Communication Flow

1. Dashboard/API sends request to orchestrator (Flask, port 5000)
2. Orchestrator starts Docker containers if needed
3. Orchestrator communicates with containers via Docker socket using stdio
4. MCP servers respond with JSON-RPC messages
5. Orchestrator aggregates responses and returns to client

## Setup and Development

### Prerequisites

```bash
# Install uv (Python package manager)
# Docker must be running
# Azure OpenAI credentials in .env file (for AI agent)
```

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

### Python Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Keep functions focused and single-purpose
- Use descriptive variable names

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
- Dependencies are installed in builder stage, not runtime

### RDF/Ontology Updates

When modifying the shared ontology (`ontology/geospatial.ttl`):
1. Use consistent namespace: `http://example.org/geospatial#`
2. Update all affected MCP servers to use new properties
3. Maintain backward compatibility with existing data
4. Document new classes/properties in README.md

## Testing

### Manual Testing

```bash
# Test individual MCP server locally (before Docker)
cd mcp-servers/kadaster-service
python server.py

# In another terminal, send JSON-RPC:
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

After building images, verify containers start and respond:
```bash
# Build and start services
docker-compose up -d kadaster-service cbs-service rijkswaterstaat-service

# Check logs for errors
docker logs eai-kadaster-service
docker logs eai-cbs-service
docker logs eai-rijkswaterstaat-service

# Verify distroless (should fail - no shell)
docker exec eai-kadaster-service ls
```

## Common Tasks

### Adding a New MCP Tool

1. Edit the appropriate `mcp-servers/*/server.py`
2. Add tool definition to `list_tools()`
3. Add implementation case to `call_tool()`
4. Test manually before Docker deployment
5. Rebuild: orchestrator does this automatically on startup

### Adding New Sample Data

1. Edit the RDF graph initialization in the server's `__init__`
2. Use consistent location IDs (LOC001, LOC002, LOC003)
3. Follow the shared ontology structure
4. Ensure all three services have complementary data for the same locations

### Modifying the AI Agent

The agent service (`mcp-servers/agent-service/server.py`) uses Azure OpenAI with function calling:
1. Available tools are defined in the `tools` list
2. Functions are called based on LLM decisions
3. Results are synthesized into natural language answers
4. Modify prompts carefully to maintain data accuracy

### Updating Documentation

- **README.md**: User-facing documentation, setup guides, architecture diagrams
- **AGENTS.md** (this file): Agent-specific technical guidance
- **TROUBLESHOOTING.md**: Common issues and solutions
- **AI-AGENT.md**: AI agent feature documentation

## Debugging

### Orchestrator Logs

```bash
tail -f /tmp/orchestrator.log
```

### Docker Communication Issues

The orchestrator handles Docker socket communication with special multiplexing headers. If services fail to respond:
1. Check container logs: `docker logs eai-[service-name]`
2. Verify container is running: `docker ps`
3. Check orchestrator logs for encoding errors
4. Restart container: `docker-compose restart [service-name]`

### UTF-8 Encoding

All MCP communication uses UTF-8. If you see encoding errors:
- Ensure all JSON-RPC messages are properly encoded
- Check that RDF data doesn't contain invalid UTF-8 sequences
- Review `TROUBLESHOOTING.md` for specific solutions

## Important Technical Details

### Distroless Images

The three data services use distroless images which means:
- **NO shell access**: Cannot `docker exec` with `sh` or `bash`
- **NO debugging tools**: No `ls`, `cat`, `grep`, etc. inside containers
- **Limited debugging**: Use logs and Python's built-in capabilities only
- **Security benefit**: Minimal attack surface, production-ready

### Stdio Communication

MCP servers use stdio (stdin/stdout) not HTTP:
- All communication via JSON-RPC 2.0 over stdin/stdout
- Orchestrator manages Docker attach for stdio multiplexing
- Messages must be complete JSON objects
- No partial message handling

### RDF Data Format

All servers return JSON-LD which is:
- Valid JSON (easy to parse)
- Valid RDF (semantic meaning via `@context`)
- Uses shared namespace: `http://example.org/geospatial#`
- Can be converted to other RDF formats (Turtle, N-Triples, etc.)

## Security Considerations

1. **No secrets in code**: Use `.env` file for API keys
2. **Docker socket access**: Orchestrator needs `/var/run/docker.sock` - be aware of security implications
3. **Distroless images**: Maintain distroless approach for production deployments
4. **Input validation**: All MCP tool inputs should be validated before processing
5. **RDF injection**: Sanitize any user input that becomes part of RDF queries

## CI/CD and Deployment

This is a demonstration project without formal CI/CD. For production deployment:
1. Pre-build Docker images instead of building on startup
2. Use Docker registry for image distribution
3. Implement health checks for all services
4. Add monitoring and observability
5. Consider Kubernetes for orchestration at scale

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

# Verify distroless (should see no shell)
docker history ais-kadaster-service
```

## Additional Resources

- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [RDFLib Documentation](https://rdflib.readthedocs.io/)
- [Distroless Images](https://github.com/GoogleContainerTools/distroless)
- Project-specific docs: README.md, AI-AGENT.md, TROUBLESHOOTING.md, MCP-AGENT-ARCHITECTURE.md
