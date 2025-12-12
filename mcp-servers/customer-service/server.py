#!/usr/bin/env python3
"""
Customer Service MCP Server
Manages customer data using in-memory RDF store
"""

import json
import sys
from datetime import datetime
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Define namespace
ECOM = Namespace("http://example.org/ecommerce#")

# Initialize in-memory RDF graph
graph = Graph()
graph.bind("ecom", ECOM)

# Add some sample customer data
def init_data():
    customers = [
        ("CUST001", "Alice Johnson", "alice@example.com"),
        ("CUST002", "Bob Smith", "bob@example.com"),
        ("CUST003", "Carol White", "carol@example.com"),
    ]
    
    for cust_id, name, email in customers:
        customer_uri = URIRef(f"http://example.org/customers/{cust_id}")
        graph.add((customer_uri, RDF.type, ECOM.Customer))
        graph.add((customer_uri, ECOM.customerId, Literal(cust_id)))
        graph.add((customer_uri, ECOM.customerName, Literal(name)))
        graph.add((customer_uri, ECOM.customerEmail, Literal(email)))

init_data()

def get_customer(customer_id):
    """Get customer data as JSON-LD"""
    customer_uri = URIRef(f"http://example.org/customers/{customer_id}")
    
    # Check if customer exists
    if (customer_uri, RDF.type, ECOM.Customer) not in graph:
        return None
    
    # Extract data
    name = str(graph.value(customer_uri, ECOM.customerName))
    email = str(graph.value(customer_uri, ECOM.customerEmail))
    
    return {
        "@context": {"ecom": "http://example.org/ecommerce#"},
        "@id": str(customer_uri),
        "@type": "ecom:Customer",
        "ecom:customerId": customer_id,
        "ecom:customerName": name,
        "ecom:customerEmail": email
    }

def list_customers():
    """List all customers as JSON-LD"""
    customers = []
    for customer_uri in graph.subjects(RDF.type, ECOM.Customer):
        cust_id = str(graph.value(customer_uri, ECOM.customerId))
        name = str(graph.value(customer_uri, ECOM.customerName))
        email = str(graph.value(customer_uri, ECOM.customerEmail))
        
        customers.append({
            "@id": str(customer_uri),
            "@type": "ecom:Customer",
            "ecom:customerId": cust_id,
            "ecom:customerName": name,
            "ecom:customerEmail": email
        })
    
    return {
        "@context": {"ecom": "http://example.org/ecommerce#"},
        "@graph": customers
    }

def handle_request(request):
    """Handle MCP JSON-RPC request"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "customer-service",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_customer",
                        "description": "Get customer information by ID. Returns RDF data in JSON-LD format.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "customer_id": {
                                    "type": "string",
                                    "description": "The customer ID"
                                }
                            },
                            "required": ["customer_id"]
                        }
                    },
                    {
                        "name": "list_customers",
                        "description": "List all customers. Returns RDF data in JSON-LD format.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if tool_name == "get_customer":
            customer_id = tool_args.get("customer_id")
            result = get_customer(customer_id)
            
            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Customer {customer_id} not found"
                            }
                        ],
                        "isError": True
                    }
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        
        elif tool_name == "list_customers":
            result = list_customers()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
    
    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }

def main():
    """Main MCP server loop using stdio transport"""
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
