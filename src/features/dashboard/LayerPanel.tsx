import { Info, ChevronDown, Layers, X } from "lucide-react";
import { useStore } from "../../store/useStore";
import type { CaseStudy } from "../../data/types";
import { caseIcons } from "../../lib/caseRegistry";
import { caseText, useI18n } from "../../lib/i18n";
import { layerGroups, relevantLayers } from "../../data/layers";
export default function LayerPanel({cases,current}:{cases:CaseStudy[];current:CaseStudy}){
 const {layers,toggleLayer,selectCase,set,sheet,layersOpen,siteId}=useStore();const {locale,t}=useI18n();
 const available=relevantLayers(current);
 return <aside className={"left-panel glass "+(!layersOpen?"desktop-hidden ":"")+(sheet==="layers"?"sheet-open":"")} aria-label={t("Layers")}>
 <div className="panel-heading"><span><Layers size={14}/>{t("EXPLORER")}</span><button className="mobile-only" aria-label={t("Close layers")} onClick={()=>set({sheet:null})}><X size={16}/></button><span className="desktop-only">01 — {String(cases.length).padStart(2,"0")}</span></div>
 <nav className="case-tabs" aria-label={t("Switch case")}>{cases.map((c,i)=>{const Icon=caseIcons[c.phenomenon];return <button key={c.id} title={(i+1)+" · "+caseText(c,"name",locale)} aria-label={caseText(c,"name",locale)} aria-pressed={c.id===current.id} className={c.id===current.id?"selected":""} style={{color:c.accentColor}} onClick={()=>selectCase(c.id)}><Icon size={19}/><span className="case-tab-tooltip">{caseText(c,"name",locale)} <kbd>{i+1}</kbd></span></button>;})}</nav>
 <div className="case-heading"><span className="eyebrow">{t("CASE STUDY")} / {String(cases.findIndex(c=>c.id===current.id)+1).padStart(2,"0")}</span><h2>{caseText(current,"name",locale)}<ChevronDown size={16}/></h2><p>{caseText(current,"subtitle",locale)}</p><div className="location-tag">{current.center[0].toFixed(2)}° / {current.center[1].toFixed(2)}° <span>2026</span></div>
 {current.sites&&<label className="site-selector"><span>{t("Select site")}</span><select aria-label={t("Select site")} value={siteId??current.sites[0].id} onChange={e=>set({siteId:e.target.value,focus:null,compare:false})}>{current.sites.map(s=><option key={s.id} value={s.id}>{s.nameI18n?.[locale]??s.name}</option>)}</select><small>{t("Synthetic site")}</small></label>}
 </div>
 <div className="layer-scroll">{layerGroups.map((group,i)=>{const items=available.filter(l=>l.group===i);return items.length?<section className="layer-group" key={i}><h3>{group[locale]}</h3>{items.map(item=><div className={"layer-row "+(layers[item.id]>0?"enabled":"")} key={item.id}><div><button className="layer-toggle" role="switch" aria-checked={layers[item.id]>0} aria-label={item.label[locale]} onClick={()=>toggleLayer(item.id)}><span/></button><span className="layer-name">{item.label[locale]}</span><span className="product-tag">{item.tag}</span><span title={item.info[locale]} tabIndex={0} className="info-tip"><Info size={12}/><span>{item.info[locale]}</span></span></div>{layers[item.id]>0&&<input aria-label={item.label[locale]+" "+t("opacity")} type="range" min="0" max="1" step=".01" value={layers[item.id]} onChange={e=>set({layers:{...layers,[item.id]:Number(e.target.value)}})}/>}</div>)}</section>:null;})}
 {current.historicalReferences&&<section className="historical-references"><h3>{t("HISTORICAL REFERENCES")}</h3>{current.historicalReferences.map(r=><p key={r.name}><strong>{r.name} · {r.date.slice(0,4)}</strong><span>{r.note[locale]}</span></p>)}</section>}
 {current.referencePeriods&&<section className="historical-references"><h3>{t("Reference period")}</h3>{current.referencePeriods.map(r=><p key={r.product}>{r.product==="sentinel1"?"Sentinel-1":"ALOS-2"} · {r.start.slice(0,4)}–{r.end.slice(0,4)}<span>{t("SIMULATED")}</span></p>)}</section>}
 </div><div className="panel-foot"><span className="live-dot"/>{t("FILE-BASED DATA PIPELINE")} <span>v1.1</span></div></aside>;
}
