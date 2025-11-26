import os
import json
import uuid
from typing import Any, Dict, List
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

load_dotenv()

cargo_data = {
    "shipments": [],
    "waybills": [],
    "parties": [],
    "companies": [],
    "locations": [],
    "pieces": [],
    "items": [],
    "products": []
}

file_path = "cargo_data.json"

def save_data():
    with open(file_path, "w") as f:
        json.dump(cargo_data, f, indent=2)

def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

@tool
def create_company(name: str, short_name: str, iata_code: int, location_identifier: str, based_at: str) -> str:
    """Create a company with name, short name, IATA code, location identifier, and base location"""
    company_id = generate_id("Company")
    company = {
        "company_id": company_id,
        "name": name,
        "shortName": short_name,
        "iataCargoAgentCode": iata_code,
        "iataCargoAgentLocationIdentifier": location_identifier,
        "basedAtLocation": based_at
    }
    cargo_data["companies"].append(company)
    return f"Company created: {company_id}"

@tool
def create_location(location_name: str, location_type: str, location_codes: str = "") -> str:
    """Create a location with name, type, and optional codes"""
    location_id = generate_id("Location")
    location = {
        "location_id": location_id,
        "locationName": location_name,
        "locationType": location_type,
        "locationCodes": location_codes if location_codes else None
    }
    cargo_data["locations"].append(location)
    return f"Location created: {location_id}"

@tool
def create_party(party_role: str, company_id: str) -> str:
    """Create a party with role and company ID"""
    party_id = generate_id("Party")
    party = {
        "party_id": party_id,
        "partyROLE": party_role,
        "partyDetails": company_id
    }
    cargo_data["parties"].append(party)
    return f"Party created: {party_id}"

@tool
def create_shipment(goods_description: str, total_gross_weight: float, total_piece: int, incoterms: str) -> str:
    """Create a shipment with goods description, total weight, piece count, and incoterms"""
    shipment_id = generate_id("Shipment")
    shipment = {
        "id": f"https://onerecord.iata.org/Shipment/{shipment_id}",
        "goodsDescription": goods_description,
        "totalGrossWeight": total_gross_weight,
        "totalPiece": total_piece,
        "incoterms": incoterms
    }
    cargo_data["shipments"].append(shipment)
    return f"Shipment created: {shipment_id}"

@tool
def create_waybill(waybill_type: str, waybill_prefix: int, waybill_number: int, shipment_id: str, 
                   departure_location_id: str, arrival_location_id: str, modular_check: bool,
                   carrier_signature: str, consignor_signature: str, shipping_info: str) -> str:
    """Create a waybill with type, prefix, number, shipment ID, locations, and signatures"""
    waybill_id = generate_id("Waybill")
    waybill = {
        "waybill_id": waybill_id,
        "waybillType": waybill_type,
        "waybillPrefix": waybill_prefix,
        "waybillNumber": waybill_number,
        "shipment": shipment_id,
        "departureLocation": departure_location_id,
        "arrivalLocation": arrival_location_id,
        "modularCheckNumber": modular_check,
        "carrierDeclarationDate": datetime.now(timezone.utc).isoformat(),
        "carrierDeclarationSignature": carrier_signature,
        "consignorDeclarationSignature": consignor_signature,
        "shippingInfo": shipping_info
    }
    cargo_data["waybills"].append(waybill)
    return f"Waybill created: {waybill_id}"

@tool
def create_piece(shipment_id: str, upid: int, gross_weight: float, goods_description: str) -> str:
    """Create a piece with shipment ID, UPID, weight, and description"""
    piece_id = generate_id("Piece")
    dimensions_id = generate_id("DIM")
    piece = {
        "id": piece_id,
        "ofShipment": shipment_id,
        "upid": upid,
        "dimensions": dimensions_id,
        "grossWeight": gross_weight,
        "goodsDescription": goods_description
    }
    cargo_data["pieces"].append(piece)
    return f"Piece created: {piece_id}"

