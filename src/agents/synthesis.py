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
Adayın seçilmiş projelerinden gelen teknik verileri sentezleyerek 'Nihai Teknik DNA Analiz Raporu' oluşturmalısın.

Analiz Kapsamı (Tüm İlgili Projeler): {', '.join(state['relevant_repos'])}
Ana Teknik Odak (Derinlemesine İncelenen): {state['repo_name']}
    
İş İlanı Gereksinimleri: {state['job_description']}

Teknik Ajanlardan Gelen Raporlar:
1. Proje Özetleri (Geniş Perspektif): {state.get('repo_overview')}
2. Teknoloji Yığını (Tüm Projeler): {state.get('tech_stack')}
3. Derinlemesine Mimari Analiz: {state.get('architecture_analysis')}
4. Kod Kalitesi Raporu: {state.get('code_quality_report')}
5. Güvenlik Denetimi: {state.get('security_report')}
6. Emek & Geçmiş: {state.get('commit_history_analysis')}
7. DevOps & Süreç: {state.get('ci_cd_testing_status')}
8. İşbirliği & PR: {state.get('teamwork_pr_analysis')}

Görevin: Bu verileri harmanlayarak adayın hem geniş teknik spektrumunu (relevant_repos) hem de derinlemesine teknik becerilerini (repo_name) profesyonelce raporla.

RAPOR FORMATI (BU KURALA KESİNLİKLE UY):
# 🧬 Teknik DNA Analiz Raporu

1. 🌟 Aday Özeti: (Kısa ve öz, tüm projeler dahi ederek)
2. 🎯 Genel İşe Uygunluk: %X (İş ilanına göre yüzde ver)
3. 📊 Teknik Karnesi (Aşağıdaki etiketleri KESİNLİKLE satır başında kullan):
   - [MİMARİ_PUAN: XX]
   - [GÜVENLİK_PUAN: XX]
   - [KOD_KALİTESİ_PUAN: XX]
   - [DEVOPS_PUAN: XX]
   - [DOKÜMANTASYON_PUAN: XX]

4. 🛠️ Teknik Gen Haritası (Kullandığı güçlü araçlar ve frameworkler)
5. ✅ Teknik Artılar (Green Flags)
6. ⚠️ Tespit Edilen Riskler (Red Flags)
7. 🗣️ Mülakat İçin Kritik Sorular (Adayın zayıf noktalarını test edecek 3 soru)

Rapor dili Türkçe ve son derece profesyonel olmalıdır."""

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
