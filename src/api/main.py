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
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI
from src.api.schemas import AnalysisRequest, ChatRequest
from langchain_core.messages import HumanMessage
from src.agents.qa_agent import run_qa_agent
from fastapi.responses import FileResponse
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlarken MCP Sunucusu ayağa kalkar
    try:
        await MCPConnectionManager.get_tools()
        yield
    finally:
        # Uygulama kapanırken MCP bağlantısı koparılır
        await MCPConnectionManager.close()

app = FastAPI(title="GitHub Autopilot API", version="1.0.0", lifespan=lifespan)

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
        try:
            github_owner = request.github_owner
            repo_name = request.repo_name
            job_desc = request.job_description
            
            # --- AGENT 0: Akıllı Profil Analizi ---
            # Eğer repo_name girilmediyse, adayın tüm profili taranıp en iyi projeler seçilir
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
                    
                    yield f"data: {json.dumps({'type': 'system', 'message': f'🧠 Repolar başarıyla çekildi. İş ilanı ile eşleştirilerek Profil Analizi yapılıyor...'}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)
                    
                    # LLM'e Sor
                    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
                    prompt = f"""
Sen uzman bir İK Yöneticisisin. Aşağıda bir GitHub kullanıcısının (Aday) repoları (JSON) ve iş ilanı verilmiştir.
Amacın, adayın yeteneklerini EN İYİ yansıtacak ve iş ilanıyla EN ÇOK örtüşen 3-5 adet projeyi seçmektir.

Kriterler:
1. İlandaki dillerle/teknolojilerle en çok eşleşen projeleri bul. 
2. 'fork: true' olanları KESİNLİKLE SEÇME. Adayın kendi üretimi olmalı.
3. Yıldız sayısı ve güncellik önemlidir.

Cevabını SADECE aşağıdaki JSON formatında ver:
{{
  "primary_repo": "en_onemli_tek_repo_adi",
  "relevant_repos": ["repo1", "repo2", "repo3"]
}}

İş İlanı ({job_desc[:100]}...):
{job_desc}

Adayın Repoları:
{repos_str[:25000]}
"""
                    profil_res = llm.invoke(prompt).content.strip()
                    # JSON temizliği
                    if "```json" in profil_res:
                        profil_res = profil_res.split("```json")[1].split("```")[0].strip()
                    elif "```" in profil_res:
                        profil_res = profil_res.split("```")[1].split("```")[0].strip()
                    
                    selection = json.loads(profil_res)
                    repo_name = selection["primary_repo"]
                    relevant_repos = selection["relevant_repos"]
                    
                    yield f"data: {json.dumps({'type': 'system', 'message': f'🏆 Çoklu Proje Analizi Başlatıldı: {', '.join(relevant_repos)}'}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Profil analizi (Agent 0) başarısız oldu: {str(e)}'}, ensure_ascii=False)}\n\n"
                    return
            else:
                relevant_repos = [repo_name]
            # -------------------------------------
            
            # LLM Memory Bloat önlemek için benzersiz bir UUID ekliyoruz
            unique_run_id = uuid.uuid4().hex[:8]
            config = {"configurable": {"thread_id": f"hr_session_{github_owner}_{repo_name}_{unique_run_id}"}}
            
            initial_state = {
                "github_owner": github_owner,
                "repo_name": repo_name,
                "relevant_repos": relevant_repos,
                "job_description": job_desc,
                "total_tokens": 0,
                "total_tool_calls": 0,
                "current_agent": "",
                "errors": [],
                "messages": [HumanMessage(content=f"{github_owner} kullanıcısının {', '.join(relevant_repos)} repolarını {job_desc} ilanına göre analiz edin.")]
            }
            
            # Checkpointer bağlantısı açılır
            async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
                langgraph_app = graph_builder.compile(checkpointer=checkpointer)
                
                thread_id = config["configurable"]["thread_id"]
                yield f"data: {json.dumps({'type': 'system', 'message': '🕹️ Analiz Grafiği Derlendi. Akış Başlatılıyor...', 'thread_id': thread_id}, ensure_ascii=False)}\n\n"

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
                            yield f"data: {json.dumps({'type': 'system', 'message': '🏁 HR yöneticisi raporu tamamladı, veriler gönderiliyor...'}, ensure_ascii=False)}\n\n"
                            data["type"] = "final_report"
                            data["report"] = node_state.get("final_hr_report", "")
                        
                        # SSE (Server-Sent Events) spesifikasyonuna göre datayı string olarak gönder
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.1)
                    
                # Tüm sistem bitti mesajı
                yield f"data: {json.dumps({'type': 'system', 'message': '✅ Analiz başarıyla tamamlandı. Rapor aşağıdadır.'}, ensure_ascii=False)}\n\n"
                    
        except Exception as e:
            # Kritik bir hata olursa frontend'e hata akışı (stream) sağla
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    # Header değerlerini SSE formatı için özel dönüyoruz
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat")
async def chat_with_report(req: ChatRequest):
    """
    Rapor hakkında soru-cevap yapılmasını sağlayan endpoint.
    """
    DB_PATH = "checkpoints.sqlite"
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        config = {"configurable": {"thread_id": req.thread_id}}
        checkpoint = await checkpointer.aget(config)
        if not checkpoint:
            return {"answer": "Oturum bulunamadı veya analiz tamamlanmadı. Lütfen analizin bitmesini bekleyin."}
        
        # LangGraph versiyonuna göre 'values' veya 'channel_values' olabilir
        state = checkpoint.get("values") or checkpoint.get("channel_values")
        if not state:
            return {"answer": "Oturum verisine ulaşılamadı. Lütfen analizi tekrar çalıştırın."}
            
        answer = await run_qa_agent(state, req.query)
        
        return {
            "answer": answer,
            "thread_id": req.thread_id
        }

