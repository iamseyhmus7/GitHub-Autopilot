from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from langchain_google_genai import ChatGoogleGenerativeAI

async def hr_synthesizer_node(state: HRGraphState):
    """Ajan 9: HR Synthesizer (Baş İK Yöneticisi)"""
    print("🧑‍💼 [Ajan 9] HR Synthesizer (Baş İK Yöneticisi) Karar Aşamasına Geçti...")
    
    # Bu ajanın araç kullanmasına gerek yok. Tüm veriler zaten State içinde!
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0, 
        max_tokens=4096
    )
    
    # Bütün uzmanlardan gelen devasa veriyi İK için süzüyoruz
    sys_prompt = f"""Sen 'HR Synthesizer' ajanısın (Baş İK Yöneticisi). 
Aşağıda 8 farklı teknik uzmandan gelen detaylı {state['github_owner']}/{state['repo_name']} Github Aday Analiz Raporları bulunuyor.
    
İş İlanı Gereksinimleri: {state['job_description']}

Teknik Ajanlardan Gelen Raporlar:
- Proje Özeti: {state.get('repo_overview')}
- Teknoloji Yığını: {state.get('tech_stack')}
- Mimari Analiz: {state.get('architecture_analysis')}
- Kod Kalitesi: {state.get('code_quality_report')}
- Güvenlik: {state.get('security_report')}
- Git Geçmişi & Emek: {state.get('commit_history_analysis')}
- Test & CI/CD: {state.get('ci_cd_testing_status')}
- Ekip/PR Yönetimi: {state.get('teamwork_pr_analysis')}

Görevin: Bu devasa ve teknik verileri süz, harmanla ve kesinlikle TEKNİK OLMAYAN BİR İK UZMANININ anlayacağı sade, net, profesyonel BİR 'Nihai Aday Skor Kartı' çıkar.

ŞU FORMATTA OLMALI:
1. 🌟 Aday Özeti: (1-2 Cümle)
2. 🎯 İşe Uygunluk Skoru: (100 üzerinden, İş İlanı Kriterlerine göre)
3. ✅ Artılar (Green Flags): 
4. ⚠️ Eksiler/Uyarılar (Red Flags): (Örn: kopya şüphesi varsa kesin uyar)
5. ⚖️ Nihai Karar: (Mülakata Çağrılmalı mı, Neden?)
6. 🗣️ Mülakatta Sorulacak 3 Teknik/Süreç Sorusu: (Adayı köşeye sıkıştırmak veya tebrik etmek için)

Rapor dilin ikna edici, Türkçe ve son derece profesyonel olmalıdır."""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Lütfen toplanan tüm teknik verileri sentezleyerek İK Nihai Raporunu Kart Formatında hazırla.")
    ]
    
    response = await llm.ainvoke(messages)
    
    tokens = 0
    if response.usage_metadata:
        tokens = response.usage_metadata.get("total_tokens", 0)
        
    return {
        "final_hr_report": response.content, 
        "total_tokens": tokens,
        "current_agent": "HR Synthesizer"
    }
