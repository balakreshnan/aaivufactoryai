from openai import AzureOpenAI
import streamlit as st  
from azure.cosmos import CosmosClient, exceptions  
import pandas as pd  
from datetime import datetime
import os
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load .env file
load_dotenv()
  
# Azure Cosmos DB Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("DATABASE_NAME")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

# Azure Cognitive Search Configuration
SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_AI_SEARCH_KEY")

aoaiclient = AzureOpenAI(
  azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
  api_version="2024-10-21",
)
  

   
def authenticate_admin(username, password):  
    try:  
        # Connect to Azure Cosmos DB  
        credential = DefaultAzureCredential()

        client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client(CONTAINER_NAME)

        query = f"SELECT * FROM c WHERE c.username = '{username}' AND c.password = '{password}'"
        users = list(container.query_items(query, enable_cross_partition_query=True))

        if users:
            return users[0]  # Return the first matching user record 
    except exceptions.CosmosHttpResponseError as e:  
        st.error(f"An error occurred: {e}")  
        return False  
    
def show_token_usage_and_hits(admin_user, company_name):  
    try:  
        # Connect to Azure Cosmos DB  
        credential = DefaultAzureCredential()

        client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client("userlogs")
        # Query documents for the specified admin user and company name  
        # query = f"SELECT c.token_input, c.token_output, c.timestamp FROM c WHERE c.user = '{admin_user}' AND c.company_name = '{company_name}'"
        query = f"SELECT c.token_input, c.token_output, c.timestamp FROM c WHERE c.company_name = '{company_name}'"   
        st.write(query)
        items = list(container.query_items(query=query, enable_cross_partition_query=True))  
  
        if not items:  
            st.warning("No data found for the specified admin user and company name.")  
            return  
  
        # Convert the data to a pandas DataFrame  
        data = []  
        for item in items:  
            data.append({  
                "token_input": item.get("token_input", 0),  
                "token_output": item.get("token_output", 0),  
                "timestamp": item.get("timestamp")  
            })  
          
        df = pd.DataFrame(data)  
  
        # Convert timestamp to datetime  
        df['timestamp'] = pd.to_datetime(df['timestamp'])  
  
        # Calculate total tokens (input + output)  
        df['total_tokens'] = df['token_input'] + df['token_output']  
  
        # Group by month  
        df['month'] = df['timestamp'].dt.to_period('M')  
        monthly_token_usage = df.groupby('month')['total_tokens'].sum().reset_index()  
        monthly_token_usage['hits'] = df.groupby('month').size().values  
  
        # Display the result  
        st.write(f"### Total Token Usage and Hits by Month for {admin_user} at {company_name}")  
        st.table(monthly_token_usage)  
    except exceptions.CosmosHttpResponseError as e:  
        st.error(f"An error occurred: {e}")  
  
def show_users():  
    try:  
        credential = DefaultAzureCredential()

        client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client(CONTAINER_NAME)
        # Query all users  
        query = "SELECT c.id, c.username, c.email, c.roles FROM c"  
        users = list(container.query_items(query=query, enable_cross_partition_query=True))  
          
        st.write("### Users List")  
        for user in users:  
            st.write(f"ID: {user['id']}, Username: {user['username']}, Email: {user['email']}, Roles: {user['roles']}")  
            show_token_usage_and_hits(user['username'], user['company_name'])
    except exceptions.CosmosHttpResponseError as e:  
        st.error(f"An error occurred: {e}")  

# Streamlit app  
def main():  
    st.title("Admin Interface")  
    # User Authentication
    with st.sidebar:
        st.header("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            user = authenticate_admin(username, password)
            if user:
                st.success(f"Welcome, {user['username']}!")
                #indices = get_user_indices(user)
                st.session_state["user"] = user
                #st.session_state["indices"] = indices
            else:
                st.error("Invalid credentials. Please try again.")

        # Logout button
        if st.button("Logout"):
            st.session_state.clear()  # Clear session state
            #st.experimental_rerun()  # Reload app
            st.write("You have been logged out.")

    # If authenticated
    if "user" in st.session_state:
        st.sidebar.success("Authenticated!")

        welcome_message = (
            f"Welcome {st.session_state['user']['username']} "
            f"from Company: {st.session_state['user']['companyname']}!"
        )
        st.title(welcome_message)
        headers = st.context.headers  # Convert the string to a dictionary
        
        # Access individual values  
        host = headers.get("Host")  
        origin = headers.get("Origin")  
        user_agent = headers.get("User-Agent")  
        cookie = headers.get("Cookie") 

        show_token_usage_and_hits(st.session_state["user"]["username"], st.session_state["user"]["companyname"])
  
if __name__ == "__main__":  
    main()  