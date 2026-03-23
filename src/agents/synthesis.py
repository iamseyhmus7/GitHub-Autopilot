import asyncio
import time

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import HRGraphState

# HR Synthesizer tek büyük LLM çağrısı — daha uzun timeout (120s)
HR_SYNTHESIZER_TIMEOUT = 120


def _ts() -> str:
    t = time.localtime()
    ms = int((time.time() % 1) * 1000)
    return f"[{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}]"


async def hr_synthesizer_node(state: HRGraphState):
    """Ajan 10: HR Synthesizer (Baş İK Yöneticisi)"""
    print(f"{_ts()} 🧑‍💼 [HR Synthesizer] ═══ BAŞLADI ═══", flush=True)

    # Bu ajanın araç kullanmasına gerek yok. Tüm veriler zaten State içinde!
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        max_tokens=8000,
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
9. Geçmişle Karşılaştırma (Bellek): {state.get('historical_analysis')}

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

4. 📊 Teknik Yetkinlik Şeması (Mermaid JS Diyagramı)
   Lütfen adayın yetkinlik haritasını gösteren bir Mermaid 'pie' veya 'mindmap' veya 'graph TD' diyagramı oluştur. Diyagramı mutlaka ```mermaid (kod bloğu) içine al! Örnek:
   ```mermaid
   graph TD
     A[Aday Genel Profili] --> B(Backend)
     B --> C[Node.js]
     A --> D(DevOps)
     D --> E[Docker]
   ```

5. 🛠️ Teknik Gen Haritası (Kullandığı güçlü araçlar ve frameworkler, metin olarak açıklama)
6. ✅ Teknik Artılar (Green Flags)
6. ⚠️ Tespit Edilen Riskler (Red Flags)
7. 🗣️ Mülakat İçin Kritik Sorular (Adayın zayıf noktalarını test edecek 3 soru)

Rapor dili Türkçe ve son derece profesyonel olmalıdır."""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Lütfen toplanan tüm teknik verileri sentezleyerek İK Nihai Raporunu Kart Formatında hazırla."),
    ]

    # Prompt boyutunu logla (debug için)
    prompt_chars = sum(len(m.content) for m in messages)
    print(f"{_ts()} [HR Synthesizer] Prompt boyutu: {prompt_chars} karakter — LLM çağrısı başlıyor (max {HR_SYNTHESIZER_TIMEOUT}s)...", flush=True)

    t0 = time.time()
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=HR_SYNTHESIZER_TIMEOUT,
        )
        elapsed = time.time() - t0
        report_len = len(response.content)
        print(f"{_ts()} [HR Synthesizer] ✅ LLM tamamlandı ({elapsed:.1f}s) — rapor={report_len} karakter", flush=True)
    except asyncio.TimeoutError:
        elapsed = time.time() - t0
        print(f"{_ts()} [HR Synthesizer] ⏰ ZAMAN AŞIMI! ({elapsed:.1f}s >= {HR_SYNTHESIZER_TIMEOUT}s)", flush=True)
        return {
            "final_hr_report": (
                "## ⏰ Rapor Oluşturulamadı\n\n"
                f"HR Synthesizer {HR_SYNTHESIZER_TIMEOUT} saniye içinde yanıt alamadı. "
                "Lütfen tekrar deneyin."
            ),
            "total_tokens": 0,
            "current_agent": "HR Synthesizer",
        }

    tokens = 0
    if response.usage_metadata:
        tokens = response.usage_metadata.get("total_tokens", 0)

    total_elapsed = time.time() - t0
    print(f"{_ts()} [HR Synthesizer] ✅ TAMAMEN BİTTİ ({total_elapsed:.1f}s, token={tokens})", flush=True)

    return {
        "final_hr_report": response.content,
        "total_tokens": tokens,
        "current_agent": "HR Synthesizer",
    }
