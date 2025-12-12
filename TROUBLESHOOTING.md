# Troubleshooting Guide

This document contains solutions to technical issues encountered during development and deployment of the EAI MCP Demo project.

## Table of Contents
1. [Docker Socket Communication Issues](#docker-socket-communication-issues)
2. [Dashboard UI Issues](#dashboard-ui-issues)
3. [Image Building](#image-building)
4. [Debugging Tips](#debugging-tips)

---

## Docker Socket Communication Issues

### Issue: UTF-8 Decode Errors with MCP Responses

**Problem:**
When querying MCP servers running in Docker containers via `exec_run` with socket communication, you may encounter:
```
'utf-8' codec can't decode byte 0x80 in position 7: invalid start byte
```

**Root Cause:**
Docker's socket API uses **multiplexing headers** to distinguish between stdout and stderr streams. When using `container.exec_run(..., socket=True)`, Docker prepends an 8-byte header to each output chunk:

```
Byte 0:     Stream type (0x01 = stdout, 0x02 = stderr)
Bytes 1-3:  Padding (0x00)
Bytes 4-7:  Size of the following message (32-bit big-endian integer)
```

For example, a JSON response is prefixed with:
```
\x01\x00\x00\x00\x00\x00\x03\xa5{"jsonrpc": ...
```

These binary bytes corrupt UTF-8 decoding and JSON parsing.

**Solution:**
Strip the 8-byte header before processing the response:

```python
# Read response from socket
response_line = b""
while True:
    chunk = socket._sock.recv(1)
    if not chunk or chunk == b"\n":
        break
    response_line += chunk

# Strip Docker multiplexing header if present
if len(response_line) > 8 and response_line[0] in (0x01, 0x02):
    response_line = response_line[8:]

# Now decode as UTF-8
decoded_response = response_line.decode('utf-8')
result = json.loads(decoded_response)
```

**Location in Code:**
- File: `client/orchestrator.py`
- Function: `call_mcp_tool()`
- Lines: ~114-116 and ~145-149

**References:**
- Docker Engine API documentation on multiplexed streams
- The header format is consistent across Docker API versions

---

### Issue: Mixed stdout/stderr Contaminating Responses

**Problem:**
Python warnings, debug messages, or error output from the MCP server process mix with JSON responses, causing parsing failures.

**Root Cause:**
When `exec_run` is called with `stderr=True`, both stdout and stderr are combined into a single stream. Any Python warnings (e.g., deprecation warnings, module import messages) get mixed with the JSON-RPC responses.

**Solution:**
Disable stderr in `exec_run`:

```python
exec_result = container.exec_run(
    f"python -u server.py",
    stdin=True,
    stdout=True,
    stderr=False,  # Disable stderr to prevent mixing with JSON responses
    detach=False,
    tty=False,
    socket=True
)
```

**Location in Code:**
- File: `client/orchestrator.py`
- Function: `call_mcp_tool()`
- Line: ~86

**Note:**
This means stderr output from the MCP server won't be visible. If you need to debug the server, consider:
1. Running the server directly (not via exec_run)
2. Using `docker logs` to view container output
3. Temporarily enabling stderr and parsing only clean JSON lines

---

## Dashboard UI Issues

### Issue: Service Dropdown Deselects Every Few Seconds

**Problem:**
When selecting a service from the dropdown in the dashboard, the selection resets after a few seconds.

**Root Cause:**
The dashboard polls `/api/services` every 5 seconds to refresh service statuses. The `updateServiceSelect()` function rebuilds the dropdown HTML from scratch, destroying the current selection:

```javascript
function updateServiceSelect() {
    const select = document.getElementById('service-select');
    select.innerHTML = '<option value="">Select a service...</option>'; // This wipes the selection
    services.forEach(service => {
        // Rebuild options...
    });
}
```

**Solution:**
Preserve the current selection before rebuilding, then restore it:

```javascript
function updateServiceSelect() {
    const select = document.getElementById('service-select');
    const toolSelect = document.getElementById('tool-select');
    const currentValue = select.value; // Save current selection
    const currentTool = toolSelect.value; // Save tool selection too

    select.innerHTML = '<option value="">Select a service...</option>';
    services.forEach(service => {
        const option = document.createElement('option');
        option.value = service.name;
        option.textContent = service.display_name;
        select.appendChild(option);
    });
    select.value = currentValue; // Restore selection

    // Repopulate tools if a service was selected
    if (currentValue && serviceTools[currentValue]) {
        toolSelect.innerHTML = '<option value="">Select a tool...</option>';
        serviceTools[currentValue].forEach(tool => {
            const option = document.createElement('option');
            option.value = tool.name;
            option.textContent = tool.name;
            option.dataset.args = JSON.stringify(tool.args);
            toolSelect.appendChild(option);
        });
        toolSelect.value = currentTool; // Restore tool selection
    }
}
```

**Location in Code:**
- File: `dashboard/index.html`
- Function: `updateServiceSelect()`
- Lines: ~489-516

**Alternative Solutions:**
- Use a virtual DOM library (React, Vue) that preserves element state
- Only update the dropdown when services list actually changes
- Disable auto-refresh while user is interacting with dropdowns

---

## Image Building

### Issue: Docker Images Not Rebuilding with Code Changes

**Problem:**
After modifying MCP server code, the containers still run the old version.

**Root Cause:**
The orchestrator checks if images exist and only builds them if they're missing. Docker's layer caching means even `docker build` might use cached layers.

**Solution:**
Configure the orchestrator to always rebuild images on startup:

```python
# Always rebuild images on startup (like --build flag)
for service in SERVICES.values():
    logger.info(f"Building {service['image']}...")
    docker_client.images.build(
        path=service["build_path"],
        tag=service["image"],
        rm=True,  # Remove intermediate containers
        forcerm=True  # Always remove intermediate containers
    )
    logger.info(f"✓ Built {service['image']}")
```

**Location in Code:**
- File: `client/orchestrator.py`
- Main block: `if __name__ == '__main__'`
- Lines: ~283-292

**Manual Rebuild:**
To force rebuild without starting orchestrator:
```bash
docker build --no-cache -t eai-kadaster-service mcp-servers/kadaster-service/
docker build --no-cache -t eai-cbs-service mcp-servers/cbs-service/
docker build --no-cache -t eai-rijkswaterstaat-service mcp-servers/rijkswaterstaat-service/
```

**Restart Containers:**
After rebuilding, restart the containers:
```bash
docker restart eai-kadaster-service eai-cbs-service eai-rijkswaterstaat-service
```

---

## Debugging Tips

### Enable Comprehensive Logging

The orchestrator includes detailed logging to `/tmp/orchestrator.log`:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/orchestrator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

**View logs in real-time:**
```bash
tail -f /tmp/orchestrator.log
```

**View recent logs:**
```bash
tail -50 /tmp/orchestrator.log
```

**Location in Code:**
- File: `client/orchestrator.py`
- Lines: ~17-27

---

### Inspect Docker Socket Communication

The orchestrator logs raw bytes from Docker socket responses:

```
[INFO] Tool response raw bytes (first 50): b'\x01\x00\x00\x00\x00\x00\x03\xa5{"jsonrpc"...'
[INFO] Stripping Docker multiplexing header
[INFO] After header strip (first 50): b'{"jsonrpc": "2.0", "id": 2, "result": {...'
[INFO] Tool response decoded (first 200 chars): {"jsonrpc": "2.0", "id": 2...
```

This helps identify:
- Whether Docker headers are being stripped correctly
- UTF-8 encoding issues
- JSON structure problems

---

### Check MCP Server Logs

View logs from MCP server containers:

```bash
# Kadaster service
docker logs eai-kadaster-service

# CBS service
docker logs eai-cbs-service

# Rijkswaterstaat service
docker logs eai-rijkswaterstaat-service

# Follow logs in real-time
docker logs -f eai-kadaster-service
```

---

### Test MCP Servers Directly

Test MCP servers without the orchestrator:

```bash
# Start container interactively
docker run -it --rm eai-kadaster-service python -u server.py

# Send JSON-RPC request (paste and press Enter)
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}

# Should get initialize response
# Then send tool list request
{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

# Then call a tool
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_properties", "arguments": {}}}
```

---

### Common Error Messages and Solutions

#### "Container not found"
**Cause:** Service container doesn't exist
**Solution:** Start the service from the dashboard or build the image manually

#### "Container is not running"
**Cause:** Service container is stopped
**Solution:** Click "Start" button in dashboard

#### "Invalid JSON response"
**Cause:** Docker multiplexing headers not stripped, or malformed JSON from server
**Solution:** Check logs for raw bytes, ensure header stripping is working

#### "Module not found" in container
**Cause:** Missing Python dependencies in Dockerfile
**Solution:** Add missing packages to Dockerfile, rebuild image

#### "CORS error" in browser console
**Cause:** Dashboard can't reach orchestrator API
**Solution:**
- Ensure orchestrator is running on port 5000
- Check `API_BASE` URL in `dashboard/index.html`
- Verify Flask CORS is enabled

---

## Known Limitations

1. **Socket Performance:** Reading byte-by-byte from socket (`recv(1)`) is slow. Consider buffering for production use.

2. **No Streaming:** Current implementation reads entire response before parsing. Large responses may cause delays.

3. **Error Handling:** MCP server exceptions may not propagate clearly through Docker socket layer.

4. **Single Request per Container:** Each query spawns a new `exec_run` process. For high-frequency queries, consider persistent connections.

5. **No Authentication:** MCP communication is unauthenticated. Add security layer for production.

---

## Best Practices

1. **Always check logs first** when debugging communication issues
2. **Test MCP servers independently** before integrating with orchestrator
3. **Use raw byte inspection** to diagnose encoding/protocol issues
4. **Rebuild images** after any code changes to MCP servers
5. **Monitor container status** via `docker ps` during development
6. **Keep dependencies updated** in requirements.txt and Dockerfiles

---

## Additional Resources

- [Docker Engine API - Attach to Container](https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerAttach)
- [MCP Protocol Specification](https://modelcontextprotocol.io/docs)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [RDFLib Documentation](https://rdflib.readthedocs.io/)
- [JSON-LD Specification](https://json-ld.org/)

---

**Last Updated:** 2025-12-12
**Document Version:** 1.0
