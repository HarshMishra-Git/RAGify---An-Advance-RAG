import os
import logging
import requests
import json
import time
from flask import current_app
from app import socketio
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import format_tool_to_openai_function
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

class QueryDocumentsTool(BaseTool):
    name = "query_documents"
    description = "Query the document database to find relevant information based on the user's question."
    
    def _run(self, query: str):
        from pathway_processor import query_documents
        results = query_documents(query, top_k=3)
        
        if not results:
            return "No relevant documents found."
        
        context = "\n\n".join([
            f"Document {i+1}: {doc['title']}\n{doc['content'][:300]}..."
            for i, doc in enumerate(results)
        ])
        return f"Retrieved the following relevant documents:\n{context}"

class TogetherAIService:
    def __init__(self):
        self.api_key = os.environ.get("TOGETHER_API_KEY", current_app.config.get("TOGETHER_API_KEY"))
        if not self.api_key:
            logging.error("Together AI API key not found in environment or app config")
        
        self.api_url = "https://api.together.xyz/v1/completions"
        self.model = "togethercomputer/llama-2-70b-chat"  # Default model
    
    def generate_completion(self, prompt, max_tokens=512, temperature=0.7):
        """
        Generate a completion using Together AI API
        """
        if not self.api_key:
            raise ValueError("Together AI API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "top_k": 50
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("text", "")
        except Exception as e:
            logging.error(f"Error calling Together AI API: {str(e)}")
            raise
    
    def generate_rag_response(self, query, context_docs):
        """
        Generate a RAG response using retrieved documents as context
        """
        # Format context from retrieved documents
        context = "\n\n".join([
            f"Document {i+1} (Title: {doc['title']}):\n{doc['content']}"
            for i, doc in enumerate(context_docs)
        ])
        
        # Create the prompt
        prompt = f"""
You are an AI assistant that provides helpful, accurate, and concise responses based on the provided context.

CONTEXT:
{context}

USER QUERY:
{query}

Based only on the context provided above, answer the user's query. If the context doesn't contain relevant information to answer the query, state that you don't have enough information rather than making up an answer.

RESPONSE:
"""
        
        # Stream the response
        socketio.emit('generation_started', {'query': query})
        
        try:
            response = self.generate_completion(prompt, max_tokens=1024, temperature=0.7)
            
            # Emit the completed response
            socketio.emit('generation_completed', {
                'query': query,
                'response': response
            })
            
            return response
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error generating RAG response: {error_msg}")
            socketio.emit('generation_error', {'error': error_msg})
            return f"Error generating response: {error_msg}"

class LangGraphService:
    def __init__(self):
        self.together_ai = TogetherAIService()
        self.tools = [QueryDocumentsTool()]
    
    def setup_agent(self):
        """
        Set up a LangGraph agent with Together AI
        """
        # Define custom Together AI chat model
        class TogetherAIChatModel:
            def __init__(self, service):
                self.service = service
            
            def invoke(self, messages):
                # Convert messages to a prompt
                prompt = ""
                for message in messages:
                    if isinstance(message, HumanMessage):
                        prompt += f"Human: {message.content}\n"
                    elif isinstance(message, AIMessage):
                        prompt += f"AI: {message.content}\n"
                    else:
                        prompt += f"{message.type}: {message.content}\n"
                
                prompt += "AI: "
                
                # Generate response
                response = self.service.generate_completion(prompt)
                return AIMessage(content=response)
        
        llm = TogetherAIChatModel(self.together_ai)
        
        # Set up the agent
        functions = [format_tool_to_openai_function(t) for t in self.tools]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI assistant that helps users find information in documents. Use the tools available to find relevant information before answering."),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        agent = {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_function_messages(x["intermediate_steps"])
        } | prompt | llm | OpenAIFunctionsAgentOutputParser()
        
        executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
        return executor
    
    def process_query(self, query):
        """
        Process a query using the LangGraph agent
        """
        socketio.emit('agent_thinking', {'query': query})
        
        try:
            agent = self.setup_agent()
            result = agent.invoke({"input": query})
            return result["output"]
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error in LangGraph agent: {error_msg}")
            return f"Error processing query: {error_msg}"
