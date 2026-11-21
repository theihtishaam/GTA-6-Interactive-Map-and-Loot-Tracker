import assert from "node:assert/strict";
import { exportRows, fieldPack } from "../public/export-center.mjs";
const row = {id:"personal-a",title:'<draft> & "reward"',category:"bounty",region:"Vice City",x:.5,y:.5,confidence:"personal",details:"My field notes",source:"javascript:alert(1)",steps:["Inspect <door>"]};
const pending = {id:"lead",category:"bounty",title:"Unplaced",confidence:"lead",x:null,y:null};
const data = {catalog:[row,pending],filtered:[pending],entry:row,done:new Set(["personal-a"]),route:{origin:{x:.1,y:.2,label:"Private start"},stops:[{x:.5,y:.5,label:"Stop one"}]},track:[],directions:{cues:[]},meta:{width:3456,height:4864,coordinateFrame:{minX:-10240,maxX:3584,minY:-8960,maxY:10496},source:"https://map.gtadb.org",licenseUrl:"https://creativecommons.org/licenses/by/4.0/",license:"CC BY 4.0",attribution:"GTADB and contributors"}};
assert.deepEqual(exportRows("entry",data),[row]);
assert.deepEqual(exportRows("bounty",data),[row,pending]);
assert.deepEqual(exportRows("done",data),[row]);
assert.deepEqual(exportRows("filtered",data),[pending]);
const card = fieldPack([row], data, "data:image/webp;base64,QUJD", false, "2026-11-21");
assert.match(card,/GTA 6 field card/);
assert.match(card,/&lt;draft&gt;/);
assert.match(card,/Inspect &lt;door&gt;/);
assert.match(card,/265 167"/);
assert.doesNotMatch(card,/Private start|javascript:alert|<draft>/);
assert.match(fieldPack([row],data,"data:image/webp;base64,QUJD",true,"today"),/Private start/);
assert.throws(()=>fieldPack([row],data,"https://example.com/image",false,"today"));
console.log("Field card scopes, local map, private route exclusion and escaped output passed.");

