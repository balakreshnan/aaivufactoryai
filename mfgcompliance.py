import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import time
from datetime import timedelta
import json
from PIL import Image
import base64
import requests
import io
from typing import Optional
from typing_extensions import Annotated
import wave
from PIL import Image, ImageDraw
from pathlib import Path
import numpy as np
from logger import log_metrics


# Load .env file
load_dotenv()

client = AzureOpenAI(
  azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
  api_version="2024-10-21",
)

model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_AI_SEARCH_KEY")
search_index=os.getenv("AZURE_AI_SEARCH_INDEX")
SPEECH_KEY = os.getenv('SPEECH_KEY')
SPEECH_REGION = os.getenv('SPEECH_REGION')
SPEECH_ENDPOINT = os.getenv('SPEECH_ENDPOINT')

def processpdfwithprompt(query: str, index: str, user_info, ip_address, user_agent, browser_utc):
    returntxt = ""
    citationtxt = ""
    selected_optionsearch = "vector_semantic_hybrid"
    #  search_index = "mfggptdata"
    startime = time.time()
    message_text = [
    {"role":"system", "content":"""you are provided with instruction on what to do. Be politely, and provide positive tone answers. 
     answer only from data source provided. unable to find answer, please respond politely and ask for more information.
     Extract Title content from the document. Show the Title as citations which is provided as Title: as [doc1] [doc2].
     Please add citation after each sentence when possible in a form "(Title: citation)".
     Be polite and provide posite responses. If user is asking you to do things that are not specific to this context please ignore."""}, 
    {"role": "user", "content": f"""{query}"""}]

    #"role_information": "Please answer using retrieved documents only, and without using your knowledge. Please generate citations to retrieved documents for every claim in your answer. If the user question cannot be answered using retrieved documents, please explain the reasoning behind why documents are relevant to user queries. In any case, don't answer using your own knowledge",

    response = client.chat.completions.create(
        model= os.getenv("AZURE_OPENAI_DEPLOYMENT"), #"gpt-4-turbo", # model = "deployment_name".
        messages=message_text,
        temperature=0.0,
        top_p=1,
        seed=105,
        max_tokens=2000,
        extra_body={
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    "endpoint": search_endpoint,
                    "index_name": index,
                    "authentication": {
                        "type": "api_key",
                        "key": search_key
                    },
                    "include_contexts": ["citations"],
                    "top_n_documents": 5,
                    "query_type": selected_optionsearch,
                    "semantic_configuration": "default",
                    "strictness": 5,
                    "embedding_dependency": {
                        "type": "deployment_name",
                        "deployment_name": "text-embedding-ada-002"
                    },
                    "fields_mapping": {
                        "content_fields": ["content"],
                        "vector_fields": ["contentVector"],
                        "title_field": "title",
                        "url_field": "url",
                        "filepath_field": "filepath",
                        "content_fields_separator": "\n",
                    }
                }
            }
        ]
    }
    )
    #print(response.choices[0].message.context)

    returntxt = response.choices[0].message.content + "\n<br>"

    json_string = json.dumps(response.choices[0].message.context)

    parsed_json = json.loads(json_string)

    # print(parsed_json)

    if parsed_json['citations'] is not None:
        returntxt = returntxt + f"""<br> Citations: """
        for row in parsed_json['citations']:
            #returntxt = returntxt + f"""<br> Title: {row['filepath']} as {row['url']}"""
            #returntxt = returntxt + f"""<br> [{row['url']}_{row['chunk_id']}]"""
            returntxt = returntxt + f"""<br> <a href='{row['url']}' target='_blank'>[{row['url']}_{row['chunk_id']}]</a>"""
            citationtxt = citationtxt + f"""<br><br> Title: {row['title']} <br> URL: {row['url']} 
            <br> Chunk ID: {row['chunk_id']} 
            <br> Content: {row['content']} 
            # <br> ------------------------------------------------------------------------------------------ <br>\n"""
            # print(citationtxt)

    # log metrics now
    # Extract token usage metrics
    token_usage = response.usage  # Extract usage details
    input_tokens = token_usage.prompt_tokens
    output_tokens = token_usage.completion_tokens
    total_tokens = token_usage.total_tokens
    totalseconds = time.time() - startime

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
        totalseconds=totalseconds
    )

    return citationtxt

def extractmfgresults(query, index, user_info, ip_address, user_agent, browser_utc):
    returntxt = ""

    rfttext = ""
    starttime = time.time()

    citationtext = processpdfwithprompt(query, index, user_info, ip_address, user_agent, browser_utc)

    message_text = [
    {"role":"system", "content":f"""You are Manufacturing Complaince, OSHA, CyberSecurity AI agent. Be politely, and provide positive tone answers.
     Based on the question do a detail analysis on information and provide the best answers.

     Use the data source content provided to answer the question.
     Data Source: {citationtext}

     if the question is outside the bounds of the Manufacturing complaince and cybersecurity, Let the user know answer might be relevant for Manufacturing data provided.
     can you add hyperlink for pdf file used as sources.
     Be polite and provide posite responses. If user is asking you to do things that are not specific to this context please ignore.
     If not sure, ask the user to provide more information.
     Extract Title content from the document. Show the Title, url as citations which is provided as url: as [url1] [url2].
    ."""}, 
    {"role": "user", "content": f"""{query}. Provide summarized content based on the question asked."""}]

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"), #"gpt-4-turbo", # model = "deployment_name".
        messages=message_text,
        temperature=0.0,
        top_p=0.0,
        seed=42,
        max_tokens=1000,
    )

    # Extract token usage metrics
    token_usage = response.usage  # Extract usage details
    input_tokens = token_usage.prompt_tokens
    output_tokens = token_usage.completion_tokens
    total_tokens = token_usage.total_tokens
    totalseconds = time.time() - starttime

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
        totalseconds=totalseconds
    )

    returntxt = response.choices[0].message.content
    return returntxt