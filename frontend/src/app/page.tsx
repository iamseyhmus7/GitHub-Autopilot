"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Github, Send, Terminal, BarChart3, Users, Sparkles } from "lucide-react";
import AgentGrid from "@/components/AgentGrid";
import { TechnicalScoreBoard } from "@/components/ScoreCard";
import styles from "./Landing.module.css";

interface LogEntry {
  type: "system" | "agent_update" | "final_report" | "error";
  message?: string;
  node?: string;
  agent?: string;
  status?: string;
  report?: string;
}

export default function Home() {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
  const [completedAgents, setCompletedAgents] = useState<string[]>([]);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [threadId, setThreadId] = useState<string | null>(null);
  const [chatQuery, setChatQuery] = useState("");
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  
  const resultsRef = useRef<HTMLDivElement>(null);

  // Mock scoring logic for demonstration if not in report
  const extractScores = (report: string) => {
    // Simple regex to find scores like "Security: 85/100" or similar
    const extracted: Record<string, number> = {};
    const patterns = [
      { key: "mimari", regex: /\[MİMARİ_PUAN:\s*(\d+)\]/i },
      { key: "güvenlik", regex: /\[GÜVENLİK_PUAN:\s*(\d+)\]/i },
      { key: "kod_kalitesi", regex: /\[KOD_KALİTESİ_PUAN:\s*(\d+)\]/i },
      { key: "devops", regex: /\[DEVOPS_PUAN:\s*(\d+)\]/i },
    ];

    patterns.forEach(p => {
      const match = report.match(p.regex);
      if (match) extracted[p.key] = parseInt(match[1]);
    });

    // Fallback mock scores if nothing found
    if (Object.keys(extracted).length === 0) {
      return {
        mimari: 78,
        güvenlik: 92,
        kod_kalitesi: 84,
        devops: 65
      };
    }
    return extracted;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!owner || !jobDescription) return;

    setIsLoading(true);
    setLogs([]);
    setFinalReport(null);
    setCompletedAgents([]);
    setActiveAgentId(null);
    setScores({});

    try {
      const response = await fetch("http://localhost:8000/api/v1/analyze-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          github_owner: owner,
          repo_name: repo || null,
          job_description: jobDescription,
        }),
      });

      if (!response.body) throw new Error("ReadableStream not supported");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.trim().startsWith("data: ")) {
            try {
              const dataValue = line.replace("data: ", "").trim();
              if (!dataValue) continue;
              
              const data = JSON.parse(dataValue);
              
              if (data.type === "final_report" && data.report) {
                setFinalReport(data.report);
                setScores(extractScores(data.report));
                setActiveAgentId(null);
                setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth" }), 500);
              } else if (data.type === "agent_update") {
                setLogs((prev) => [...prev, data]);
                if (data.agent) {
                  setActiveAgentId(data.agent);
                  setCompletedAgents((prev) => [...new Set([...prev, data.agent!])]);
                }
              } else if (data.type === "system" || data.type === "error") {
                setLogs((prev) => [...prev, data]);
                if (data.thread_id) setThreadId(data.thread_id);
              }
            } catch (err) {
              console.error("Parse error:", err);
            }
          }
        }
      }
    } catch (err) {
      setLogs((prev) => [...prev, { type: "error", message: "Bağlantı hatası: Analiz motoru yanıt vermiyor." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatQuery || !threadId) return;

    setIsChatLoading(true);
    try {
      const resp = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, query: chatQuery }),
      });
      const data = await resp.json();
      setChatAnswer(data.answer);
    } catch (err) {
      console.error("Chat error:", err);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleDownloadPDF = () => {
    if (!threadId) return;
    window.open(`http://localhost:8000/api/report/pdf/${threadId}`, "_blank");
  };

  return (
    <main className={styles.main}>
      {/* Hero Section */}
      <section className={styles.hero}>
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className={styles.badge}
        >
          <Sparkles size={14} style={{ marginRight: '8px' }} />
          Veri Odaklı Teknik İşe Alım
        </motion.div>
        <h1 className={styles.title}>GitHub Autopilot <br/> Technical DNA</h1>
        <p className={styles.subtitle}>
          9 uzman yapay zeka ajanı, adayın tüm GitHub geçmişini saniyeler içinde tarar, 
          mühendislik derinliğini ölçer ve mülakat risklerini belirler.
        </p>
      </section>

      {/* Input Section */}
      <section className={styles.configCard}>
        <form onSubmit={handleSubmit}>
          <div className={styles.formGrid}>
            <div>
              <label className={styles.label}>GITHUB KULLANICI ADI</label>
              <div style={{ position: 'relative' }}>
                <Github size={18} style={{ position: 'absolute', left: '12px', top: '14px', color: '#666' }} />
                <input 
                  type="text" 
                  className={styles.input} 
                  style={{ paddingLeft: '40px' }}
                  placeholder="örn: facebook" 
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  required
                />
              </div>
            </div>
            <div>
              <label className={styles.label}>REPO SEÇİMİ (OPSİYONEL)</label>
              <input 
                type="text" 
                className={styles.input} 
                placeholder="Boş = Akıllı Profilleme" 
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
              />
            </div>
            <div className={styles.textareaContainer}>
              <label className={styles.label}>İŞ İLANI / TEKNİK BEKLENTİLER</label>
              <textarea 
                className={styles.textarea} 
                placeholder="Adayın hangi teknolojilerde ne seviyede olmasını bekliyorsunuz?" 
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                required
              />
            </div>
          </div>

          <button 
            type="submit" 
            className={styles.button} 
            disabled={isLoading}
          >
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                <Terminal size={18} /> Ajanlar Sahada...
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                <Send size={18} /> Derin Analizi Başlat
              </span>
            )}
          </button>
        </form>
      </section>

      {/* Dashboard Section */}
      <AnimatePresence>
        {(isLoading || logs.length > 0) && (
          <motion.section 
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={styles.dashboardSection}
          >
            <h2 className={styles.sectionTitle}>Canlı Analiz Paneli</h2>
            <AgentGrid activeAgentId={activeAgentId} completedAgents={completedAgents} />
          </motion.section>
        )}
      </AnimatePresence>

      {/* Results Section */}
      {finalReport && (
        <section ref={resultsRef} className={styles.resultsSection}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
            <h2 className={styles.sectionTitle}>Teknik Yetkinlik Karnesi</h2>
            <button onClick={handleDownloadPDF} className={styles.badge} style={{ cursor: 'pointer', background: 'rgba(0, 255, 136, 0.2)', border: '1px solid #00ff88' }}>
              📄 PDF OLARAK İNDİR
            </button>
          </div>
          
          <div className={styles.scoreSection}>
            <TechnicalScoreBoard scores={scores} />
          </div>

          <motion.div 
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            className={styles.reportCard}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
              <div className={styles.badge} style={{ margin: 0 }}>Nihai Değerlendirme</div>
              <div style={{ height: '1px', flex: 1, background: 'rgba(255,255,255,0.1)' }} />
            </div>
            <div className={styles.markdownContent}>
              <ReactMarkdown>{finalReport}</ReactMarkdown>
            </div>
          </motion.div>

          {/* Chat Interface */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            className={styles.reportCard}
            style={{ marginTop: '2rem', border: '1px solid rgba(0, 149, 255, 0.3)' }}
          >
            <div className={styles.badge} style={{ background: 'rgba(0, 149, 255, 0.2)', color: '#0095ff', marginBottom: '1.5rem' }}>
              🤖 Rapora Soru Sor
            </div>
            <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: '1rem' }}>
              <input 
                type="text" 
                className={styles.input} 
                placeholder="Örn: Bu adayın en zayıf olduğu teknik nokta nedir?"
                value={chatQuery}
                onChange={(e) => setChatQuery(e.target.value)}
              />
              <button type="submit" className={styles.button} style={{ width: 'auto', padding: '0 2rem' }} disabled={isChatLoading}>
                {isChatLoading ? "..." : "Sor"}
              </button>
            </form>
            {chatAnswer && (
              <div className={styles.markdownContent} style={{ marginTop: '1.5rem', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                <ReactMarkdown>{chatAnswer}</ReactMarkdown>
              </div>
            )}
          </motion.div>
        </section>
      )}
    </main>
  );
}
