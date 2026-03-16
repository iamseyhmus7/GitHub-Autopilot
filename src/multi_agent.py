from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

from src.state import HRGraphState
from src.agents.discovery import repo_explorer_node, dependency_analyst_node
from src.agents.engineering import (
    architecture_reviewer_node, 
    code_quality_inspector_node, 
    security_agent_node
)
from src.agents.process import (
    git_historian_node, 
    devops_evaluator_node, 
    pr_manager_node
)
from src.agents.history import history_analyzer_node
from src.agents.synthesis import hr_synthesizer_node

def create_hr_graph(memory_db_path="checkpoints.sqlite"):
    """9-Agent郎Graph akışını inşa eder ve geri döner."""
    
    # 1. Grafiği State üzerinden başlat
    graph_builder = StateGraph(HRGraphState)
    
    # 2. Düğümleri (Ajanları) Ekle
    graph_builder.add_node("repo_explorer", repo_explorer_node)
    graph_builder.add_node("dependency_analyst", dependency_analyst_node)
    
    graph_builder.add_node("architecture_reviewer", architecture_reviewer_node)
    graph_builder.add_node("code_quality", code_quality_inspector_node)
    graph_builder.add_node("security", security_agent_node)
    
    graph_builder.add_node("git_historian", git_historian_node)
    graph_builder.add_node("devops", devops_evaluator_node)
    graph_builder.add_node("pr_manager", pr_manager_node)
    graph_builder.add_node("history_analyzer", history_analyzer_node)
    
    graph_builder.add_node("hr_synthesizer", hr_synthesizer_node)

    # 3. Akışı Gerçek Zamanda Paralelleştir (Turbo Mode)
    
    # Faz 1: Keşif (Sıralı - Temel veriler için)
    graph_builder.add_edge(START, "repo_explorer")
    graph_builder.add_edge("repo_explorer", "dependency_analyst")
    
    # Faz 2: Paralel Analiz (Fan-out)
    analysts = [
        "architecture_reviewer", 
        "code_quality", 
        "security", 
        "git_historian", 
        "devops", 
        "pr_manager",
        "history_analyzer"
    ]
    
    for analyst in analysts:
        graph_builder.add_edge("dependency_analyst", analyst)
        graph_builder.add_edge(analyst, "hr_synthesizer")
    
    # Faz 3: Sentez & Karar (Tüm paralel işler bitince çalışır)
    graph_builder.add_edge("hr_synthesizer", END)

    # 4. Kalıcı Hafıza (SqliteSaver) ile Derle
    # Asenkron çalışacağı için checkpointer derlemesi ana (main) döngüye bırakıldı.
    return graph_builder
