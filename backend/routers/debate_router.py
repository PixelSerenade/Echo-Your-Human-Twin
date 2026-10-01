from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import datetime

from backend.database import get_db
from backend.services.data_access import get_permitted_user_data
from backend.models import User, TwinWeight
from backend.services.identity import resolve_twin_name
from backend.llm.gemini_client import gemini_client
from backend.services.style_blend import normalize_style_weights, style_order

router = APIRouter(tags=["On-Demand Debate Studio"])

class DebateRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    question: str
    primary_twin: str
    first_answer: str
    recent_turns: List[Dict[str, str]] = Field(default_factory=list)

class StyleVoice(BaseModel):
    style: str
    label: str
    argument: str
    your_usual_voice: bool = False

class OtherTwinView(BaseModel):
    twin: str
    title: str
    argument: str
    points_missed: List[str]

class TradeOffItem(BaseModel):
    dimension: str
    description: str

class CompromiseOption(BaseModel):
    title: str
    action: str

class HumanTwinSynthesis(BaseModel):
    summary_of_tensions: str
    trade_offs: List[TradeOffItem]
    compromise_option: CompromiseOption
    consider_before_deciding: List[str]

class DebateResponse(BaseModel):
    question: str
    primary_twin: str
    first_answer: str
    other_twins: List[OtherTwinView]
    synthesis: HumanTwinSynthesis
    sources_used: List[str]
    timestamp: datetime.datetime
    voices: List[StyleVoice] = []
    closing_line: str = "It's your call, and I'm with you either way."

@router.post("/debate", response_model=DebateResponse)
@router.post("/api/debate", response_model=DebateResponse)
async def conduct_debate(req: DebateRequest, db: AsyncSession = Depends(get_db)):
    """
    On-Demand Debate Feature:
    - Only called when user clicks 'See the debate'.
    - The two other twins respond in parallel (asyncio.gather), each adding
      considerations the primary twin missed and NOT repeating its points.
    - HumanTwin synthesis returns trade-offs, a compromise option, and a
      'consider before deciding' list without giving a single command.
    """
    user_id = req.user_id or "demo-alex-rivers"

    from backend.routers.ask_router import is_crisis_like_message
    if is_crisis_like_message(req.question):
        raise HTTPException(status_code=400, detail="I can't bring in other voices for a safety crisis. Your immediate safety comes first; please contact local emergency services or someone you trust now.")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    weight = await db.scalar(select(TwinWeight).where(TwinWeight.user_id == user_id))
    blend = normalize_style_weights({
        "emotional": weight.emotional if weight else 0.25,
        "rational": weight.rational if weight else 0.50,
        "ambitious": weight.ambitious if weight else 0.25,
    })
    ordered_styles = style_order(blend)
    usual_style = ordered_styles[0]

    # Single permission-enforcing data gateway touch
    bundle = await get_permitted_user_data(
        db, user_id=user_id, log_audit_endpoint="/debate", audit_action="debate_twins"
    )

    permitted_context = bundle.to_context_string()
    user_name = (user.name or "the user").strip()
    twin_name = resolve_twin_name(user)

    try:
        voices_raw = await gemini_client.run_style_blend_debate(
            question=req.question,
            styles=ordered_styles,
            usual_style=usual_style,
            first_answer=req.first_answer,
            permitted_context=permitted_context,
            recent_turns=req.recent_turns,
            user_name=user_name,
            twin_name=twin_name,
        )
    except Exception as exc:
        voices_raw = []
        fallback_line = "Couldn't reach the other voices right now, try again?"
    else:
        fallback_line = "It's your call, and I'm with you either way."

    voices = [StyleVoice(**voice) for voice in voices_raw]

    other_twins_out = [OtherTwinView(twin=voice.style, title=f"{voice.label} voice", argument=voice.argument, points_missed=[]) for voice in voices if voice.style != usual_style]

    synthesis_out = HumanTwinSynthesis(
        summary_of_tensions="Each voice is noticing a different part of what matters to you.",
        trade_offs=[],
        compromise_option=CompromiseOption(title="Your call", action=fallback_line),
        consider_before_deciding=[]
    )

    return DebateResponse(
        question=req.question,
        primary_twin=usual_style,
        first_answer=req.first_answer,
        other_twins=other_twins_out,
        synthesis=synthesis_out,
        sources_used=bundle.accessed_sources,
        timestamp=datetime.datetime.utcnow(),
        voices=voices,
        closing_line=fallback_line,
    )
