import { motion } from "framer-motion";
import { ArrowUpRight, ArrowRight, Play, Radio } from "lucide-react";
import type { CaseStudy } from "../../data/types";
import { useStore } from "../../store/useStore";
import { caseIcons } from "../../lib/caseRegistry";
import { caseText, useI18n } from "../../lib/i18n";
export default function Intro({cases}:{cases:CaseStudy[]}){
const {selectCase,set}=useStore();const {t,locale}=useI18n();
return <main className="intro"><motion.div className="intro-copy" initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} transition={{duration:.8}}>
<div className="eyebrow"><span className="live-dot"/>{t("AN EARTH SURFACE OBSERVATORY")}</div><h1>{t("Every change")}<br/>{t("leaves a")} <span>{t("signal.")}</span></h1><p className="intro-description">{t("Listening to the Earth's surface change, one radar pulse at a time.")}</p><p className="hero-product-line">{t("NISAR L-band SAR · GCOV · GUNW · GOFF · 8 phenomena")}</p>
<div className="intro-actions"><button className="primary" onClick={()=>selectCase(cases[0].id)}>{t("Explore the planet")}<ArrowUpRight size={18}/></button><button className="text-button" onClick={()=>{selectCase(cases[0].id);set({tour:true,playing:true});}}><Play size={14}/>{t("Take a guided tour")}<span>104 SEC</span></button></div>
<div className="mission-specs"><div><strong>{t("L-band")}</strong><span>{t("RADAR FREQUENCY")}</span></div><div><strong>{t("12 days")}</strong><span>{t("REVISIT CYCLE")}</span></div><div><strong>{t("8 signals")}</strong><span>{t("ONE CHANGING EARTH")}</span></div></div>
<div className="intro-note"><Radio size={15}/><span>DANCING WITH THE SARS<br/>BEN GUERIR · {locale==="fr"?"MAROC · 14–15 NOVEMBRE":"MOROCCO · NOVEMBER 14–15"} 2026</span></div></motion.div>
<div className="globe-caption"><span className="orbit-label">{t("01 / PLANETARY PERSPECTIVE")}</span><span>{t("Drag to rotate · Scroll to explore")}</span></div>
<div className="case-strip"><div className="strip-heading"><span>{t("EIGHT SIGNALS. A PLANET OF CHANGE.")}</span><span>{t("SELECT A SIGNAL")}<ArrowRight size={12}/></span></div><div className="case-cards">{cases.map((c,i)=>{const Icon=caseIcons[c.phenomenon];return <motion.button key={c.id} className="case-card" style={{"--case-accent":c.accentColor} as React.CSSProperties} whileHover={{y:-5}} onClick={()=>selectCase(c.id)}><div className="case-card-top"><Icon size={18}/><span>{String(i+1).padStart(2,"0")}</span><ArrowUpRight size={16}/></div><strong>{caseText(c,"name",locale)}</strong><span>{caseText(c,"subtitle",locale)}</span><div className="case-card-line"/></motion.button>;})}</div></div>
<footer className="intro-footer"><span>SPACE APPS 2026 <i/>{t("TEAM THE SAR")} <i/> BEN GUERIR · 14–15 NOV 2026</span><span>{t("EXPERIMENTAL OBSERVATORY")}<i/>{t("SIMULATED DATA")}</span></footer></main>;
}
