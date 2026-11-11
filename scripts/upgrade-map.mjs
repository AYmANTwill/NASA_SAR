import fs from "node:fs";
let s=fs.readFileSync("src/components/MapScene.tsx","utf8");
s=s.replace('BitmapLayer, GeoJsonLayer','BitmapLayer, GeoJsonLayer, ScatterplotLayer');
s=s.replace('import { productLabels } from "../data/types";','import { relevantLayers, relevantRasters, dataPath, layerDefinitions } from "../data/layers";\nimport { caseText, classLabel, translate, useI18n } from "../lib/i18n";');
const start=s.indexOf("const products: Product[] ="),end=s.indexOf("const context =",start);s=s.slice(0,start)+s.slice(end);
s=s.replace('  const intro = screen === "intro",','  const {locale,t}=useI18n();\n  const products=useMemo(()=>relevantRasters(current),[current]);\n  const path=dataPath(current);\n  const visibleProducts=useMemo(()=>compare&&(compareKind==="sentinel1"||compareKind==="alos2")?products.filter(p=>p==="gcov"):products,[products,compare,compareKind]);\n  const enabledKey=visibleProducts.filter(p=>layers[p]>0||compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov").join(",");\n  const [ps,setPs]=useState<FeatureCollection|null>(null);\n  const intro = screen === "intro",');
s=s.replace('setFailure("WebGL is unavailable. Explore case data using the controls.");','setFailure(translate("WebGL is unavailable. Explore case data using the controls.",useStore.getState().locale));');
s=s.replace('setFailure("Some map imagery is unavailable. Data panels remain usable.")','setFailure(translate("Some map imagery is unavailable. Data panels remain usable.",useStore.getState().locale))');
s=s.replace('setFailure("Context data could not be loaded.");','setFailure(translate("Context data could not be loaded.",useStore.getState().locale));');
s=s.replace('button.setAttribute("aria-label", "Explore " + c.name);','button.setAttribute("aria-label", t("Explore")+" "+caseText(c,"name",locale));');
s=s.replace('label.textContent = c.name;','label.textContent = caseText(c,"name",locale);');
const detailStart=s.indexOf('      detail.textContent ='),detailEnd=s.indexOf('      button.onclick',detailStart);
s=s.slice(0,detailStart)+`      detail.textContent = caseText(c,"subtitle",locale)+" · "+c.dates.at(-1)+" · "+Number(c.kpis.affected_area_km2).toLocaleString(locale)+" km²";
      button.append(dot,ring,label,detail);
      button.title=caseText(c,"subtitle",locale)+" · "+Math.round(c.confidence*100)+"% "+t("model confidence");
`+s.slice(detailEnd);
s=s.replace('    return () => markers.forEach((m) => m.remove());\n  }, [ready, intro, cases, current, selectCase]);',`    const spread=()=>{
      if(!intro||!mapRef.current)return;
      const placed:{x:number;y:number}[]=[];
      markers.forEach(marker=>{
        const projected=mapRef.current!.project(marker.getLngLat());
        const candidates:[[number,number],...[number,number][]]=[[0,0],[-48,-36],[48,-36],[-48,40],[48,40],[0,-78],[0,78]];
        const offset=candidates.find(([x,y])=>placed.every(p=>Math.hypot(p.x-projected.x-x,p.y-projected.y-y)>48))??candidates[6];
        marker.setOffset(offset);placed.push({x:projected.x+offset[0],y:projected.y+offset[1]});
      });
    };
    spread();mapRef.current.on("move",spread);
    return () => {mapRef.current?.off("move",spread);markers.forEach(m=>m.remove());};
  }, [ready, intro, cases, current, selectCase,locale,t]);`);
s=s.replace('products\n        .filter((p) => layers[p] > 0)','(enabledKey?enabledKey.split(",") as Product[]:[])',1);
s=s.replace('loadMeta(current.id, p, dateString, controller.signal)','loadMeta(path, p, dateString, controller.signal)');
s=s.replace('  }, [intro, current.id, dateString, layers]);','  }, [intro, path, dateString, enabledKey]);');
s=s.replace('  }, [intro, current, date, layers]);','  }, [intro, current, date, layers,products,path]);');
s=s.replace('          current.id,\n          p,','          path,\n          p,');
const deckStart=s.indexOf('  const deckLayers =');
s=s.slice(0,deckStart)+`  useEffect(()=>{
    if(intro||layers.ps_insar<=0||!relevantLayers(current).some(l=>l.id==="ps_insar")){setPs(null);return;}
    const controller=new AbortController();
    loadJSON<FeatureCollection>(path+"/ps_insar/"+dateString+".geojson",controller.signal).then(setPs).catch(e=>{if(e.name!=="AbortError")setFailure(e.message);});
    return()=>controller.abort();
  },[intro,current,path,dateString,layers.ps_insar]);
`+s.slice(deckStart);
s=s.replace('...products.flatMap((p) =>','...visibleProducts.flatMap((p) =>');
s=s.replace('image: rasterURL(current.id, p, dateString),','image: rasterURL(path, p, dateString),');
s=s.replace('opacity: layers[p],\n                transitions','opacity: compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov"?.85:layers[p],\n                transitions');
s=s.replace('(f) => f.properties?.caseId === current.id,','(f) => f.properties?.caseId === current.id && (f.properties?.siteId??current.sites?.[0].id??null)===(current.siteId??current.sites?.[0].id??null),');
s=s.replace('visible: layers[key] > 0,','visible: layers[key] > 0 && relevantLayers(current).some(l=>l.id===key),');
s=s.replace('    return [\n      ...visibleProducts',`    return [
      new ScatterplotLayer({id:"ps-insar",data:ps?.features??[],visible:layers.ps_insar>0,opacity:layers.ps_insar,getPosition:f=>f.geometry.type==="Point"?f.geometry.coordinates as [number,number]:[0,0],getRadius:4,radiusUnits:"pixels",getFillColor:f=>{const v=Number(f.properties?.velocity_mm_year??0);return v<0?[70,150,255,220]:[255,95,125,220];},pickable:true,transitions:{opacity:400}}),
      ...visibleProducts`);
