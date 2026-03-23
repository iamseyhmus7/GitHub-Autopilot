import time
from src.state import HRGraphState


def _ts() -> str:
    t = time.localtime()
    ms = int((time.time() % 1) * 1000)
    return f"[{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}]"


async def history_analyzer_node(state: HRGraphState):
    """Ajan 9: Bellek Muhafızı (History Analyzer)

    Gerçek çapraz-thread SQLite okuma LangGraph'ta karmaşıktır.
    Şu an için ilk analiz bilgisi sabit döndürülür, LLM çağrısı yapılmaz.
    Bu sayede ajan <1 saniyede tamamlanır ve HR Synthesizer'ı bekletmez.
    """
    print(f"{_ts()} 🤖 [History Analyzer] ═══ BAŞLADI ═══", flush=True)
    t0 = time.time()

    # Sqlite'dan bu aday için eski raporları ara
    # Gerçek uygulamada: db.execute("SELECT ... FROM checkpoints WHERE thread_id LIKE ?")
    historical_analysis = (
        f"Bu analize ait önceki kayıt bulunamadı — "
        f"{state['github_owner']}/{state['repo_name']} için ilk analiz."
    )

    elapsed = time.time() - t0
    print(f"{_ts()} [History Analyzer] ✅ BİTTİ ({elapsed:.2f}s) — LLM çağrısı yapılmadı (sabit veri)", flush=True)

    return {
        "historical_analysis": historical_analysis,
        "total_tokens": 0,
        "total_tool_calls": 0,
        "current_agent": "History Analyzer",
    }
