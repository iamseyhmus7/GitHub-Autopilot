from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import uuid
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client import MCPConnectionManager
from src.multi_agent import create_hr_graph
from src.api.schemas import AnalysisRequest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlarken MCP Sunucusu ayağa kalkar
    try:
        await MCPConnectionManager.get_tools()
        yield
    finally:
        # Uygulama kapanırken MCP bağlantısı koparılır
        await MCPConnectionManager.close()

app = FastAPI(title="AI HR Assistant API", version="1.0.0", lifespan=lifespan)

# Frontend'lerin (Next.js vb.) istek atabilmesi için CORS izinleri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/analyze-stream")
async def analyze_stream(request: AnalysisRequest):
    """
    Girilen adayın GitHub reposunu 9-Ajanlı sistem ile asenkron olarak inceler
    ve Server-Sent Events (SSE) kullanılarak frontend'e canlı (streaming) akış sağlar.
    """
    graph_builder = create_hr_graph()
    
    async def event_generator():
        github_owner = request.github_owner
        repo_name = request.repo_name
        job_desc = request.job_description
        
        # --- AGENT 0: Akıllı Profil Analizi ---
        # Eğer repo_name girilmediyse, adayın tüm profili taranıp en iyi proje seçilir
        if not repo_name:
            yield f"data: {json.dumps({'type': 'system', 'message': f'📦 {github_owner} adlı adayın profilindeki tüm GitHub repoları taranıyor...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            try:
                tools = await MCPConnectionManager.get_tools()
                list_repos_tool = next((t for t in tools if t.name == "list_user_repos"), None)
                if not list_repos_tool:
                    raise ValueError("list_user_repos MCP aracı bulunamadı!")
                
                # Repoları çek (100 repo limiti)
                repos_str = await list_repos_tool.ainvoke({"username": github_owner, "per_page": 100})
                
                yield f"data: {json.dumps({'type': 'system', 'message': f'🧠 Repolar başarıyla çekildi. İş ilanı ile eşleştirilerek Şampiyon Proje aranıyor...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                
                # LLM'e Sor
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
                prompt = f"""
Sen uzman bir İK Yöneticisisin. Aşağıda bir GitHub kullanıcısının (Aday) repoları (JSON formatında) ve başvurduğu iş ilanının detayı verilmiştir.
Amacın, bu adayın yeteneklerini en iyi şekilde yansıtacak, iş ilanına EN UYGUN olan tek 1 master projeyi (repository) seçmektir.
Kriterler:
1. İlanda istenen programlama dillerine (language) dikkat et.
2. Çatal (fork: true) olan repoları KESİNLİKLE SEÇME. Adayın kendi kodu olmalı.
3. Yıldız sayısı (stargazers_count) yüksek ve güncel (updated_at) olanlara öncelik ver.

İş İlanı ({job_desc[:100]}...):
{job_desc}

Adayın Repoları:
{repos_str[:25000]}

SADECE VE SADECE seçtiğin reponun TAM ADINI (name alanını) yaz. Başka hiçbir açıklama, markdown veya noktalama işareti kullanma.
Örnek geçerli cevap: automationexercise-ui-test-framework
"""
                repo_name = llm.invoke(prompt).content.strip()
                
                # LLM validasyonu
                if not repo_name or " " in repo_name or repo_name.startswith("```"):
                   raise ValueError(f"LLM geçerli bir repo adı dönemedi: {repo_name}")
                   
                yield f"data: {json.dumps({'type': 'system', 'message': f'🏆 Şampiyon Repo Seçildi: {repo_name}. Derin analize başlanıyor...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Profil analizi (Agent 0) başarısız oldu: {str(e)}'}, ensure_ascii=False)}\n\n"
                return
        # -------------------------------------
        
        # LLM Memory Bloat önlemek için benzersiz bir UUID ekliyoruz
        unique_run_id = uuid.uuid4().hex[:8]
        config = {"configurable": {"thread_id": f"hr_session_{github_owner}_{repo_name}_{unique_run_id}"}}
        
        initial_state = {
            "github_owner": github_owner,
            "repo_name": repo_name,
            "job_description": job_desc,
            "total_tokens": 0,
            "total_tool_calls": 0,
            "messages": [HumanMessage(content=f"{github_owner} kullanıcısının {repo_name} reposunu {job_desc} ilanına göre analiz edin.")]
        }
        
        try:
            # Checkpointer bağlantısı açılır
            async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
                langgraph_app = graph_builder.compile(checkpointer=checkpointer)
                
                # astream() ile her bir ajan (node) işini bitirdikçe canlı veri fırlatılır
                async for chunk in langgraph_app.astream(initial_state, config):
                    for node_name, node_state in chunk.items():
                        
                        agent_name = node_state.get("current_agent", node_name)
                        
                        data = {
                            "type": "agent_update",
                            "node": node_name,
                            "agent": agent_name,
                            "status": "completed",
                            "tokens_so_far": node_state.get("total_tokens", 0),
                            "tool_calls_so_far": node_state.get("total_tool_calls", 0)
                        }
                        
                        # Eğer çalışan ajan sonuncu ajan (HR) ise raporu da bas
                        if node_name == "hr_synthesizer":
                            data["type"] = "final_report"
                            data["final_report"] = node_state.get("final_hr_report", "")
                            
                        # SSE (Server-Sent Events) spesifikasyonuna göre datayı string olarak gönder
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.1) # İstemci tarafında yığılmayı önlemek için minik delay
                        
                # Tüm sistem bitti mesajı
                yield f"data: {json.dumps({'type': 'system', 'status': 'done'})}\n\n"
                
        except Exception as e:
            # Kritik bir hata olursa frontend'e hata akışı (stream) sağla
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    # Header değerlerini SSE formatı için özel dönüyoruz
    return StreamingResponse(event_generator(), media_type="text/event-stream")
