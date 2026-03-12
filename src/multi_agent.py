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
    
    graph_builder.add_node("hr_synthesizer", hr_synthesizer_node)

    # 3. Akışı (Edge/Bağlantıları) Çiz - Rate Limit yememek için sıralı yapıyoruz
    # Faz 1: Keşif
    graph_builder.add_edge(START, "repo_explorer")
    graph_builder.add_edge("repo_explorer", "dependency_analyst")
    
    # Faz 2: Mühendislik
    graph_builder.add_edge("dependency_analyst", "architecture_reviewer")
    graph_builder.add_edge("architecture_reviewer", "code_quality")
    graph_builder.add_edge("code_quality", "security")
    
    # Faz 3: Kayıt & Süreç
    graph_builder.add_edge("security", "git_historian")
    graph_builder.add_edge("git_historian", "devops")
    graph_builder.add_edge("devops", "pr_manager")
    
    # Faz 4: Sentez & Karar
    graph_builder.add_edge("pr_manager", "hr_synthesizer")
    graph_builder.add_edge("hr_synthesizer", END)

    # 4. Kalıcı Hafıza (SqliteSaver) ile Derle
    # Asenkron çalışacağı için checkpointer derlemesi ana (main) döngüye bırakıldı.
    return graph_builder