@tool
def create_product(product_name: str, product_code: str, price: float) -> str:
    """Create a product with name, code, and price"""
    product_id = generate_id("Product")
    product = {
        "id": product_id,
        "name": product_name,
        "code": product_code,
        "price": price
    }
    cargo_data["products"].append(product)
    return f"Product created: {product_id}"

@tool
def create_item(piece_id: str, product_id: str, item_quantity: int, weight: float, unit_price: float) -> str:
    """Create an item linking piece to product with quantity, weight, and price"""
    item_id = generate_id("Item")
    item = {
        "id": item_id,
        "inPiece": piece_id,
        "ofProduct": product_id,
        "itemQuantity": item_quantity,
        "weight": weight,
        "unitPrice": unit_price
    }
    cargo_data["items"].append(item)
    return f"Item created: {item_id}"

@tool
def get_last_company_id() -> str:
    """Get the ID of the last created company"""
    if cargo_data["companies"]:
        return cargo_data["companies"][-1]["company_id"]
    return "No companies created yet"

@tool
def get_last_location_id() -> str:
    """Get the ID of the last created location"""
    if cargo_data["locations"]:
        return cargo_data["locations"][-1]["location_id"]
    return "No locations created yet"

@tool
def get_last_shipment_id() -> str:
    """Get the ID of the last created shipment"""
    if cargo_data["shipments"]:
        return cargo_data["shipments"][-1]["id"]
    return "No shipments created yet"

@tool
def get_last_piece_id() -> str:
    """Get the ID of the last created piece"""
    if cargo_data["pieces"]:
        return cargo_data["pieces"][-1]["id"]
    return "No pieces created yet"

@tool
def get_last_product_id() -> str:
    """Get the ID of the last created product"""
    if cargo_data["products"]:
        return cargo_data["products"][-1]["id"]
    return "No products created yet"

if __name__ == "__main__":
    llm = AzureChatOpenAI(
        model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
        azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
        api_version="2025-04-01-preview",
    )
    
    tools = [
        create_company,
        create_location,
        create_party,
        create_shipment,
        create_waybill,
        create_piece,
        create_product,
        create_item,
        get_last_company_id,
        get_last_location_id,
        get_last_shipment_id,
        get_last_piece_id,
        get_last_product_id
    ]
    
    system_prompt = """You are a cargo data generator. Create realistic dummy data following this workflow:

1. Create 3-4 companies (shipper, consignee, forwarder, carrier) with realistic IATA codes
2. Create 2-3 locations (origin, destination, warehouse)
3. Create parties linking companies to their roles (shipper, consignee, etc)
4. Create 2-3 shipments with different LEGO products
5. For each shipment:
   - Create a waybill linking to that shipment and locations
   - Create 2-3 pieces for that shipment
   - Create 3-5 products (different LEGO sets)
   - Create items linking pieces to products

Use getter tools to retrieve IDs from previously created entities to maintain referential integrity.
Make the data realistic with proper weights, quantities, and descriptions."""
    
    llm_with_tools = llm.bind_tools(tools)
    
    messages = [
        HumanMessage(content="Generate complete cargo shipment data with all related entities. Create multiple shipments with consistent relationships between all tables.")
    ]
    
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        if not response.tool_calls:
            break
        
        for tool_call in response.tool_calls:
            tool_to_run = next((t for t in tools if t.name == tool_call["name"]), None)
            if tool_to_run:
                try:
                    result = tool_to_run.invoke(tool_call.get("args", {}))
                except Exception as e:
                    result = f"Error: {str(e)}"
            else:
                result = f"Tool {tool_call['name']} not found"
            
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
    

    save_data()

    
    try:
        from convert import convert_top_level_json_to_csvs
        converted_files = convert_top_level_json_to_csvs(file_path, out_dir=None, verbose=True)
        print("Conversion completed. Created files:")
        for p in converted_files:
            print(" -", p)
    except Exception as e:
        print(f"Conversion to CSV failed: {e}")