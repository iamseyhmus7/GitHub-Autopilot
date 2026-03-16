from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from src.agents.llm_utils import get_agent_llm, run_agent_loop
import sqlite3
import json

async def history_analyzer_node(state: HRGraphState):
    """Ajan 9: Bellek Muhafızı (History Analyzer)"""
    print("🤖 [Ajan 9] History Analyzer (Bellek Muhafızı) devrede...")
    
    # 1. Sqlite'dan bu aday (github_owner) için eski raporları ara
    # Not: SqliteSaver checkpointer zaten veriyi tutuyor ama biz state bazlı sentez istiyoruz.
    # Şimdilik basitleştirilmiş bir mock/placeholder mantığı kuruyoruz, 
    # çünkü gerçek çapraz-thread okuma LangGraph'ta biraz karmaşıktır.
    
    historical_context = "Daha önce bu aday için bir analiz kaydı bulunamadı (İlk analiz)."
    
    # Gerçek uygulamada burası db.execute("SELECT ... FROM checkpoints WHERE ...") olurdu.
    
    llm, _ = await get_agent_llm(allowed_tools=[])
    
    sys_prompt = f"""
Sen 'History Analyzer' ajanısın. Görevin, adayın şu anki teknik verilerini, sistemdeki eski verileriyle karşılaştırmaktır.
Eğer eski veri yoksa, bunun ilk analiz olduğunu belirt.
Eğer varsa; 'Gelişim', 'Teknoloji Değişikliği' ve 'Süreklilik' konularında rapor ver.

Mevcut Aday: {state['github_owner']}
Geçmiş Veri: {historical_context}
"""
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Lütfen mevcut durumu geçmişle kıyasla.")
    ]
    
    res, tokens, tool_calls = await run_agent_loop(llm, [], messages)
    
    return {
        "historical_analysis": res,
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "History Analyzer"
    }
