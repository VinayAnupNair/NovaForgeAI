from typing import List

from pydantic import BaseModel, Field

from app.domain.models import UpgradeType


class NewGameRequest(BaseModel):
    company_name: str = "NovaForge AI"


class UpgradeAction(BaseModel):
    model_index: int = Field(ge=0)
    upgrade_type: UpgradeType


class ApplyUpgradesRequest(BaseModel):
    upgrades: List[UpgradeAction]


class FundingDecisionRequest(BaseModel):
    accept: bool