@app.get("/api/report/pdf/{thread_id}")
async def export_pdf(thread_id: str):
    """
    Analiz sonucunu PDF olarak dışa aktarır.
    """
    DB_PATH = "checkpoints.sqlite"
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = await checkpointer.aget(config)
        if not checkpoint:
            return {"error": "Rapor bulunamadı."}
        
        # LangGraph versiyonuna göre 'values' veya 'channel_values' olabilir
        state = checkpoint.get("values") or checkpoint.get("channel_values")
        if not state:
            print(f"[PDF DEBUG] Checkpoint var ama values/channel_values yok! Keys: {list(checkpoint.keys())}", flush=True)
            return {"error": "Rapor bulunamadı."}
            
        report_content = state.get("final_hr_report", "Rapor verisi bulunamadı.")
        
        # PDF Oluşturma (Geçici dosya)
        from fpdf import FPDF
        
        class PDF(FPDF):
            def header(self):
                self.set_font('helvetica', 'B', 15)
                self.cell(0, 10, 'Technical DNA Analysis Report', border=True, ln=True, align='C')
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font('helvetica', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        
        # FPDF helvetica fontu sadace Latin-1 destekler (Türkçe ve emojiler hata verir).
        # Bu yüzden metni basitleştiriyoruz:
        clean_text = report_content.replace("#", "").replace("*", "").replace("`", "")
        
        # 1. Türkçe karakterleri İngilizce'ye çevir
        tr_to_en = {
            'ş': 's', 'Ş': 'S', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I',
            'ç': 'c', 'Ç': 'C', 'ö': 'o', 'Ö': 'O', 'ü': 'u', 'Ü': 'U'
        }
        for tr, en in tr_to_en.items():
            clean_text = clean_text.replace(tr, en)
            
        # 2. Emojileri temizle (regex)
        import re
        clean_text = re.sub(r'[^\x00-\x7F]+', '', clean_text)  # Sadece ASCII'yi tut
        
        pdf.multi_cell(0, 10, clean_text)
        
        file_path = f"report_{thread_id}.pdf"
        pdf.output(file_path)
        
        return FileResponse(file_path, filename=f"DNA_Report_{thread_id}.pdf", background=asyncio.create_task(asyncio.sleep(10)).add_done_callback(lambda _: os.remove(file_path) if os.path.exists(file_path) else None))
