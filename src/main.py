import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()


# Windows asyncio workaround
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from src.mcp_client import MCPConnectionManager
from src.multi_agent import create_hr_graph
from langchain_core.messages import HumanMessage

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def main():
    print("🚀 İK Asistanına Hoş Geldiniz! (9 Multi-Agent Sistemi Başlatılıyor...)")
    
    # MCP bağlantısının kurulması
    try:
        await MCPConnectionManager.get_tools()
    except Exception as e:
        print("MCP Başlatılamadı! Lütfen sunucu ayarlarınızı (mcp_config.json) kontrol edin:", e)
        return
        
    # LangGraph Ajan Ağının Oluşturulması
    graph_builder = create_hr_graph()

    # Varsayılan Girdi
    github_owner = "Ahmetgrkm"
    repo_name = "automationexercise-ui-test-framework"
    job_desc = "3 yıl deneyimli Test Otomasyonu (Selenium, Java) Uzmanı, Clean Code bilen aday arıyoruz."
    
    print(f"\\n--- [Aday: {github_owner} | Repo: {repo_name} | Analiz Başlıyor] ---")
    
    import uuid
    
    # Thread ID (Her analiz için benzersiz - Böylece LLM eski token'ları hatırlayıp faturayı şişirmez)
    unique_run_id = uuid.uuid4().hex[:8]
    config = {"configurable": {"thread_id": f"hr_session_{github_owner}_{repo_name}_{unique_run_id}"}}
    initial_state = {
        "github_owner": github_owner,
        "repo_name": repo_name,
        "job_description": job_desc,
        "total_tokens": 0,
        "total_tool_calls": 0,
        "messages": [HumanMessage(content=f"{github_owner} kullanıcısının {repo_name} reposunu analiz edin.")]
    }

    try:
        # AIO Sqlite checkpointer'ı bağlan
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
            app = graph_builder.compile(checkpointer=checkpointer)
            
            # 9 ajanlık grafiği başlat ve terminalde takip et
            final_state = await app.ainvoke(initial_state, config)
            print("\\n✅ >>> NİHAİ İK ADAY RAPORU <<< ✅\\n")
            print(final_state["final_hr_report"])
            
            print("\\n📊 --- PERFORMANS VE MALİYET METRİKLERİ ---")
            print(f"Toplam API İsteği (Tool Calls): {final_state.get('total_tool_calls', 0)}")
            print(f"Toplam Token Kullanımı: {final_state.get('total_tokens', 0)}\\n")
            
    except Exception as e:
        print("\\n❌ Analiz sırasında bir hata oluştu:", e)
    finally:
        await MCPConnectionManager.close()
        print("\\nSistem güvenle kapatıldı.")

if __name__ == "__main__":
    asyncio.run(main())
