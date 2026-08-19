import asyncio
from dotenv import load_dotenv
load_dotenv()
from signal_engine.alerting import NotificationService
from signal_engine.models import SignalSchema

async def send_test():
    svc = NotificationService()
    test_signal = SignalSchema(
        symbol="HDFCBANK",
        strength_score=92.5,
        signal_type="BUY",
        confidence_label="CRITICAL BUY",
        consensus_level=100,
        expert_summary="""Triggered by 4 distinct Whales entering in 14 days (LIC, Vanguard). Whale averaging up. Current price 2850.00 is >5% higher than WAP 2600.00. Deal value is > 10% of 30-day ADV.
Analyst Verdict:
• Whale is aggressively entering HDFCBANK, aligning with their historical bias.
• News of tariff hikes contradicts recent negative retail sentiment.
• Volume anomaly indicates heavy institutional accumulation."""
    )
    await svc.send_alert(test_signal)
    print("Sent test rich email!")

if __name__ == "__main__":
    asyncio.run(send_test())
