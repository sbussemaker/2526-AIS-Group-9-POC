#!/usr/bin/env python3
"""
Order Service MCP Server
Manages order data using in-memory RDF store
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

# Add some sample order data
def init_data():
    orders = [
        ("ORD001", "CUST001", "2024-12-01T10:30:00", 149.99),
        ("ORD002", "CUST002", "2024-12-05T14:15:00", 299.50),
        ("ORD003", "CUST001", "2024-12-10T09:00:00", 89.99),
    ]
    
    for order_id, customer_id, order_date, total in orders:
        order_uri = URIRef(f"http://example.org/orders/{order_id}")
        customer_uri = URIRef(f"http://example.org/customers/{customer_id}")
        
        graph.add((order_uri, RDF.type, ECOM.Order))
        graph.add((order_uri, ECOM.orderId, Literal(order_id)))
        graph.add((order_uri, ECOM.orderDate, Literal(order_date, datatype=XSD.dateTime)))
        graph.add((order_uri, ECOM.orderTotal, Literal(total, datatype=XSD.decimal)))
        graph.add((order_uri, ECOM.placedBy, customer_uri))

init_data()

def get_order(order_id):
    """Get order data as JSON-LD"""
    order_uri = URIRef(f"http://example.org/orders/{order_id}")
    
    # Check if order exists
    if (order_uri, RDF.type, ECOM.Order) not in graph:
        return None
    
    # Extract data
    order_date = str(graph.value(order_uri, ECOM.orderDate))
    order_total = str(graph.value(order_uri, ECOM.orderTotal))
    customer_uri = str(graph.value(order_uri, ECOM.placedBy))
    
    return {
        "@context": {"ecom": "http://example.org/ecommerce#"},
        "@id": str(order_uri),
        "@type": "ecom:Order",
        "ecom:orderId": order_id,
        "ecom:orderDate": order_date,
        "ecom:orderTotal": float(order_total),
        "ecom:placedBy": {"@id": customer_uri}
    }

def get_customer_orders(customer_id):
    """Get all orders for a customer as JSON-LD"""
    customer_uri = URIRef(f"http://example.org/customers/{customer_id}")
    orders = []
    
    for order_uri in graph.subjects(ECOM.placedBy, customer_uri):
        order_id = str(graph.value(order_uri, ECOM.orderId))
        order_date = str(graph.value(order_uri, ECOM.orderDate))
        order_total = str(graph.value(order_uri, ECOM.orderTotal))
        
        orders.append({
            "@id": str(order_uri),
            "@type": "ecom:Order",
            "ecom:orderId": order_id,
            "ecom:orderDate": order_date,
            "ecom:orderTotal": float(order_total),
            "ecom:placedBy": {"@id": str(customer_uri)}
        })
    
    return {
        "@context": {"ecom": "http://example.org/ecommerce#"},
        "@graph": orders
    }

def list_orders():
    """List all orders as JSON-LD"""
    orders = []
    for order_uri in graph.subjects(RDF.type, ECOM.Order):
        order_id = str(graph.value(order_uri, ECOM.orderId))
        order_date = str(graph.value(order_uri, ECOM.orderDate))
        order_total = str(graph.value(order_uri, ECOM.orderTotal))
        customer_uri = str(graph.value(order_uri, ECOM.placedBy))
        
        orders.append({
            "@id": str(order_uri),
            "@type": "ecom:Order",
            "ecom:orderId": order_id,
            "ecom:orderDate": order_date,
            "ecom:orderTotal": float(order_total),
            "ecom:placedBy": {"@id": customer_uri}
        })
    
    return {
        "@context": {"ecom": "http://example.org/ecommerce#"},
        "@graph": orders
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
                    "name": "order-service",
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
                        "name": "get_order",
                        "description": "Get order information by ID. Returns RDF data in JSON-LD format.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "order_id": {
                                    "type": "string",
                                    "description": "The order ID"
                                }
                            },
                            "required": ["order_id"]
                        }
                    },
                    {
                        "name": "get_customer_orders",
                        "description": "Get all orders for a specific customer. Returns RDF data in JSON-LD format.",
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
                        "name": "list_orders",
                        "description": "List all orders. Returns RDF data in JSON-LD format.",
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
        
        if tool_name == "get_order":
            order_id = tool_args.get("order_id")
            result = get_order(order_id)
            
            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Order {order_id} not found"
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
        
        elif tool_name == "get_customer_orders":
            customer_id = tool_args.get("customer_id")
            result = get_customer_orders(customer_id)
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
        
        elif tool_name == "list_orders":
            result = list_orders()
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
