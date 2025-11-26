import os
import json
import requests
from typing import Any
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:8080"
KEYCLOAK_URL = "http://localhost:8989/realms/neone/protocol/openid-connect/token"
CLIENT_ID = "neone-client"
CLIENT_SECRET = "lx7ThS5aYggdsMm42BP3wMrVqKm9WpNY"
STATE_FILE = "cargo_state.json"

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
# STATE PERSISTENCE - DEFINED FIRST
# ============================================================================

def load_state():
    """Load state from file if it exists"""
    global cargo_state
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            saved_state = json.load(f)
            cargo_state.update(saved_state)
            print(f"✓ Loaded saved state from {STATE_FILE}")
            return True
    return False

def save_state():
    """Save state to file for reuse"""
    with open(STATE_FILE, "w") as f:
        json.dump(cargo_state, f, indent=2)
    print(f"✓ Saved state to {STATE_FILE}")

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
    
    if response.status_code in [201, 204] or not response.text:
        return {"status": "success"}
    
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {"status": "success"}

# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@tool
def authenticate() -> str:
    """Authenticate with Keycloak and get access token"""
    token = get_access_token()
    return f"✓ Token obtained: {token[:20]}..."

@tool
def create_shipper() -> str:
    """Create LEGO Jiaxing Factory as the shipper organization"""
    if cargo_state["org_shipper_id"]:
        return f"✓ Using existing shipper: {cargo_state['org_shipper_id']}"
    
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Organization",
        "cargo:name": "LEGO Jiaxing Factory",
        "cargo:description": "The Shipper",
        "cargo:basedAtLocation": "Jiaxing, China",
        
    }
    shipper_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["org_shipper_id"] = shipper_id
    return f"✓ Shipper created: {shipper_id}"

@tool
def create_consignee() -> str:
    """Create LEGO Store Philippines as the consignee"""
    if cargo_state["org_consignee_id"]:
        return f"✓ Using existing consignee: {cargo_state['org_consignee_id']}"
    
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
    if cargo_state["org_fwd_origin_id"]:
        return f"✓ Using existing forwarder: {cargo_state['org_fwd_origin_id']}"
    
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
    if cargo_state["org_carrier_id"]:
        return f"✓ Using existing carrier: {cargo_state['org_carrier_id']}"
    
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
    if cargo_state["pvg_location_id"]:
        return f"✓ Using existing location: {cargo_state['pvg_location_id']}"
    
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
def create_shipment(waybill_number: str, goods_description: str) -> str:
    """Create shipment with waybill number and goods description - ALWAYS creates new"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Shipment",
        "cargo:waybillNumber": waybill_number,
        "cargo:goodsDescription": goods_description,
        "cargo:shipper": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_shipper_id']}"},
        "cargo:consignee": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_consignee_id']}"},
    }
    shipment_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["shipment_id"] = shipment_id
    return f"✓ Shipment created with waybill {waybill_number} ({goods_description}): {shipment_id}"

@tool
def create_piece(gross_weight: float, length: float, width: float, height: float, unit: str = "kg") -> str:
    """Create physical piece (box) for the shipment - ALWAYS creates new"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Piece",
        "cargo:grossWeight": {
            "@type": "cargo:Value",
            "cargo:numericalValue": gross_weight,
            "cargo:unit": unit,
        },
        "cargo:dimensions": {
            "@type": "cargo:Dimensions",
            "cargo:length": {"@type": "cargo:Value", "cargo:numericalValue": length, "cargo:unit": "cm"},
            "cargo:width": {"@type": "cargo:Value", "cargo:numericalValue": width, "cargo:unit": "cm"},
            "cargo:height": {"@type": "cargo:Value", "cargo:numericalValue": height, "cargo:unit": "cm"},
        },
        "cargo:shipment": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['shipment_id']}"},
    }
    piece_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["piece_id"] = piece_id
    return f"✓ Piece created: {gross_weight}{unit}, Dimensions {length}x{width}x{height}cm: {piece_id}"

