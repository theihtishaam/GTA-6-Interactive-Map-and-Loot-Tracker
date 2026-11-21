import test from "node:test";
import assert from "node:assert/strict";
import { missionEntries, mergeMissionReports } from "../public/missions.mjs";

const start = {id:"port-1",nameOrigin:"game",type:"pier",title:"Pilot’s Wharf",x:.3,y:.4,region:"Harbor",source:"https://atlas.example/port"};
const index = "https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/";
const row = {id:"mission-ferry",title:"The Ferry",chapter:2,kind:"story",actionLabel:"Meet Sam",
  source:"https://publisher.example/ferry",steps:["Use the in-game marker."],startVenue:"Pilot's Wharf"};
const report = {id:"c".repeat(24),category:"mission",title:"GTA VI The Ferry Walkthrough",missionName:"The Ferry",chapter:2,
  source:row.source,steps:["Visit the pier."],startingLocation:"Pier",verification:{status:"single-source"}};

test("links only unique named starting venues or supported mission positions", () => {
  const [one] = missionEntries([row],new Map(),[start]);
  assert.equal(one.x,.3);
  assert.equal(missionEntries([row],new Map(),[start,{...start,id:"port-2"}])[0].x,null);
  assert.equal(missionEntries([row],new Map(),[{...start,nameOrigin:"counterpart"}])[0].x,null);
  const verified = {x:.7,y:.2,precision:"mission-marker",sourceImage:"https://publisher.example/ferry.jpg"};
  assert.equal(missionEntries([row],new Map(),[start],{[row.id]:verified})[0].x,.7);
});

test("a newly discovered guide can fill an indexed mission and preserves the journal ID", () => {
  const bundled = missionEntries([{...row,steps:[],source:index,startVenue:null}],new Map(),[]);
  const [updated] = mergeMissionReports(bundled,[{...report,missionName:"The Ferry (Meet Sam)",x:.3,y:.4}]);
  assert.equal(updated.id,row.id);
  assert.equal(updated.source,report.source);
  assert.deepEqual(updated.steps,report.steps);
  assert.equal(updated.x,.3);
  assert.equal(bundled[0].x,null);
});

test("a retracted published start loses its waypoint, and a genuinely new mission stays distinct", () => {
  const bundled = missionEntries([row],new Map(),[start]);
  const result = mergeMissionReports(bundled,[{...report,verification:{status:"review"}},
    {...report,id:"d".repeat(24),missionName:"Northbound",source:"https://publisher.example/north",x:null,y:null}]);
  assert.equal(result.length,2);
  assert.equal(result[0].x,null);
  assert.equal(result[0].verification.status,"review");
  assert.equal(result[1].title,"Northbound");
  assert.equal(result[1].chapterName,"Chapter 2");
  assert.equal(result[1].x,null);
  assert.equal(bundled[0].x,.3);
});

test("a documented start from another publisher adds GPS to an existing walkthrough", () => {
  const bundled = missionEntries([row],new Map(),[]);
  const source = "https://community.example/ferry-start";
  const waypoint = {...report,source,x:.3,y:.4,region:"Harbor",startingLocation:"Pilot's Wharf"};
  const [updated] = mergeMissionReports(bundled,[report,waypoint]);
  assert.equal(updated.id,row.id);
  assert.deepEqual(updated.steps,row.steps);
  assert.equal(updated.source,row.source);
  assert.equal(updated.locationSource,source);
  assert.equal(updated.region,"Harbor");
  assert.equal(updated.x,.3);
  const correction = {...waypoint,x:null,y:null,verification:{status:"review"}};
  assert.equal(mergeMissionReports(bundled,[correction,waypoint])[0].x,null);
  for (const startMode of ["automatic","remote","unmarked"])
    assert.equal(mergeMissionReports([{...bundled[0],startMode}],[waypoint])[0].x,null);
});
