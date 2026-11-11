import type { Alert, CaseStudy, Sample, Thresholds } from "../../data/types";
export const defaultThresholds:Thresholds={deformationCmMonth:5,coherenceLossPct:50,expansionHaMonth:10,goffCm:10};
export interface Observation {caseId:string;siteId?:string;center:[number,number];series:Sample[]}
export function deriveAlerts(cases:CaseStudy[],observations:Observation[],thresholds:Thresholds):Alert[]{
return observations.flatMap(o=>{
 const c=cases.find(c=>c.id===o.caseId),last=o.series.at(-1),first=o.series[0];if(!c||!last||!first)return[];
 const loss=first.coherence>0?Math.max(0,(first.coherence-last.coherence)/first.coherence*100):0;
 const rules=[
 {key:"deformation",value:(last.deformation_mm_month??0)/10,threshold:thresholds.deformationCmMonth,unit:"cm/mo",enabled:true,en:"Deformation threshold exceeded",fr:"Seuil de déformation dépassé"},
 {key:"coherence",value:loss,threshold:thresholds.coherenceLossPct,unit:"%",enabled:true,en:"Coherence loss threshold exceeded",fr:"Seuil de perte de cohérence dépassé"},
 {key:"expansion",value:last.expansion_ha_month??0,threshold:thresholds.expansionHaMonth,unit:"ha/mo",enabled:c.phenomenon==="miningExpansion",en:"Mining expansion threshold exceeded",fr:"Seuil d’expansion minière dépassé"},
 {key:"goff",value:last.goff_cm??0,threshold:thresholds.goffCm,unit:"cm",enabled:c.phenomenon==="tailingsInstability",en:"Dam offset threshold exceeded",fr:"Seuil de déplacement du barrage dépassé"}
 ];
 return rules.filter(r=>r.enabled&&r.value>r.threshold).map(r=>({id:"threshold-"+c.id+"-"+(o.siteId??"main")+"-"+r.key,caseId:c.id,siteId:o.siteId,class:c.phenomenon,severity:c.phenomenon==="tailingsInstability"&&(r.key==="goff"||r.value>r.threshold*1.5)?"critical" as const:"high" as const,confidence:c.confidence,lat:o.center[0],lng:o.center[1],timestamp:last.date+"T12:00:00Z",message:r.en,messageI18n:{en:r.en,fr:r.fr},trigger:r.key,observedValue:+r.value.toFixed(2),threshold:r.threshold,unit:r.unit,simulated:true}));
});}
export function detectChangePoint(series:Sample[]){let result:{date:string;drop:number}|null=null;for(let i=1;i<series.length;i++){const drop=series[i-1].coherence-series[i].coherence;if(drop>=.15&&(!result||drop>result.drop))result={date:series[i].date,drop};}return result;}
