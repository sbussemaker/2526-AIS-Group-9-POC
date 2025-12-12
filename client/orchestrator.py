#!/usr/bin/env python3
"""
EAI Orchestration Backend
Manages Docker containers and acts as MCP client
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import docker
import json
import time
import sys

app = Flask(__name__)
CORS(app)

# Enable logging to file and stdout
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/orchestrator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Docker client
docker_client = docker.from_env()

# Service definitions
SERVICES = {
    "customer-service": {
        "name": "customer-service",
        "display_name": "Customer Service",
        "description": "Manages customer data",
        "image": "eai-customer-service",
        "build_path": "../mcp-servers/customer-service",
        "container_name": "eai-customer-service",
        "status": "stopped",
        "rdf_entities": ["Customer"],
        "position": {"x": 100, "y": 100}
    },
    "order-service": {
        "name": "order-service",
        "display_name": "Order Service",
        "description": "Manages order data",
        "image": "eai-order-service",
        "build_path": "../mcp-servers/order-service",
        "container_name": "eai-order-service",
        "status": "stopped",
        "rdf_entities": ["Order"],
        "position": {"x": 400, "y": 100}
    }
}

def update_service_status():
    """Update service statuses based on running containers"""
    try:
        containers = docker_client.containers.list(all=True)
        for service in SERVICES.values():
            found = False
            for container in containers:
                if container.name == service["container_name"]:
                    service["status"] = container.status
                    found = True
                    break
            if not found:
                service["status"] = "stopped"
    except Exception as e:
        logger.error(f"Error updating status: {e}")

def call_mcp_tool(container_name, tool_name, arguments={}):
    """Call an MCP tool in a running container"""
    try:
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return {"error": f"Container {container_name} is not running"}
        
        # Initialize MCP connection
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "eai-orchestrator", "version": "1.0.0"}
            }
        }) + "\n"
        
        exec_result = container.exec_run(
            f"python -u server.py",
            stdin=True,
            stdout=True,
            stderr=False,  # Disable stderr to prevent mixing with JSON responses
            detach=False,
            tty=False,
            socket=True
        )
        
        socket = exec_result.output
        socket._sock.sendall(init_request.encode())
        
        # Read initialization response
        response_line = b""
        while True:
            chunk = socket._sock.recv(1)
            if not chunk or chunk == b"\n":
                break
            response_line += chunk

        # Strip Docker multiplexing header (8 bytes) if present
        if len(response_line) > 8 and response_line[0] in (0x01, 0x02):
            response_line = response_line[8:]

        logger.info(f"Init response: {response_line.decode('utf-8', errors='replace')[:200]}")

        # Call the tool
        tool_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }) + "\n"

        socket._sock.sendall(tool_request.encode())

        # Read tool response
        response_line = b""
        while True:
            chunk = socket._sock.recv(1)
            if not chunk or chunk == b"\n":
                break
            response_line += chunk

        socket._sock.close()

        logger.info(f"Tool response raw bytes (first 50): {response_line[:50]}")

        # Strip Docker multiplexing header (8 bytes) if present
        # Docker prepends: [stream_type (1 byte)][padding (3 bytes)][size (4 bytes)]
        if len(response_line) > 8 and response_line[0] in (0x01, 0x02):
            logger.info("Stripping Docker multiplexing header")
            response_line = response_line[8:]

        logger.info(f"After header strip (first 50): {response_line[:50]}")

        # Decode with error handling for invalid UTF-8 bytes
        try:
            decoded_response = response_line.decode('utf-8')
        except UnicodeDecodeError as e:
            # Try with error handling
            decoded_response = response_line.decode('utf-8', errors='replace')
            logger.warning(f"Invalid UTF-8 in response: {e}")
            logger.warning(f"Raw bytes (first 100): {response_line[:100]}")

        # Strip whitespace
        decoded_response = decoded_response.strip()

        logger.info(f"Tool response decoded (first 200 chars): {decoded_response[:200]}")

        try:
            result = json.loads(decoded_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {decoded_response}")
            return {"error": f"Invalid JSON response: {str(e)}"}

        return result

    except Exception as e:
        import traceback
        logger.error(f"Error in call_mcp_tool: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

@app.route('/api/services', methods=['GET'])
def get_services():
    """Get all services and their statuses"""
    update_service_status()
    return jsonify(list(SERVICES.values()))

@app.route('/api/services/<service_name>/start', methods=['POST'])
def start_service(service_name):
    """Start a service container"""
    if service_name not in SERVICES:
        return jsonify({"error": "Service not found"}), 404
    
    service = SERVICES[service_name]
    
    try:
        # Check if container exists
        try:
            container = docker_client.containers.get(service["container_name"])
            if container.status == "running":
                return jsonify({"status": "already running"})
            container.start()
        except docker.errors.NotFound:
            # Build image if needed
            try:
                docker_client.images.get(service["image"])
            except docker.errors.ImageNotFound:
                print(f"Building image {service['image']}...")
                docker_client.images.build(
                    path=service["build_path"],
                    tag=service["image"]
                )
            
            # Create and start container
            container = docker_client.containers.run(
                service["image"],
                name=service["container_name"],
                detach=True,
                stdin_open=True,
                tty=False
            )
        
        # Wait a moment for container to start
        time.sleep(1)
        update_service_status()
        
        return jsonify({"status": "started", "container_id": container.id})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/<service_name>/stop', methods=['POST'])
def stop_service(service_name):
    """Stop a service container"""
    if service_name not in SERVICES:
        return jsonify({"error": "Service not found"}), 404
    
    service = SERVICES[service_name]
    
    try:
        container = docker_client.containers.get(service["container_name"])
        container.stop()
        update_service_status()
        return jsonify({"status": "stopped"})
    except docker.errors.NotFound:
        return jsonify({"status": "not found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def query_services():
    """Execute a query across multiple services using MCP"""
    data = request.json
    queries = data.get("queries", [])
    
    results = []
    for query in queries:
        service_name = query.get("service")
        tool_name = query.get("tool")
        arguments = query.get("arguments", {})
        
        if service_name not in SERVICES:
            results.append({"error": f"Service {service_name} not found"})
            continue
        
        service = SERVICES[service_name]
        result = call_mcp_tool(service["container_name"], tool_name, arguments)
        results.append({
            "service": service_name,
            "tool": tool_name,
            "result": result
        })
    
    return jsonify({"results": results})

@app.route('/api/ontology', methods=['GET'])
def get_ontology():
    """Get the RDF ontology"""
    try:
        with open('../ontology/ecommerce.ttl', 'r') as f:
            ontology = f.read()
        return jsonify({"ontology": ontology})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting EAI Orchestration Backend...")
    logger.info("Building Docker images...")

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

    update_service_status()
    logger.info("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
