import os
import json
import requests
from typing import Any
from datetime import datetime, timezone
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:8080"
KEYCLOAK_URL = "http://localhost:8989/realms/neone/protocol/openid-connect/token"
CLIENT_ID = "neone-client"
CLIENT_SECRET = "lx7ThS5aYggdsMm42BP3wMrVqKm9WpNY"

# Store extracted IDs
cargo_state = {
    "access_token": None,
    "org_shipper_id": None,
    "org_consignee_id": None,
    "org_fwd_origin_id": None,
    "org_carrier_id": None,
    "pvg_location_id": None,
    "shipment_id": None,
    "piece_id": None,
    "waybill_id": None,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_access_token():
    """Authenticate with Keycloak and get access token"""
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    response = requests.post(KEYCLOAK_URL, data=payload, headers=headers)
    response.raise_for_status()
    
    token = response.json()["access_token"]
    cargo_state["access_token"] = token
    return token

def extract_id_from_header(response):
    """Extract UUID from Location header"""
    location = response.headers.get("Location", "")
    return location.split("/")[-1] if location else None

def make_api_request(method: str, endpoint: str, body: dict = None, extract_id: bool = False):
    """Make authenticated API request"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/ld+json",
        "Accept": "application/ld+json",
        "Authorization": f"Bearer {cargo_state['access_token']}"
    }
    
    # Debug: print request body for events
    if "/logistics-events" in endpoint and body:
        print(f"\n📤 Posting to {endpoint}")
        print(f"Body: {json.dumps(body, indent=2)}")
    
    if method == "POST":
        response = requests.post(url, json=body, headers=headers)
    elif method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "PATCH":
        response = requests.patch(url, json=body, headers=headers)
    
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ API Error: {e}")
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        raise
    
    if extract_id:
        return extract_id_from_header(response)
    
    # Handle empty responses (201/204 with no body)
    if response.status_code in [201, 204] or not response.text:
        return {"status": "success"}
    
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {"status": "success"}

# ============================================================================
# TOOL DEFINITIONS (LangChain Tools using @tool decorator)
# ============================================================================

@tool
def authenticate() -> str:
    """Authenticate with Keycloak and get access token"""
    token = get_access_token()
    return f"✓ Token obtained: {token[:20]}..."

@tool
def create_shipper() -> str:
    """Create LEGO Jiaxing Factory as the shipper organization"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Organization",
        "cargo:name": "LEGO Jiaxing Factory",
        "cargo:description": "The Shipper",
    }
    shipper_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["org_shipper_id"] = shipper_id
    return f"✓ Shipper created: {shipper_id}"

@tool
def create_consignee() -> str:
    """Create LEGO Store Philippines as the consignee"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Organization",
        "cargo:name": "LEGO Store Philippines",
        "cargo:description": "The Consignee",
    }
    consignee_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["org_consignee_id"] = consignee_id
    return f"✓ Consignee created: {consignee_id}"

@tool
def create_forwarder() -> str:
    """Create DHL Global Forwarding China as origin forwarder"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Organization",
        "cargo:name": "DHL Global Forwarding CN",
        "cargo:description": "Origin Forwarder",
    }
    fwd_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["org_fwd_origin_id"] = fwd_id
    return f"✓ Origin Forwarder created: {fwd_id}"

@tool
def create_carrier() -> str:
    """Create Philippine Airlines as the carrier"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Organization",
        "cargo:name": "Philippine Airlines",
        "cargo:description": "The Carrier",
    }
    carrier_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["org_carrier_id"] = carrier_id
    return f"✓ Carrier created: {carrier_id}"

@tool
def create_location() -> str:
    """Create Shanghai Pudong (PVG) location"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Location",
        "cargo:code": "PVG",
        "cargo:locationName": "Shanghai Pudong Airport",
    }
    location_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["pvg_location_id"] = location_id
    return f"✓ Location created: {location_id}"

@tool
def create_shipment() -> str:
    """Create shipment with waybill 079-LEGO-001"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Shipment",
        "cargo:waybillNumber": "079-LEGO-001",
        "cargo:goodsDescription": "LEGO Star Wars Sets",
        "cargo:shipper": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_shipper_id']}"},
        "cargo:consignee": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_consignee_id']}"},
    }
    shipment_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["shipment_id"] = shipment_id
    return f"✓ Shipment created: {shipment_id}"

@tool
def create_piece() -> str:
    """Create physical piece (box) for the shipment"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Piece",
        "cargo:grossWeight": {
            "@type": "cargo:Value",
            "cargo:numericalValue": 50,
            "cargo:unit": "kg",
        },
        "cargo:dimensions": {
            "@type": "cargo:Dimensions",
            "cargo:length": {"@type": "cargo:Value", "cargo:numericalValue": 50, "cargo:unit": "cm"},
            "cargo:width": {"@type": "cargo:Value", "cargo:numericalValue": 50, "cargo:unit": "cm"},
            "cargo:height": {"@type": "cargo:Value", "cargo:numericalValue": 50, "cargo:unit": "cm"},
        },
        "cargo:shipment": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['shipment_id']}"},
    }
    piece_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["piece_id"] = piece_id
    return f"✓ Piece created: {piece_id}"

