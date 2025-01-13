from datetime import datetime
import time
import streamlit as st
from azure.cosmos import CosmosClient, exceptions
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI, AzureChatOpenAI
from azure.identity import DefaultAzureCredential
from langchain.document_loaders import PyPDFLoader
from langchain.vectorstores import FAISS
from mfgcompliance import extractmfgresults
from logger import log_metrics
import tempfile
import os
import PyPDF2

from openai import AzureOpenAI
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

client = AzureOpenAI(
  azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
  api_version="2024-10-21",
)

def authenticate_user(username, password):
    """Authenticate user using Azure Cosmos DB."""
    #client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    credential = DefaultAzureCredential()

    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    query = f"SELECT * FROM c WHERE c.username = '{username}' AND c.password = '{password}'"
    users = list(container.query_items(query, enable_cross_partition_query=True))

    if users:
        return users[0]  # Return the first matching user record
    return None

def get_user_indices(user):
    """Retrieve indices the user has access to."""
    return user.get("indices", [])  # Assuming `indices` is a list of accessible indices

def create_search_client(index_name):
    """Create an Azure Cognitive Search client for a given index."""

    return SearchClient(endpoint=SEARCH_ENDPOINT, index_name=index_name, credential=SEARCH_KEY)

def search_and_chat(search_client, query, chat_history, index_name):
    """Perform a search query and integrate results into a chat response."""
    results = extractmfgresults(query, index_name)  # Assuming this function returns relevant documents
    # retrieved_texts = [result["content"] for result in results]  # Assuming documents have a 'content' field

    #chat_model = ChatOpenAI(model="gpt-4", temperature=0)
    chat_model = AzureChatOpenAI(azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), api_key=os.getenv("AZURE_OPENAI_KEY"), 
                                 model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
                                 , temperature=0, api_version="2024-10-21")                                                      
    chain = ConversationalRetrievalChain.from_llm(chat_model, retriever=results)

    response = chain.run({"question": query, "chat_history": chat_history})
    return response

def upload_and_process_pdf(uploaded_file):
    """Upload and process a PDF file to create a retriever."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(uploaded_file.read())
        temp_pdf_path = temp_file.name

    loader = PyPDFLoader(temp_pdf_path)
    documents = loader.load()
    vectorstore = FAISS.from_documents(documents)
    os.unlink(temp_pdf_path)  # Clean up the temporary file
    return vectorstore.as_retriever()

def process_pdf(uploaded_file):
    returntxt = ""
    """Upload and process a PDF file to create a retriever."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(uploaded_file.read())
        temp_pdf_path = temp_file.name

    loader = PyPDFLoader(temp_pdf_path)
    documents = loader.load()
    vectorstore = FAISS.from_documents(documents)
    os.unlink(temp_pdf_path)  # Clean up the temporary file


    return vectorstore.as_retriever()

