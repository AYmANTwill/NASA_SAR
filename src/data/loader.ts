import type { CaseStudy, Alert, Sample, RasterMeta, Product } from "./types";
import { dataPath } from "./layers";
export const isMock=import.meta.env.VITE_DATA_MODE!=="real";
export const base=(isMock?"/data":import.meta.env.VITE_DATA_URL||"/data").replace(/\/$/,"");
export async function loadJSON<T>(path:string,signal?:AbortSignal):Promise<T>{const response=await fetch(base+"/"+path,{signal});if(!response.ok)throw new Error("Data / Données : "+path+" ("+response.status+")");return response.json() as Promise<T>;}
export const loadCases=()=>loadJSON<CaseStudy[]>("cases.json").then(cases=>{if(!cases.length||cases.some(c=>!c.id||!c.dates?.length||c.center?.length!==2))throw new Error("Invalid / Invalide : cases.json");return cases;});
export const loadAlerts=()=>loadJSON<Alert[]>("alerts.json");
export const loadSeries=(id:string,signal?:AbortSignal)=>loadJSON<Sample[]>("timeseries/"+id+".json",signal);
export const loadCaseSeries=(c:CaseStudy,signal?:AbortSignal)=>c.dataPath?loadJSON<Sample[]>(dataPath(c)+"/timeseries.json",signal):loadSeries(c.id,signal);
export const rasterURL=(id:string,product:Product,date:string)=>base+"/"+id+"/"+product+"/"+date+".png";
export const loadMeta=(id:string,product:Product,date:string,signal?:AbortSignal)=>loadJSON<RasterMeta>(id+"/"+product+"/"+date+".json",signal);