s=s.replace('  }, [intro, metadata, current, dateString, layers, geo, extruded]);','  }, [intro, metadata, current, dateString, layers, geo, extruded,visibleProducts,path,ps,compare,compareKind]);');
s=s.replace('if (!intro) optical(mapRef.current, dateString, layers.optical);','if (!intro && (layers.optical>0||mapRef.current.getSource("optical"))) optical(mapRef.current, dateString, layers.optical);');
s=s.replace('          products\n            .filter((p) => layers[p] > 0)',`          (compareKind==="sentinel1"||compareKind==="alos2"?[compareKind as Product]:visibleProducts.filter(p=>layers[p]>0))`);
s=s.replace('                current.id,\n                p,','                path,\n                p,');
s=s.replace('image: rasterURL(current.id, p, current.dates[compareDate]),','image: rasterURL(path, p, current.dates[compareDate]),');
s=s.replace('opacity: layers[p],\n              });','opacity:compareKind==="sentinel1"||compareKind==="alos2"?.85:layers[p],\n              });');
s=s.replace('  }, [compare, compareDate, compareKind, current, layers, ready]);','  }, [compare, compareDate, compareKind, current, layers, ready,path,visibleProducts]);');
s=s.replace('const active = products.find((p) => layers[p] > 0),','const active = visibleProducts.find((p) => layers[p] > 0 || compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov"),');
s=s.replace('current.predictedClass','classLabel(current.predictedClass,locale)');
s=s.replace('{productLabels[active]}','{layerDefinitions.find(l=>l.id===active)?.label[locale]}');
s=s.replace('{(hover?.lat ?? current.center[0]).toFixed(4)}° N &nbsp;','{(hover?.lat ?? current.center[0]).toFixed(4)}° &nbsp;').replace('{(hover?.lng ?? current.center[1]).toFixed(4)}° E','{(hover?.lng ?? current.center[1]).toFixed(4)}°');
s=s.replace('                  " ? " +','                  " · " +');
s=s.replace('{!ready ? "Connecting to Earth" : "Loading acquisition"}','{t(!ready ? "Connecting to Earth" : "Loading acquisition")}');
s=s.replace('? "SIMULATED FIELD"\n                  : "RASTER VIEW"','? t("SIMULATED FIELD")\n                  : t("RASTER VIEW")');
s=s.replace('{meta.unit === "dB" ? "0" : "RANGE"}','{meta.unit === "dB" ? "0" : t("RANGE")}');
s=s.replace('              </span>\n            </div>\n          )}\n          {pin',`              </span>
              {active==="gcov"&&<div className="legend-thresholds"><i style={{left:((-3-meta.min)/(meta.max-meta.min)*100)+"%"}}>-3</i><i style={{left:((3-meta.min)/(meta.max-meta.min)*100)+"%"}}>+3</i><small>{t("Change threshold")} ±3 dB</small></div>}
              {active==="goff"&&<small>{t(current.phenomenon==="tailingsInstability"?"Mock dam threshold":"Large offsets")} · {current.phenomenon==="tailingsInstability"?"0.10 m":"1 m"}</small>}
            </div>
          )}
          {layers.ps_insar>0&&ps&&<div className="ps-legend glass">PS-InSAR · mm/{locale==="fr"?"an":"yr"}<span><i style={{background:"#4696ff"}}/> −250 <i style={{background:"#ff5f7d"}}/> +100</span></div>}
          {pin`);
s=s.replace('{isMock\n                  ? "Case-level simulated series. No pixel-level measurement."\n                  : "Case-level series; pixel sampling unavailable."}','{t(isMock ? "Case-level simulated series. No pixel-level measurement." : "Case-level series; pixel sampling unavailable.")}');
fs.writeFileSync("src/components/MapScene.tsx",s);
