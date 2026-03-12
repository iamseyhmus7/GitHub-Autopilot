from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from src.agents.llm_utils import get_agent_llm, create_agent_prompt, run_agent_loop

async def architecture_reviewer_node(state: HRGraphState):
    """Ajan 3: Mimari İnceleyici"""
    print("🤖 [Ajan 3] Architecture Reviewer (Mimari İnceleyici) devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_repo_files"])
    sys_prompt = create_agent_prompt(
        "Sen 'Architecture Reviewer' ajanısın. Görevin projenin klasör hiyerarşisine bakarak (MVC, Clean Architecture, Microservices vb.) bir mimari desene uyup uymadığını analiz etmektir. Aday dosyaları rastgele mi dağıtmış yoksa mantıklı bir katmanlandırma mı yapmış?",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Lütfen repoyu tarayarak mimari yaklaşımı analiz et.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "architecture_analysis": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Architecture Reviewer"
    }

async def code_quality_inspector_node(state: HRGraphState):
    """Ajan 4: Kod Kalite Müfettişi"""
    print("🤖 [Ajan 4] Code Quality Inspector (Kod Kalite Müfettişi) devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_repo_files", "get_file_content", "search_code"])
    sys_prompt = create_agent_prompt(
        "Sen 'Code Quality Inspector' ajanısın. Görevin kaynak kod dosyalarının (örn: .java, .js) içine girerek Clean Code (Temiz Kod), SOLID prensipleri, isimlendirme standartları ve fonksiyon boyutlarını acımasızca eleştirmektir. Aday temiz ve okunabilir kod yazmış mı? Lütfen 1-2 dosya açıp bak.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Lütfen önemli kaynak kodlarını bulup Kod Kalite (Code Quality) raporu çıkar.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "code_quality_report": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Code Quality Inspector"
    }

async def security_agent_node(state: HRGraphState):
    """Ajan 5: Güvenlik Uzmanı"""
    print("🤖 [Ajan 5] Security Agent (Güvenlik Uzmanı) devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["search_code"])
    sys_prompt = create_agent_prompt(
        "Sen 'Security Agent' ajanısın. Görevin kod tabanında unutulmuş API anahtarları (API keys), hardcoded şifreler (passwords) veya bilinen güvenlik zaaflarını (örn: SQL injection riskleri) search_code aracı ile aramaktır. Hiçbir sorun yoksa temiz raporu ver.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Lütfen hardcoded şifreler veya güvenlik zafiyetleri için kod taraması yap.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "security_report": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Security Agent"
    }
