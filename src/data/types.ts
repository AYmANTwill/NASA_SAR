export type Locale = "en" | "fr";
export type Phenomenon = "earthquake" | "waterStress" | "flood" | "deforestation" | "subsidence" | "miningExpansion" | "tailingsInstability" | "miningRehabilitation";
export type Product = "gcov" | "gunw" | "coherence" | "goff" | "ndvi" | "rainfall" | "sentinel1" | "alos2" | "sbas" | "smap" | "grace" | "dem_slope" | "geology";
export type LayerId = Product | "ps_insar" | "classification" | "events" | "fires" | "floodExtent" | "infrastructure" | "optical" | "labels";
export interface LocalizedText { en: string; fr: string }
export interface Metric { key:string; label:LocalizedText; unit:string; value:number|string; digits?:number; sampleKey?:keyof Sample }
export interface Site {media?:{timelapse:boolean};id:string;name:string;nameI18n?:LocalizedText;center:[number,number];bbox:[number,number,number,number];zoom:number;dataPath:string;description?:LocalizedText;metrics?:Metric[]}
export interface CaseStudy {
 media?:{timelapse:boolean};
 id:string;name:string;subtitle:string;phenomenon:Phenomenon;accentColor:string;center:[number,number];zoom:number;pitch:number;bearing:number;bbox:[number,number,number,number];dates:string[];description:string;
 kpis:{displacement_mm:number;affected_area_km2:number;backscatter_db:number;coherence:number;affected_population:number;[key:string]:number|string};
 classProbabilities:Record<Phenomenon,number>;predictedClass:Phenomenon;confidence:number;contextValue:string;contextLabel:string;
 nameI18n?:LocalizedText;subtitleI18n?:LocalizedText;descriptionI18n?:LocalizedText;contextLabelI18n?:LocalizedText;
 metrics?:Metric[];sites?:Site[];siteId?:string;dataPath?:string;availableProducts?:LayerId[];
 historicalReferences?:{name:string;date:string;note:LocalizedText}[];
 referencePeriods?:{product:Product;start:string;end:string;simulated:boolean}[];
}
export interface Sample {date:string;backscatter_db:number;coherence:number;displacement_mm:number;rainfall_mm:number;ndvi:number;deformation_mm_month?:number;goff_cm?:number;expansion_ha_month?:number;revegetated_pct?:number;velocity_mm_year?:number}
export interface Alert {id:string;caseId:string;class:Phenomenon;severity:"high"|"moderate"|"critical"|"low";confidence:number;lat:number;lng:number;timestamp:string;message:string;messageI18n?:LocalizedText;siteId?:string;trigger?:string;observedValue?:number;threshold?:number;unit?:string;simulated?:boolean}
export interface Thresholds {deformationCmMonth:number;coherenceLossPct:number;expansionHaMonth:number;goffCm:number}
export interface RasterMeta {bounds:[number,number,number,number];colormap:string[];unit:string;min:number;max:number;simulated?:boolean;sampleGrid?:{width:number;height:number;values:(number|null)[]};source?:string;referencePeriod?:string}
export const phenomenonLabels:Record<Phenomenon,string>={earthquake:"Earthquake",waterStress:"Water stress",flood:"Flood",deforestation:"Deforestation",subsidence:"Subsidence",miningExpansion:"Mining expansion",tailingsInstability:"Tailings instability",miningRehabilitation:"Mine rehabilitation"};
export const productLabels:Record<Product,string>={gcov:"Backscatter change",gunw:"Surface deformation",coherence:"Interferometric coherence",goff:"Pixel offsets",ndvi:"Vegetation index",rainfall:"Rainfall",sentinel1:"Sentinel-1 · C band",alos2:"ALOS-2 · L band",sbas:"SBAS velocity",smap:"Soil moisture",grace:"Groundwater anomaly",dem_slope:"Slope / relief",geology:"Geology"};
