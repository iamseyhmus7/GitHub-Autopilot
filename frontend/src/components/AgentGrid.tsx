"use client";

import { motion } from "framer-motion";
import { 
  Search, 
  Package, 
  Layers, 
  Code, 
  ShieldCheck, 
  History, 
  Settings, 
  GitPullRequest, 
  Cpu 
} from "lucide-react";
import styles from "./AgentCard.module.css";

const AGENTS = [
  { id: "repo_explorer", name: "Repo Explorer", icon: Search, description: "Kod tabanı yapısını ve temel dosyaları haritalandırır." },
  { id: "dependency_analyst", name: "Dependency Analyst", icon: Package, description: "Harici kütüphaneleri ve güvenlik açıklarını inceler." },
  { id: "architecture_reviewer", name: "Architecture Reviewer", icon: Layers, description: "Sistem mimarisini ve modülerliğini değerlendirir." },
  { id: "code_quality", name: "Code Quality Inspector", icon: Code, description: "Kodun okunabilirliğini ve standartlara uyumunu ölçer." },
  { id: "security_agent", name: "Security Agent", icon: ShieldCheck, description: "Gizli anahtarları ve potansiyel zafiyetleri tarar." },
  { id: "git_historian", name: "Git Historian", icon: History, description: "Commit geçmişini ve ekip çalışma temposunu analiz eder." },
  { id: "devops_evaluator", name: "DevOps Evaluator", icon: Settings, description: "CI/CD süreçlerini ve deployment kalitesini kontrol eder." },
  { id: "pr_manager", name: "PR Manager", icon: GitPullRequest, description: "Pull Request kalitesini ve review süreçlerini inceler." },
  { id: "history_analyzer", name: "History Analyzer", icon: History, description: "Adayın geçmiş başvurularını ve gelişimini karşılaştırır." },
  { id: "hr_synthesis", name: "HR Synthesizer", icon: Cpu, description: "Tüm analizleri birleştirip aday puanını belirler." },
];

interface AgentGridProps {
  activeAgentId?: string | null;
  completedAgents: string[];
}

export default function AgentGrid({ activeAgentId, completedAgents }: AgentGridProps) {
  return (
    <div className={styles.grid}>
      {AGENTS.map((agent, index) => {
        const isActive = activeAgentId === agent.name || activeAgentId === agent.id;
        const isCompleted = completedAgents.includes(agent.name) || completedAgents.includes(agent.id);
        
        return (
          <motion.div 
            key={agent.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className={`${styles.card} ${isActive ? styles.activeCard : ""}`}
          >
            <div className={styles.cardHeader}>
              <div className={styles.iconWrapper}>
                <agent.icon size={20} />
              </div>
              <div>
                <h3 className={styles.title}>{agent.name}</h3>
                <div className={styles.statusIndicator}>
                  <div className={`${styles.dot} ${(isActive || isCompleted) ? styles.dotActive : ""}`} />
                  <span>{isActive ? "Analiz Ediliyor" : isCompleted ? "Tamamlandı" : "Beklemede"}</span>
                </div>
              </div>
            </div>
            <p className={styles.description}>{agent.description}</p>
            <div className={styles.progressTrack}>
              <motion.div 
                className={styles.progressBar}
                initial={{ width: "0%" }}
                animate={{ width: isCompleted ? "100%" : isActive ? "60%" : "0%" }}
                transition={{ duration: 1 }}
              />
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