def extract_text_from_pdf(pdf_file):
    """
    Extract text from a PDF file using PyPDF2
    
    Args:
        pdf_file: Uploaded PDF file object from Streamlit
    Returns:
        str: Extracted text from the PDF
    """
    try:
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Get the number of pages
        num_pages = len(pdf_reader.pages)
        
        # Initialize text variable
        text = ""
        
        # Extract text from each page
        for page_num in range(num_pages):
            # Get the page object
            page = pdf_reader.pages[page_num]
            
            # Extract text from page
            text += f"\nPage {page_num + 1}\n"
            text += page.extract_text()
            text += "\n" + "-"*50
            
        return text
    
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def predict(file, query, user_info, ip_address, user_agent, browser_utc):
    history_openai_format = []
    #file_paths = [file.name for file in upload_button]
    pdftext = ""
    #print('upload_button:', file)
    try:
        #file_paths = upload_file(files)
        print('upload_button:', file)
        pdftext = extract_text_from_pdf(file)

    except Exception as e:
        print('Error:', e)
        file_paths = []

    start_time = time.time()

    # print('Abstract Text:', pdftext)  

    
    message_text = [
    {"role":"system", "content":f"""You are Manufacturing Complaince, OSHA, CyberSecurity AI agent. Be politely, and provide positive tone answers.
     Based on the question do a detail analysis on information and provide the best answers.

     Use the data source content provided to answer the question.
     Data Source: {pdftext}
     Be polite and provide posite responses. If user is asking you to do things that are not specific to this context please ignore.
     If not sure, ask the user to provide more information.
     Extract Title content from the document. Show the Title, url as citations which is provided as url: as [url1] [url2].
    ."""}, 
    {"role": "user", "content": f"""{query}. Provide summarized content based on the question asked."""}]

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"), #"gpt-4-turbo", # model = "deployment_name".
        messages=message_text,
        temperature=0.0,
        top_p=0.0,
        seed=42,
        max_tokens=1000,
    )

    partial_message = ""
    # calculate the time it took to receive the response
    response_time = time.time() - start_time

    # print the time delay and text received
    print(f"Full response from model received {response_time:.2f} seconds after request")
    #print(f"Full response received:\n{response}")

    returntext = response.choices[0].message.content + f" \nTime Taken: ({response_time:.2f} seconds)"

    # Extract token usage metrics
    token_usage = response.usage  # Extract usage details
    input_tokens = token_usage.prompt_tokens
    output_tokens = token_usage.completion_tokens
    total_tokens = token_usage.total_tokens

    log_metrics(
        user=user_info['username'],
        company_name=user_info.get('companyname', 'unknown'),
        ip_address=ip_address,
        user_agent=user_agent,
        query=query,
        response=response.choices[0].message.content,  # Extracted response content
        browser_utc=browser_utc,
        token_input=input_tokens,
        token_output=output_tokens,
        totalseconds=response_time
    )


    return returntext

def main():
    #st.title("🔐 AI Chat with Azure Search")

    # User Authentication
    with st.sidebar:
        st.header("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            user = authenticate_user(username, password)
            if user:
                st.success(f"Welcome, {user['username']}!")
                indices = get_user_indices(user)
                st.session_state["user"] = user
                st.session_state["indices"] = indices
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

        # Display user indices
        st.subheader("Available Indices")
        indices = st.session_state.get("indices", [])
        # selected_index = st.selectbox("Choose an index to interact with:", indices)
        # Extract display names for the selectbox  
        # Extract names and ids  
        index_names = [index["name"] for index in indices]  
        index_mapping = {index["name"]: index["id"] for index in indices}  
        
        # Create a selectbox with display names  
        selected_name = st.selectbox("Choose an index to interact with:", index_names)  
        
        # Get the corresponding ID for the selected name  
        selected_id = index_mapping[selected_name]

        # PDF Upload
        st.subheader("Upload and Chat with Your PDF")
        uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
        

        # Chat Interface
        if selected_name:
            # Get the corresponding ID for the selected name  
            selected_id = index_mapping[selected_name]
            # st.subheader(f"Chat with Index: {selected_index['name']}")
            st.subheader(f"Chat with Index: {selected_id}")

            # search_client = create_search_client(selected_index['id'])
            search_client = create_search_client(selected_id)

            user_info = st.session_state["user"]
            chat_history = st.session_state.get("chat_history", [])
            #ip_address = st.request.remote_addr if hasattr(st.request, 'remote_addr') else "unknown"
            #user_agent = st.request.headers.get("User-Agent", "unknown")
            ip_address = "WIP"  # Placeholder for IP address
            user_agent = "WIP"  # Placeholder for user agent
            browser_utc = datetime.now().isoformat()  # Placeholder for browser UTC time
            user_input = st.text_input("Ask a question:", "what are the personal protection i should consider in manufacturing?")

            if st.button("Submit") and user_input:
                # response = search_and_chat(search_client, user_input, chat_history, selected_index['id'])
                if uploaded_file:
                    #retriever = process_pdf(uploaded_file)
                    
                    response = predict(uploaded_file, user_input, user_info, ip_address, user_agent, browser_utc)
                else:
                    response = extractmfgresults(user_input, selected_id, user_info, ip_address, user_agent, browser_utc)
                chat_history.append((user_input, response))
                st.session_state["chat_history"] = chat_history

                # Extract token usage metrics                   
                #log_metrics(user_info['username'], user_info.get('companyname', 'unknown'), ip_address, user_agent, user_input, response, browser_utc, token_input, token_output)

            for question, answer in chat_history:
                st.write(f"**You:** {question}")
                st.write(f"**AI:** {answer}")

if __name__ == "__main__":
    main()
