import fs from "node:fs";
import path from "node:path";
const file="public/data/cases.json";
if(fs.existsSync(file)){
 const cases=JSON.parse(fs.readFileSync(file,"utf8"));
 for(const c of cases){c.media={timelapse:fs.existsSync(path.join("public/data",c.id,"timelapse.mp4"))};for(const site of c.sites??[])site.media={timelapse:fs.existsSync(path.join("public/data",site.dataPath,"timelapse.mp4"))};}
 fs.writeFileSync(file,JSON.stringify(cases,null,2));
 console.log("Indexed optional pipeline timelapse.mp4 assets.");
}
