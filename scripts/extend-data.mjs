import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";
const root="public/data",read=name=>JSON.parse(fs.readFileSync(path.join(root,name),"utf8"));
const save=(name,value)=>{const p=path.join(root,name);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(value,null,2));};
const L=(en,fr)=>({en,fr});
const M=(key,en,fr,value,unit="",digits=0,sampleKey)=>({key,label:L(en,fr),value,unit,digits,...(sampleKey?{sampleKey}:{})});
const classes=["earthquake","waterStress","flood","deforestation","subsidence","miningExpansion","tailingsInstability","miningRehabilitation"];
const cases=read("cases.json");
const legacyText=[
["Venezuela","Séismes côtiers","Unwrapped GUNW phase describes line-of-sight deformation; GOFF identifies large-motion zones. GCOV changes and USGS-style epicentres provide complementary context. All events and measurements shown are simulated.","La phase déroulée GUNW décrit la déformation en ligne de visée ; GOFF localise les grands déplacements. Les changements GCOV et les épicentres de type USGS complètent l’analyse. Événements et mesures affichés sont simulés.","Séquence sismique simulée"],
["Souss-Massa","L’eau sous pression","Compare GCOV backscatter, MODIS-style NDVI, rainfall and GUNW subsidence. SMAP and GRACE-FO provide coarse regional water context; they cannot resolve a farm or prove a local pumping mechanism.","Comparer rétrodiffusion GCOV, NDVI de type MODIS, pluies et subsidence GUNW. SMAP et GRACE-FO apportent un contexte hydrique régional grossier ; ils ne résolvent pas une parcelle et ne prouvent pas un mécanisme local de pompage.","Pluie cumulée sur 12 jours"],
["Bihar","Le fleuve hors de ses rives","Water can act as a specular reflector and reduce GCOV backscatter. GUNW coherence loss helps locate disturbed surfaces. Cross-check with GFM flood extent, rainfall and exposed OSM-style roads and villages. These layers are simulated.","L’eau peut agir comme réflecteur spéculaire et faire chuter la rétrodiffusion GCOV. La perte de cohérence GUNW aide à localiser les surfaces perturbées. Recouper avec l’emprise GFM, les pluies et les routes/villages de type OSM exposés. Couches simulées.","Précipitations de mousson"],
["Amazonie","La lisière forestière se transforme","A persistent backscatter change and a coherence break suggest structural canopy change. Its sign depends on canopy, moisture and geometry; no universal L-band sign is assumed. FIRMS-style hotspots, optical context and Sentinel-1 history support interpretation.","Une variation persistante de rétrodiffusion et une rupture de cohérence suggèrent un changement structurel du couvert. Le signe dépend de la végétation, de l’humidité et de la géométrie ; aucun signe universel en bande L n’est supposé. Feux de type FIRMS, optique et historique Sentinel-1 complètent l’interprétation.","Détections de feu simulées"],
["Mexico","Une ville qui s’affaisse","GUNW time series reveal differential LOS subsidence. PS-InSAR points and an SBAS velocity field add spatial context; Sentinel-1 provides a pre-NISAR reference. Compare with urban infrastructure; attribution to groundwater extraction requires independent evidence.","Les séries GUNW révèlent une subsidence différentielle en ligne de visée. Les points PS-InSAR et le champ de vitesse SBAS ajoutent un contexte spatial ; Sentinel-1 fournit une référence pré-NISAR. Comparer au bâti ; l’attribution au pompage exige des preuves indépendantes.","Intersections avec les infrastructures"]
];
cases.forEach((c,i)=>{const v=legacyText[i];Object.assign(c,{nameI18n:L(c.name,v[0]),subtitleI18n:L(c.subtitle,v[1]),descriptionI18n:L(v[2],v[3]),contextLabelI18n:L(c.contextLabel,v[4])});for(const cl of classes)c.classProbabilities[cl]??=0;});
const bounds=(center,span)=>[center[1]-span,center[0]-span*.7,center[1]+span,center[0]+span*.7];
const dates=Array.from({length:8},(_,i)=>new Date(Date.UTC(2026,5,1+i*12)).toISOString().slice(0,10));
function make(id,name,nameFr,subtitle,subtitleFr,phenomenon,accentColor,center,zoom,span,description,descriptionFr,metrics,kpis,contextValue,contextLabel,contextFr){
return {id,name,nameI18n:L(name,nameFr),subtitle,subtitleI18n:L(subtitle,subtitleFr),phenomenon,accentColor,center,zoom,pitch:42,bearing:-12,bbox:bounds(center,span),dates,description,descriptionI18n:L(description,descriptionFr),kpis:{displacement_mm:48,affected_area_km2:4.8,backscatter_db:3.9,coherence:.64,affected_population:2800,...kpis},metrics,classProbabilities:Object.fromEntries(classes.map(cl=>[cl,cl===phenomenon?.91:.09/7])),predictedClass:phenomenon,confidence:.91,contextValue,contextLabel,contextLabelI18n:L(contextLabel,contextFr)};
}
cases.push(make("north-africa-mining","North African mines","Mines d’Afrique du Nord","The expanding pit","La fosse s’étend","miningExpansion","#FF4FA3",[32.88,-6.91],11,.055,
"Red GCOV log-ratio patches illustrate pit expansion and exposed rock. GUNW slope motion and GOFF offsets are compared with rainfall, neighbouring roads and settlements. Historical Sentinel-1 and ALOS-2 layers are simulated references, not observed extraction records.",
"Des plages rouges de log-ratio GCOV illustrent l’expansion de fosse et la roche exposée. Mouvements de talus GUNW et offsets GOFF sont comparés aux pluies, routes et villages riverains. Les historiques Sentinel-1 et ALOS-2 sont des références simulées, pas des relevés d’exploitation.",
[M("pit_expansion_ha","Pit expansion","Expansion de fosse",124,"ha"),M("expansion_ha_month","Expansion rate","Vitesse d’expansion",18.5,"ha/mo",1,"expansion_ha_month"),M("slope_velocity_mm_year","Max slope deformation","Déformation max des talus",86,"mm/yr"),M("unstable_area_km2","Unstable area","Zone instable",1.24,"km²",2),M("exposed_infrastructure","Exposed infrastructure","Infrastructures exposées",17)],
{pit_expansion_ha:124,expansion_ha_month:18.5,slope_velocity_mm_year:86,unstable_area_km2:1.24,exposed_infrastructure:17},"2015–2025","Synthetic Sentinel-1 reference","Référence Sentinel-1 synthétique"));
cases.push(make("tailings-dams","Tailings dams","Barrages à résidus","Watching the embankment","Surveiller la digue","tailingsInstability","#FF3B3B",[-20.12,-44.12],13,.012,
"Localized GUNW deformation, a coherence drop and rising offsets illustrate a possible embankment instability pattern. Rainfall and downstream infrastructure add context. Brumadinho 2019 and Mount Polley 2014 are historical references only; this synthetic 2026 scenario is not a reconstruction, forecast or safety assessment.",
"Déformation GUNW localisée, baisse de cohérence et offsets croissants illustrent un motif possible d’instabilité. Pluies et infrastructures en aval ajoutent du contexte. Brumadinho 2019 et Mount Polley 2014 sont des repères historiques ; ce scénario synthétique de 2026 n’est ni une reconstitution, ni une prévision, ni une expertise de sécurité.",
[M("deformation_mm_month","Dam deformation","Déformation du barrage",68,"mm/mo",1,"deformation_mm_month"),M("coherence","Mean coherence","Cohérence moyenne",.37,"",2,"coherence"),M("goff_cm","Max GOFF displacement","Déplacement GOFF max",16,"cm",1,"goff_cm"),M("affected_population","Downstream population","Population en aval",8200),M("exposed_infrastructure","Downstream infrastructure","Infrastructures en aval",43)],
{displacement_mm:176,coherence:.37,goff_cm:16,deformation_mm_month:68,affected_population:8200,exposed_infrastructure:43},"186 mm","Synthetic intense rainfall episode","Épisode simulé de pluies intenses"));
cases.push(make("mine-rehabilitation","Mine rehabilitation","Réhabilitation minière","Life after extraction","La vie après l’extraction","miningRehabilitation","#2DD4BF",[32.5,-6.6],12,.025,
"Increasing MODIS-style NDVI and changing L-band backscatter illustrate revegetation of a closed mine. GUNW residual motion is checked against seasonal rainfall and pre-closure Sentinel-1/ALOS-2 context. The location, closure date and recovery trajectory are synthetic.",
"La hausse du NDVI de type MODIS et l’évolution de la rétrodiffusion en bande L illustrent la revégétalisation d’une mine fermée. Le mouvement résiduel GUNW est comparé aux pluies saisonnières et aux références Sentinel-1/ALOS-2 avant fermeture. Position, date de fermeture et trajectoire sont synthétiques.",
[M("revegetated_pct","Revegetated surface","Surface revégétalisée",72,"%",0,"revegetated_pct"),M("ndvi","Mean NDVI","NDVI moyen",.68,"",2,"ndvi"),M("residual_velocity_mm_year","Residual subsidence","Subsidence résiduelle",-2.4,"mm/yr",1),M("closure_date","Closure date","Date de fermeture","2022-09-30"),M("stability_trend","Stability trend","Tendance de stabilité","Improving")],
{displacement_mm:-3,revegetated_pct:72,ndvi:.68,residual_velocity_mm_year:-2.4,closure_date:"2022-09-30",stability_trend:"Improving"},"72%","Synthetic vegetation recovery","Reprise végétale simulée"));
function site(c,id,name,nameFr,center,span,zoom,base=false){return {id,name,nameI18n:L(name,nameFr),center,bbox:bounds(center,span),zoom,dataPath:base?c.id:c.id+"/sites/"+id,description:L("Synthetic site-specific field; coordinates are approximate.","Champ propre au site simulé ; coordonnées approximatives.")};}
cases[5].sites=[site(cases[5],"khouribga","Khouribga · Morocco","Khouribga · Maroc",[32.88,-6.91],.055,11,true),site(cases[5],"gafsa","Gafsa · Tunisia","Gafsa · Tunisie",[34.42,8.78],.055,11),site(cases[5],"djebel-onk","Djebel Onk · Algeria","Djebel Onk · Algérie",[34.6,8],.055,11)];
cases[6].sites=[site(cases[6],"brazil","Brazil · Brumadinho reference","Brésil · référence Brumadinho",[-20.12,-44.12],.012,13,true),site(cases[6],"north-africa","North Africa · synthetic site","Afrique du Nord · site synthétique",[32.86,-6.94],.012,13),site(cases[6],"south-africa","South Africa · synthetic site","Afrique du Sud · site synthétique",[-26.18,27.82],.012,13)];
cases[6].historicalReferences=[{name:"Brumadinho",date:"2019-01-25",note:L("Historical event, predates NISAR; no event reconstruction is shown.","Événement historique antérieur à NISAR ; aucune reconstitution n’est affichée.")},{name:"Mount Polley",date:"2014-08-04",note:L("Historical event in Canada, not a selectable monitoring site.","Événement historique au Canada, pas un site de suivi sélectionnable.")}];
const baseProducts=["gcov","gunw","coherence","goff","ndvi","rainfall"];
function extras(i){return ["sentinel1",...([4,6].includes(i)?["sbas"]:[]),...([1,2,6,7].includes(i)?["smap"]:[]),...(i===1?["grace"]:[]),...([0,5,6,7].includes(i)?["dem_slope"]:[]),...([0,4,5,6,7].includes(i)?["geology"]:[]),...(i>=5?["alos2"]:[])];}
cases.forEach((c,i)=>{c.availableProducts=[...baseProducts,...extras(i),"classification","infrastructure","optical","labels",...([4,6].includes(i)?["ps_insar"]:[]),...(i===0?["events"]:[]),...(i===3?["fires"]:[]),...([2,6].includes(i)?["floodExtent"]:[])];c.referencePeriods=[{product:"sentinel1",start:"2015-01-01",end:"2025-12-31",simulated:true},...(i>=5?[{product:"alos2",start:"2018-01-01",end:"2024-12-31",simulated:true}]:[])];});
const ramps={gcov:{unit:"dB",min:-12,max:12,colormap:["#287dff","#162d49","#ff633e"]},gunw:{unit:"mm",min:-250,max:250,colormap:["#6345f5","#30cbe8","#9de051","#ffe43d","#ff5b50","#6345f5"]},coherence:{unit:"",min:0,max:1,colormap:["#440154","#31688e","#35b779","#fde725"]},goff:{unit:"m",min:0,max:.3,colormap:["#182453","#b57bff","#fff0c8"]},ndvi:{unit:"NDVI",min:0,max:1,colormap:["#9d6e35","#c6c64b","#2dd4bf"]},rainfall:{unit:"mm",min:0,max:300,colormap:["#152848","#3ba7ff","#c1eaff"]},sentinel1:{unit:"dB",min:-12,max:12,colormap:["#287dff","#162d49","#ff633e"]},alos2:{unit:"dB",min:-12,max:12,colormap:["#283750","#ac74d9","#ffe9c7"]},sbas:{unit:"mm/yr",min:-250,max:100,colormap:["#3ba7ff","#c5cde0","#ff4f69"]},smap:{unit:"m³/m³",min:0,max:.6,colormap:["#925b36","#aecf89","#3ba7ff"]},grace:{unit:"cm EWH",min:-30,max:30,colormap:["#d4673d","#f3e0c2","#2c8bc8"]},dem_slope:{unit:"°",min:0,max:60,colormap:["#1b252c","#77908a","#f2dfb6"]},geology:{unit:"unit id",min:1,max:4,colormap:["#788675","#bb9168","#6e83a8","#b5799b"]}};
const hex=h=>h.match(/[0-9a-f]{2}/gi).map(v=>parseInt(v,16));
function rgb(t,colors){const pos=Math.max(0,Math.min(.999,t))*(colors.length-1),i=Math.floor(pos);return hex(colors[i]).map((v,j)=>Math.round(v+(hex(colors[i+1])[j]-v)*(pos-i)));}
const coll=features=>({type:"FeatureCollection",features});
for(const [ci,c] of cases.entries()){
 const targets=[{...c,path:c.id,siteId:c.sites?.[0].id},...(c.sites??[]).filter(s=>s.dataPath!==c.id).map(s=>({...c,center:s.center,bbox:s.bbox,zoom:s.zoom,path:s.dataPath,siteId:s.id}))];
 for(const [si,target] of targets.entries()){
 const old=ci<5?read("timeseries/"+c.id+".json"):null;
 const series=old??c.dates.map((date,j)=>({date,backscatter_db:+(ci===7?-3+j*.8:ci===5?j*.75:-j*.45).toFixed(2),coherence:+(j<3?.94-j*.012:ci===6?.65-(j-3)*.07:ci===5?.68-(j-3)*.025:.85+j*.01).toFixed(2),displacement_mm:+((ci===6?j*j*3.6:ci===5?j*7:-j*.4)*(1+si*.12)).toFixed(1),rainfall_mm:Math.round((ci===6?75:20)*(1+Math.sin(j*1.5))),ndvi:+(ci===7?.2+j*.068:.55-j*.03).toFixed(3)}));
 series.forEach((row,j)=>Object.assign(row,{deformation_mm_month:ci===6?+(12+j*j*1.15+si*4).toFixed(1):+(Math.abs(row.displacement_mm)/Math.max(1,j*12)*30).toFixed(1),goff_cm:ci===6?+(2+j*2.3+si).toFixed(1):+(Math.abs(row.displacement_mm)/10).toFixed(1),expansion_ha_month:ci===5?+(5+j*2+si).toFixed(1):0,revegetated_pct:ci===7?Math.round(18+j*7.7):0,velocity_mm_year:ci===7?-2.4:ci===5?86:-218}));
 if(si===0)save("timeseries/"+c.id+".json",series);
 save(target.path+"/timeseries.json",series);
 for(const product of [...(ci>=5?baseProducts:[]),...extras(ci)]){
 for(const [di,date] of c.dates.entries()){
 const meta={...ramps[product]},png=new PNG({width:160,height:160}),values=[];
 const t=(di+1)/8;
 for(let py=0;py<160;py++)for(let px=0;px<160;px++){
 const x=px/80-1,y=py/80-1,r=Math.hypot(x,y),noise=(Math.sin(x*41+y*17)+Math.cos(y*37-x*23))*.06;
 const pit=Math.exp(-Math.pow(r-(.2+t*.35),2)*160),dam=Math.exp(-x*x*9-(y-.1)*(y-.1)*35),regrowth=Math.exp(-Math.pow(x+.15,2)*4-y*y*3)*t;
 let f=ci===5?pit*.9+noise:ci===6?dam*Math.sin(x*38+t*4)+noise*.1:ci===7?regrowth*.9+noise*.2:Math.sin(x*5)*Math.cos(y*6)*.6;
 let value=product==="gunw"?(f+1)/2:product==="coherence"?series[di].coherence+noise*.3:product==="goff"?Math.abs(f)*t:product==="ndvi"?(ci===7?.2+regrowth*.7:.5+f*.3):product==="rainfall"?series[di].rainfall_mm/300+noise:product==="smap"?.4+f*.25:product==="grace"?.5-t*.35+noise:product==="dem_slope"?Math.abs(Math.sin(x*7)*Math.cos(y*8))*.8:product==="geology"?Math.floor((Math.sin(x*4)+Math.cos(y*3)+2)/4*3.99)/3:product==="sbas"?.3+f*.3:(1+f*(product==="sentinel1"?.6:1))/2;
 value=Math.min(1,Math.max(0,value));const idx=(py*160+px)*4,col=rgb(value,meta.colormap);png.data[idx]=col[0];png.data[idx+1]=col[1];png.data[idx+2]=col[2];png.data[idx+3]=Math.round(Math.pow(Math.max(0,1-r),.4)*220);
 if(px%4===0&&py%4===0)values.push(r<1?+(meta.min+value*(meta.max-meta.min)).toFixed(3):null);
 }
 const p=target.path+"/"+product+"/"+date;fs.mkdirSync(path.dirname(path.join(root,p)),{recursive:true});fs.writeFileSync(path.join(root,p+".png"),PNG.sync.write(png));save(p+".json",{...meta,bounds:target.bbox,simulated:true,source:product,referencePeriod:["sentinel1","alos2"].includes(product)?"Synthetic pre-NISAR reference; co-registered to the display date":undefined,sampleGrid:{width:40,height:40,values}});
 }}
 if([4,6].includes(ci))for(const [di,date] of c.dates.entries()){
 const [w,s,e,n]=target.bbox;save(target.path+"/ps_insar/"+date+".geojson",coll(Array.from({length:100},(_,j)=>({type:"Feature",properties:{caseId:c.id,siteId:target.siteId,velocity_mm_year:+((ci===6?95:-200)*Math.sin(j*.17)*(di+1)/8).toFixed(1),coherence:.82+(j%10)*.015,simulated:true},geometry:{type:"Point",coordinates:[w+(e-w)*(.1+(j*.618%1)*.8),s+(n-s)*(.1+(j*.382%1)*.8)]}}))));
 }
}
}
const existingAlerts=read("alerts.json").map(a=>({...a,messageI18n:L(a.message,a.id.endsWith("-1")?"L’emprise du changement s’étend":cases.find(c=>c.id===a.caseId).subtitleI18n.fr+" : signal détecté"),simulated:true}));
const generatedAlerts=cases.slice(5).map(c=>({id:c.id+"-context",caseId:c.id,class:c.phenomenon,severity:"moderate",confidence:c.confidence,lat:c.center[0],lng:c.center[1],timestamp:c.dates[7]+"T10:24:00Z",message:c.subtitle+" · contextual signal",messageI18n:L(c.subtitle+" · contextual signal",c.subtitleI18n.fr+" · signal contextuel"),simulated:true}));
save("alerts.json",[...existingAlerts,...generatedAlerts]);
for(const kind of ["events","fires","floodExtent","infrastructure","classification"]){
 const collection=read(kind+".geojson");
 for(const c of cases.slice(5))for(const [si,site] of (c.sites??[{id:undefined,center:c.center,bbox:c.bbox}]).entries()){
 const [w,s,e,n]=site.bbox;
 for(let j=0;j<(kind==="infrastructure"?18:kind==="classification"?12:3);j++){
 const lng=w+(e-w)*(.12+(j*.618%1)*.7),lat=s+(n-s)*(.12+(j*.381%1)*.7),size=(e-w)*.04;
 collection.features.push({type:"Feature",properties:{caseId:c.id,siteId:si===0?undefined:site.id,class:c.phenomenon,name:kind+" "+j,height:10+j*3,simulated:true},geometry:["events","fires"].includes(kind)?{type:"Point",coordinates:[lng,lat]}:{type:"Polygon",coordinates:[[[lng,lat],[lng+size,lat],[lng+size,lat+size],[lng,lat+size],[lng,lat]]]}});
 }}
 save(kind+".geojson",collection);
}
save("cases.json",cases);
console.log("Extended to 8 classes/cases, 4 additional site datasets, advanced/reference rasters and PS-InSAR points. Original five observations retained.");
