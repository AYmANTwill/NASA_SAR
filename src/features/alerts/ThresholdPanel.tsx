import { useStore } from "../../store/useStore";
import { useI18n } from "../../lib/i18n";
import { defaultThresholds } from "./rules";
import type { Thresholds } from "../../data/types";
import { isMock } from "../../data/loader";
export default function ThresholdPanel(){
const {thresholds,set}=useStore();const {t,locale}=useI18n();
const controls:{key:keyof Thresholds;label:string;min:number;max:number;step:number}[]=[{key:"deformationCmMonth",label:"Deformation > cm/month",min:1,max:20,step:.5},{key:"coherenceLossPct",label:"Coherence loss > %",min:10,max:90,step:5},{key:"expansionHaMonth",label:"Mining expansion > ha/month",min:1,max:50,step:1},{key:"goffCm",label:"Dam GOFF > cm",min:1,max:50,step:1}];
return <details className="threshold-panel" open><summary>{t("Thresholds")}</summary><p>{t(isMock?"Mock rules only; not operational safety thresholds.":"Threshold controls apply only to mock mode.")}</p><div className="threshold-grid">{controls.map(c=><label key={c.key}><span>{t(c.label)}<b>{thresholds[c.key].toLocaleString(locale)}</b></span><input disabled={!isMock} aria-label={t(c.label)} type="range" min={c.min} max={c.max} step={c.step} value={thresholds[c.key]} onChange={e=>set({thresholds:{...thresholds,[c.key]:Number(e.target.value)}})}/></label>)}</div><button disabled={!isMock} onClick={()=>set({thresholds:{...defaultThresholds}})}>{t("Reset thresholds")}</button></details>;
}
