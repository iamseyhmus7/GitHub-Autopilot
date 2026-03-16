from typing import Optional
from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    github_owner: str
    repo_name: Optional[str] = None
    job_description: str = "Senior Full Stack Developer"

class ChatRequest(BaseModel):
    thread_id: str
    query: str
