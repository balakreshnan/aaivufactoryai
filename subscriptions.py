from datetime import datetime, timedelta  
from decimal import Decimal  
import json  
import os
from collections import defaultdict 
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
  
class SubscriptionPlan:  
    def __init__(self, max_tokens, monthly_fee, overage_fee_per_token):  
        self.max_tokens = max_tokens  
        self.monthly_fee = monthly_fee  
        self.overage_fee_per_token = overage_fee_per_token  
  
class UserSubscription:  
    def __init__(self, user, company_name, plan):  
        self.user = user  
        self.company_name = company_name  
        self.plan = plan  
        self.current_usage = 0  
  
    def add_usage(self, tokens):  
        self.current_usage += tokens  
  
    def calculate_charges(self):  
        if self.current_usage > self.plan.max_tokens:  
            overage = self.current_usage - self.plan.max_tokens  
            return self.plan.monthly_fee + (overage * self.plan.overage_fee_per_token)  
        return self.plan.monthly_fee  
  
    def reset_usage(self):  
        self.current_usage = 0  
  
# Example usage  
standard_plan = SubscriptionPlan(max_tokens=10000, monthly_fee=Decimal('100.00'), overage_fee_per_token=Decimal('0.01'))  
john_subscription = UserSubscription('john_doe', 'Company A', standard_plan)  

def calculate_monthly_usage(user_logs):  
    usage_by_company = defaultdict(int)  
      
    for log in user_logs:  
        data = json.loads(log)  # Assuming logs are in JSON format  
        company_name = data['company_name']  
        token_input = data.get('token_input', 0)  
        token_output = data.get('token_output', 0)  
        usage_by_company[company_name] += token_input + token_output  
      
    return usage_by_company  
  
# Sample logs  
user_logs = [  
    '{"company_name": "Company A", "token_input": 6001, "token_output": 254}',  
    # Add more logs here  
]  
  
usage = calculate_monthly_usage(user_logs) 