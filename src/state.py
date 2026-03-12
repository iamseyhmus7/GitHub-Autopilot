import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class HRGraphState(TypedDict):
    # Girdi Verileri (Başlangıçta verilecek)
    github_owner: str
    repo_name: str
    job_description: str # İK'nın aradığı kriterler
    
    # İletişim & Hafıza
    messages: Annotated[list[BaseMessage], operator.add]
    
    # Maliyet / Performans İzleme
    total_tokens: Annotated[int, operator.add]
    total_tool_calls: Annotated[int, operator.add]
    
    # 1. BÖLÜM: KEŞİF
    repo_overview: Optional[str]        # Repository Mapper'dan gelen özet
    tech_stack: Optional[str]           # Dependency Analyst'ten
    
    # 2. BÖLÜM: MÜHENDİSLİK
    architecture_analysis: Optional[str] # Architecture Reviewer'dan
    code_quality_report: Optional[str]  # Code Quality Inspector'dan
    security_report: Optional[str]      # Security Agent'tan
    
    # 3. BÖLÜM: EMEK VE SÜREÇ
    commit_history_analysis: Optional[str] # Git Historian'dan (Kopya/Gerçek emek)
    ci_cd_testing_status: Optional[str]    # DevOps & Testing Evaluator'dan
    teamwork_pr_analysis: Optional[str]    # Issue & PR Manager'dan
    
    # 4. BÖLÜM: SENTEZ
    final_hr_report: Optional[str]         # HR Synthesizer'dan çıkan Nihai Puan Kartı
    
    # Yönetimsel Durumlar
    current_agent: str # Hangi ajanın devrede olduğunu loglamak için
    errors: list[str]
