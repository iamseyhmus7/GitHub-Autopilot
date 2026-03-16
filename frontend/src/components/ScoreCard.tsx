"use client";

import { motion } from "framer-motion";
import styles from "./ScoreCard.module.css";

interface ScoreProps {
  label: string;
  score: number;
  color?: string;
}

export default function ScoreCard({ label, score, color }: ScoreProps) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <motion.div 
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={styles.scoreCard}
    >
      <div className={styles.circularProgress}>
        <svg className={styles.svg}>
          <circle className={styles.backgroundCircle} cx="40" cy="40" r={radius} />
          <motion.circle 
            className={styles.foregroundCircle} 
            cx="40" 
            cy="40" 
            r={radius}
            stroke={color || "var(--primary)"}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.5, ease: "easeOut" }}
          />
        </svg>
        <div className={styles.scoreValue}>{score}</div>
      </div>
      <span className={styles.label}>{label}</span>
    </motion.div>
  );
}

export function TechnicalScoreBoard({ scores }: { scores: Record<string, number> }) {
  const scoreData = Object.entries(scores).map(([key, val]) => ({
    label: key.charAt(0).toUpperCase() + key.slice(1).replace("_", " "),
    score: val,
    color: val > 80 ? "#10b981" : val > 50 ? "#f59e0b" : "#ef4444"
  }));

  return (
    <div className={scoreData.length > 0 ? styles.scoreGrid : ""}>
      {scoreData.map((data, i) => (
        <ScoreCard key={i} {...data} />
      ))}
    </div>
  );
}