@tool
def create_waybill() -> str:
    """Create Air Waybill linking shipment, forwarder, and carrier"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Waybill",
        "cargo:waybillNumber": "079-12345678",
        "cargo:shipment": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['shipment_id']}"},
        "cargo:bookingParty": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_fwd_origin_id']}"},
        "cargo:carrier": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_carrier_id']}"},
    }
    waybill_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["waybill_id"] = waybill_id
    return f"✓ Waybill created: {waybill_id}"

@tool
def log_rcs_event() -> str:
    """Log RCS (Received) event at origin"""
    piece_id = cargo_state.get("piece_id")
    org_fwd_id = cargo_state.get("org_fwd_origin_id")
    pvg_loc_id = cargo_state.get("pvg_location_id")
    
    if not piece_id or not org_fwd_id or not pvg_loc_id:
        raise RuntimeError("Cannot log RCS event: missing piece_id, org_fwd_origin_id, or pvg_location_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "RCS",
        "cargo:eventName": "Received from Shipper/Agent",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:eventLocation": {
            "@id": f"{API_BASE_URL}/logistics-objects/{pvg_loc_id}",
            "@type": "cargo:Location"
        },
        "cargo:recordingOrganization": {
            "@id": f"{API_BASE_URL}/logistics-objects/{org_fwd_id}",
            "@type": "cargo:Organization"
        },
        "cargo:partialEventIndicator": False
    }
    
    # Append event directly to piece
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: RCS - Received from Shipper/Agent"

@tool
def log_man_event() -> str:
    """Log MAN (Manifested) event"""
    piece_id = cargo_state.get("piece_id")
    
    if not piece_id:
        raise RuntimeError("Cannot log MAN event: missing piece_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "MAN",
        "cargo:eventName": "Manifested on Flight",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:partialEventIndicator": False
    }
    
    # Append event directly to piece
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: MAN - Manifested on Flight"

@tool
def log_dep_event() -> str:
    """Log DEP (Departure) event"""
    piece_id = cargo_state.get("piece_id")
    
    if not piece_id:
        raise RuntimeError("Cannot log DEP event: missing piece_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "DEP",
        "cargo:eventName": "Flight Departed",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:partialEventIndicator": False
    }
    
    # Append event directly to piece
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: DEP - Flight Departed"

@tool
def log_arr_event() -> str:
    """Log ARR (Arrival) event at destination"""
    piece_id = cargo_state.get("piece_id")
    
    if not piece_id:
        raise RuntimeError("Cannot log ARR event: missing piece_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "ARR",
        "cargo:eventName": "Flight Arrived",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:partialEventIndicator": False
    }
    
    # Append event directly to piece
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: ARR - Flight Arrived"

@tool
def log_dlv_event() -> str:
    """Log DLV (Delivered) event"""
    piece_id = cargo_state.get("piece_id")
    
    if not piece_id:
        raise RuntimeError("Cannot log DLV event: missing piece_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "DLV",
        "cargo:eventName": "Delivered to Delivery Agent",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:partialEventIndicator": False
    }
    
    # Append event directly to piece
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: DLV - Delivered to Delivery Agent"

@tool
def log_pod_event() -> str:
    """Log POD (Proof of Delivery) event"""
    piece_id = cargo_state.get("piece_id")
    shipment_id = cargo_state.get("shipment_id")
    
    if not piece_id or not shipment_id:
        raise RuntimeError("Cannot log POD event: missing piece_id or shipment_id")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:LogisticsEvent",
        "cargo:eventCode": "POD",
        "cargo:eventName": "Delivered to Consignee - Signed by Manager",
        "cargo:creationDate": timestamp,
        "cargo:eventDate": timestamp,
        "cargo:partialEventIndicator": False
    }
    
    # Append event to shipment
    make_api_request("POST", f"/logistics-objects/{shipment_id}/logistics-events", body)
    return "✓ Event logged: POD - Proof of Delivery"

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("LEGO CARGO LOGISTICS WORKFLOW - LangChain + Azure OpenAI")
    print("="*70)
    
    llm = AzureChatOpenAI(
        model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
        azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
        api_version="2025-04-01-preview",
    )
    
    tools = [
        authenticate,
        create_shipper,
        create_consignee,
        create_forwarder,
        create_carrier,
        create_location,
        create_shipment,
        create_piece,
        create_waybill,
        log_rcs_event,
        log_man_event,
        log_dep_event,
        log_arr_event,
        log_dlv_event,
        log_pod_event,
    ]
    
    system_prompt = """You are an intelligent cargo logistics coordinator. 
Your job is to orchestrate a complete LEGO shipment from China to the Philippines.
Execute the workflow step by step in this exact order:
1. Authenticate
2. Create master data (shipper, consignee, forwarder, carrier, location)
3. Create shipment and piece
4. Create waybill
5. Log all logistics events in sequence (RCS → MAN → DEP → ARR → DLV → POD)

Use the tools available to you. After each step, explain what was created.
Wait for each tool to complete before calling the next one."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Use the simpler direct approach with bind_tools
    from langchain_core.messages import HumanMessage
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Simple agentic loop
    messages = [
        HumanMessage(content="Execute the complete LEGO shipment workflow from China to Philippines. Create all entities and log all events in sequence.")
    ]
    
    print("\n🚀 Starting workflow execution...\n")
    
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        # Check if we're done (no tool calls)
        if not response.tool_calls:
            print(f"\n✅ Agent completed: {response.content}")
            break
        
        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            print(f"\n🔧 Executing tool: {tool_name}")
            
            # Find and execute the tool
            tool_to_run = next((t for t in tools if t.name == tool_name), None)
            if tool_to_run:
                try:
                    result = tool_to_run.invoke(tool_call.get("args", {}))
                    print(f"✓ Result: {result}")
                except Exception as e:
                    result = f"Error: {str(e)}"
                    print(f"✗ Error: {result}")
            else:
                result = f"Tool {tool_name} not found"
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
    
    result = response
    
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)
    print(f"\nFinal State:")
    print(json.dumps(cargo_state, indent=2))
    print("="*70)