@tool
def create_waybill(waybill_number: str) -> str:
    """Create Air Waybill (AWB) - ALWAYS creates new"""
    body = {
        "@context": {"cargo": "https://onerecord.iata.org/ns/cargo#"},
        "@type": "cargo:Waybill",
        "cargo:waybillNumber": waybill_number,
        "cargo:shipment": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['shipment_id']}"},
        "cargo:bookingParty": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_fwd_origin_id']}"},
        "cargo:carrier": {"@id": f"{API_BASE_URL}/logistics-objects/{cargo_state['org_carrier_id']}"},
    }
    waybill_id = make_api_request("POST", "/logistics-objects", body, extract_id=True)
    cargo_state["waybill_id"] = waybill_id
    return f"✓ Waybill created with number {waybill_number}: {waybill_id}"

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
    
    make_api_request("POST", f"/logistics-objects/{piece_id}/logistics-events", body)
    return "✓ Event logged: DLV - Delivered to Delivery Agent"

@tool
def log_pod_event() -> str:
    """Log POD (Proof of Delivery) event"""
    shipment_id = cargo_state.get("shipment_id")
    
    if not shipment_id:
        raise RuntimeError("Cannot log POD event: missing shipment_id")
    
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
    
    make_api_request("POST", f"/logistics-objects/{shipment_id}/logistics-events", body)
    return "✓ Event logged: POD - Proof of Delivery"

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("LEGO CARGO LOGISTICS WORKFLOW - LangChain + Azure OpenAI")
    print("="*70)
    
    # Load saved state if it exists
    print("\n📦 Checking for saved state...")
    state_loaded = load_state()
    
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
2. Create master data (shipper, consignee, forwarder, carrier, location) - reuse if already exists
3. Create shipment with UNIQUE LEGO product and waybill number EACH TIME
4. Create piece with realistic weight and dimensions for that LEGO product
5. Create waybill with unique AWB number
6. Log all logistics events in sequence (RCS → MAN → DEP → ARR → DLV → POD)

REQUIREMENTS - GENERATE DIFFERENT LEGO PRODUCTS EACH TIME:
- Shipment waybill: Use format like 280-LEGO-1125, 750-LEGO-0825, 390-LEGO-2401
- Goods: Different LEGO product sets each time:
  * "LEGO Star Wars Collection - Multiple Sets" (120kg, 100x80x60cm)
  * "LEGO Architecture Series Assortment" (85kg, 90x70x50cm)
  * "LEGO Technic Heavy Machinery Sets" (200kg, 150x100x80cm)
  * "LEGO Friends Playset Bundle" (60kg, 80x60x45cm)
  * "LEGO Classic Large Brick Sets" (95kg, 100x75x55cm)
  * "LEGO Ninjago Movie Collection" (110kg, 105x75x65cm)
  * "LEGO Harry Potter Hogwarts Sets" (140kg, 120x85x70cm)
  * "LEGO Ideas Creator Sets Mix" (75kg, 95x65x50cm)
- AWB numbers: Unique like 280-98765432, 750-54321098, 390-11223344

CRITICAL: Create a NEW DIFFERENT LEGO product shipment EVERY RUN.
Reuse the same shipper/consignee/forwarder/carrier/location (saved in state).
Use the tools with different parameters each execution."""
    
    llm_with_tools = llm.bind_tools(tools)
    
    messages = [
        HumanMessage(content="Create a NEW LEGO shipment with DIFFERENT product type, waybill number, weight, and dimensions than previous runs. Execute the complete workflow from authentication through all logistics events.")
    ]
    
    print("\n🚀 Starting workflow execution...\n")
    
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        if not response.tool_calls:
            print(f"\n✅ Agent completed: {response.content}")
            break
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            print(f"\n🔧 Executing tool: {tool_name}")
            
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
            
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
    
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)
    print(f"\nFinal State:")
    print(json.dumps(cargo_state, indent=2))
    
    # Save state for next run
    save_state()
    print("="*70)