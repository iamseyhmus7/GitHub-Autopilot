from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import HRGraphState

async def run_qa_agent(state: HRGraphState, user_query: str):
    """
    Kullanıcının Teknik DNA Raporu hakkındaki sorularını yanıtlayan bağımsız ajan.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2 # Biraz daha yaratıcı cevaplar için hafif artırdık
    )
    
    # Rapor verilerini bağlam olarak kullanıyoruz
    context = f"""
Sistemin oluşturduğu Teknik DNA Raporu:
{state.get('final_hr_report', 'Rapor henüz hazır değil.')}

Aday Hakkında Diğer Tespitler:
- Mimari: {state.get('architecture_analysis')}
- Kod Kalitesi: {state.get('code_quality_report')}
- Güvenlik: {state.get('security_report')}
- DevOps: {state.get('ci_cd_testing_status')}
"""

    sys_prompt = f"""
Sen 'Technical DNA Assistant'sın. Görevin, yukarıda sunulan teknik analiz raporuna dayanarak kullanıcının (İK Uzmanı veya Teknik Müdür) aday hakkındaki sorularını yanıtlamaktır.
Cevapların profesyonel, objektif ve doğrudan verilere dayalı olmalıdır. 
Eğer verilerde olmayan bir şey sorulursa, bu konuda bilgimiz olmadığını dürüstçe belirt.
"""

    messages = [
        SystemMessage(content=sys_prompt),
        SystemMessage(content=f"Context Verisi: {context}"),
        HumanMessage(content=user_query)
    ]
    
    response = await llm.ainvoke(messages)
    return response.content
