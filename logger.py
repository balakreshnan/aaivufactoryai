import datetime
import time
import os
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Azure Cosmos DB Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("DATABASE_NAME")
CONTAINER_NAME = "userlogs"  # Container name for storing logs

def log_metrics(user, company_name, ip_address, user_agent, query, response, browser_utc, token_input, token_output, totalseconds):
    """Log user activity and chat metrics into Azure Cosmos DB."""
    credential = DefaultAzureCredential()

    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    log_entry = {
        "id": str(datetime.datetime.now().timestamp()),
        "user": user,
        "company_name": company_name,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "timestamp": datetime.datetime.now().isoformat(),
        "browser_utc": browser_utc,
        "query": query,
        "response": response,
        "token_input": token_input,
        "token_output": token_output,
        "totalseconds": totalseconds
    }

    try:
        container.create_item(body=log_entry)
        return True
    except exceptions.CosmosHttpResponseError as e:
        print(f"Error logging metrics: {e}")
        return False