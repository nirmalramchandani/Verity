import os
import asyncio
from typing import Dict, Any
from signal_engine.models import SignalSchema
from signal_engine.logger import get_structured_logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Using Tavily for searching real-time news
from tavily import TavilyClient

logger = get_structured_logger("signal_engine.enrichment")

class ContextualistAgent:
    """
    Agentic RAG pipeline to enrich numerical signals with fundamental news context using OpenRouter & Tavily.
    """
    def __init__(self):
        # The user has OPENROUTER_API_KEY
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.search_api_key = os.getenv("TAVILY_API_KEY")
        
        if self.api_key:
            # Connect to OpenRouter API
            self.llm = ChatOpenAI(
                model="google/gemma-2-9b-it:free", # Using a common free tier model on OpenRouter
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.2
            )
        else:
            self.llm = None
            
        if self.search_api_key:
            self.search_client = TavilyClient(api_key=self.search_api_key)
        else:
            self.search_client = None

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Cynical Institutional Researcher. Analyze the stock signal, recent news, and Whale behavior. Look for contradictions between the news and price action. Output strictly a 3-bullet 'Analyst Verdict' explaining why this Whale is buying/selling now. Keep it concise."),
            ("user", "Stock: {symbol}\nWhale Sector Bias: {whale_sector}\nSignal Details: {signal_details}\nRecent News:\n{news}")
        ])
        
        if self.llm:
            self.chain = self.prompt | self.llm | StrOutputParser()

    async def enrich_signal(self, signal: SignalSchema, investor_dna: Dict[str, Any]) -> SignalSchema:
        """
        Triggers if score >= 70 (HIGH/CRITICAL). Fetches news and synthesizes an Analyst Verdict.
        """
        if signal.strength_score < 70:
            return signal

        logger.info(f"Triggering Contextualist Agent for {signal.symbol} (Score: {signal.strength_score})")

        symbol = signal.symbol
        whale_sector = investor_dna.get("favorite_sector", "Unknown")
        signal_details = signal.expert_summary
        
        news_context = "No recent news found."
        
        if self.search_client:
            try:
                # Run the synchronous Tavily client in an executor
                loop = asyncio.get_event_loop()
                search_res = await loop.run_in_executor(
                    None, 
                    lambda: self.search_client.search(f"{symbol} NSE India stock news", search_depth="basic", max_results=3)
                )
                if search_res and "results" in search_res:
                    news_context = "\n".join([r.get("content", "") for r in search_res["results"]])
            except Exception as e:
                logger.error(f"Tavily search failed: {e}")
                
        if self.llm:
            try:
                verdict = await self.chain.ainvoke({
                    "symbol": symbol,
                    "whale_sector": whale_sector,
                    "signal_details": signal_details,
                    "news": news_context
                })
                # Attach to signal
                signal.expert_summary = signal.expert_summary + "\n\nAnalyst Verdict:\n" + verdict
                logger.info(f"Successfully enriched signal for {symbol}")
            except Exception as e:
                logger.error(f"LLM enrichment failed: {e}")
        else:
            logger.warning("No OpenRouter API Key found. Skipping AI enrichment.")
            
        return signal
