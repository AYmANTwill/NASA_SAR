import fs from "node:fs";
import ts from "typescript";
const dictionary=ts.createSourceFile("i18n.ts",fs.readFileSync("src/lib/i18n.ts","utf8"),ts.ScriptTarget.Latest,true);
const keys=new Set();
function gather(node){if(ts.isPropertyAssignment(node)&&ts.isStringLiteral(node.name))keys.add(node.name.text);ts.forEachChild(node,gather);}gather(dictionary);
for(const file of ["src/App.tsx","src/components/MapScene.tsx","src/features/dashboard/Dashboard.tsx"]){
 let source=fs.readFileSync(file,"utf8");
 if(file.endsWith("Dashboard.tsx")){source='import { useI18n } from "../../lib/i18n";\n'+source;source=source.replace('const { set, sheet } = useStore();','const { set, sheet } = useStore();\n  const {t}=useI18n();');}
 const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),edits=[];
 function visit(node){
 if(ts.isJsxText(node)){const text=node.getText(tree).trim();if(keys.has(text))edits.push({start:node.pos,end:node.end,value:"{t("+JSON.stringify(text)+")}"});}
 if(ts.isJsxAttribute(node)&&["aria-label","title","placeholder"].includes(node.name.getText(tree))&&node.initializer&&ts.isStringLiteral(node.initializer)&&keys.has(node.initializer.text))edits.push({start:node.initializer.getStart(tree),end:node.initializer.end,value:"{t("+JSON.stringify(node.initializer.text)+")}"});
 ts.forEachChild(node,visit);
 }
 visit(tree);for(const e of edits.sort((a,b)=>b.start-a.start))source=source.slice(0,e.start)+e.value+source.slice(e.end);
 fs.writeFileSync(file,source);
}
