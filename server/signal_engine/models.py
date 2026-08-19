from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class StrategyResult(BaseModel):
    strategy_name: str
    score: float = Field(..., ge=0, le=100, description="Strategy score from 0 to 100")
    weight: float = Field(..., description="Weight of the strategy in the final consensus")
    reasoning_metadata: str = Field(..., description="Explanation for the generated score")
    insufficient_data: bool = Field(default=False, description="Flag indicating if the strategy failed due to lack of historical data")

class SignalSchema(BaseModel):
    signal_id: UUID = Field(default_factory=uuid4)
    symbol: str
    signal_type: SignalType
    strength_score: float = Field(..., ge=0, le=100)
    confidence_label: str = Field(..., description="CRITICAL, HIGH, or SPECULATIVE")
    consensus_level: int = Field(..., description="1 (Weak), 2 (Medium), 3 (High)")
    expert_summary: str = Field(..., description="Human-readable aggregation of the reasoning")
    strategy_breakdown: List[StrategyResult] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deal_date: str = Field(default="")

class WeightingConfig(BaseModel):
    InstitutionalHerdingStrategy: float = 0.40
    WhaleConvictionStrategy: float = 0.40
    RelativeVolumeIntensityStrategy: float = 0.20
    
    def validate_weights(self):
        total = self.InstitutionalHerdingStrategy + self.WhaleConvictionStrategy + self.RelativeVolumeIntensityStrategy
        if not abs(total - 1.0) < 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

class ExitMetadata(BaseModel):
    target_price: float
    stop_loss: float
    estimated_exit_date: Optional[datetime] = None

class PortfolioHolding(BaseModel):
    holding_id: UUID = Field(default_factory=uuid4)
    symbol: str
    investor_name: str
    entry_price: float
    entry_date: datetime
    whale_stats_at_entry: dict
    exit_metadata: ExitMetadata
    status: str = Field(default="ACTIVE", description="ACTIVE, TIME_EXHAUSTED, TARGET_HIT, STOPPED_OUT, MIRROR_EXIT")
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
