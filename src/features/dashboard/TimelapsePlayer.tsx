import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { X,Download,Play,Pause } from "lucide-react";
import type { CaseStudy } from "../../data/types";
import { base } from "../../data/loader";
import { dataPath } from "../../data/layers";
import { useStore } from "../../store/useStore";
import { useI18n } from "../../lib/i18n";
export default function TimelapsePlayer({current}:{current:CaseStudy}){
const {set,playing}=useStore(),{t}=useI18n(),[failed,setFailed]=useState(false);
const available=current.media?.timelapse===true,url=base+"/"+dataPath(current)+"/timelapse.mp4";
return <Dialog.Root open onOpenChange={open=>{if(!open)set({animationOpen:false,playing:false});}}><Dialog.Portal><Dialog.Overlay className="modal-backdrop"/><Dialog.Content className="modal-content glass animation-dialog"><Dialog.Title>{t("Animation player")}</Dialog.Title><Dialog.Description>{t(available?"Pipeline video":"No pipeline video available. Timeline playback is still available.")}</Dialog.Description><Dialog.Close className="modal-close" aria-label={t("Close animation")}><X size={18}/></Dialog.Close>{available&&!failed?<video key={url} src={url} controls playsInline preload="metadata" onError={()=>setFailed(true)} aria-label={t("Pipeline video")}/>:<div className="animation-placeholder"><span className="radar-loader"/><p>{failed?t("Video could not be played."):t("Play timeline")}</p></div>}<div className="animation-actions"><button className="top-button" onClick={()=>set({playing:!playing})}>{playing?<Pause size={14}/>:<Play size={14}/>} {t(playing?"Pause timeline":"Play timeline")}</button>{available&&!failed&&<a className="top-button" href={url} download><Download size={14}/>{t("Export cycle")}</a>}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
