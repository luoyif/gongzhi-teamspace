import test from 'node:test';
import assert from 'node:assert/strict';
import {evidenceGraphProjection,EVIDENCE_TYPE_LABELS} from '../web/knowledge-flow-layout.mjs';

const sample = {
 nodes:[
  {id:'task:t1',type:'task',title:'研究'},
  {id:'message:m1',type:'message',seq:1,speaker:'人'},
  {id:'run:r1',type:'run',created_at:'2026-10-25'},
  {id:'review_step:s1',type:'review_step',approved_by:1,approval_recorded:true},
  {id:'document:d1',type:'document',adopted:true},
  {id:'published_knowledge:k1',type:'published_knowledge',source_state:'explicitly_published_snapshot'}
 ],
 edges:[
  {from:'task:t1',to:'message:m1',relation:'contains_message'},
  {from:'message:m1',to:'run:r1',relation:'triggered_run'},
  {from:'run:r1',to:'review_step:s1',relation:'run_reviewed_in_step'},
  {from:'document:d1',to:'published_knowledge:k1',relation:'explicit_company_publication'}
 ]
};

test('stable six-column visual projection reflects only real rows',()=>{
 const a=evidenceGraphProjection(sample),b=evidenceGraphProjection(sample);
 assert.deepEqual(a,b);
 assert.equal(a.nodes.length,6);
 assert.equal(a.edges.length,4);
 assert.equal(a.partial,false);
 assert.ok(a.width>400);
 assert.ok(a.nodes.every(n=>Number.isFinite(n.layout_x)&&Number.isFinite(n.layout_y)));
});
test('missing, unauthorised or filtered endpoints never invent or render links',()=>{
 const graph={nodes:sample.nodes.filter(x=>x.id!=='document:d1'),edges:[
  ...sample.edges,{from:'private:p2',to:'task:t1',relation:'unauthorised'}]};
 const p=evidenceGraphProjection(graph);
 assert.equal(p.edges.length,3);
 assert.equal(p.edges.some(x=>x.relation==='unauthorised'),false);
 assert.equal(p.edges.some(x=>x.from==='document:d1'),false);
});
test('dedupe identical relations without merging semantically distinct evidence',()=>{
 const g={...sample,edges:[...sample.edges,sample.edges[0],{...sample.edges[0],relation:'different_recorded_relation'}]};
 const p=evidenceGraphProjection(g);
 assert.equal(p.edges.length,5);
});
test('history older than visual bounds marks partial, does not silently imply completeness',()=>{
 const nodes=Array.from({length:91},(_,i)=>({
  id:'message:m'+i,type:'message',seq:i+1
 }));
 const p=evidenceGraphProjection({nodes,edges:[],partial:false,counts:{messages:91}});
 assert.equal(p.nodes.length,7);
 assert.equal(p.displayCounts.message.total,91);
 assert.equal(p.partial,true);
 assert.equal(p.nodes[0].seq,91);
});
test('review and source filters do not produce phantom edges',()=>{
 const review=evidenceGraphProjection(sample,{filter:'reviewed'});
 const origin=evidenceGraphProjection(sample,{filter:'origin'});
 assert.equal(review.nodes.some(x=>x.type==='run'),false);
 assert.equal(origin.nodes.some(x=>x.type==='published_knowledge'),false);
 assert.ok(review.edges.every(e=>review.nodes.some(n=>n.id===e.from) && review.nodes.some(n=>n.id===e.to)));
});
test('restricted company publication does not require or surface absent source project',()=>{
 const g={nodes:[
  {id:'workspace:w1',type:'workspace'},
  {id:'published_knowledge:k2',type:'published_knowledge',title:'Public snapshot',source_visibility:'restricted'}
 ],edges:[{from:'workspace:w1',to:'published_knowledge:k2',relation:'workspace_published_snapshot'}]};
 const p=evidenceGraphProjection(g);
 assert.equal(p.nodes.length,2);
 assert.equal(p.edges.length,1);
 assert.ok(!JSON.stringify(p).includes('source_document_id'));
});
test('bad input fails closed and labels remain semantic',()=>{
 assert.throws(()=>evidenceGraphProjection({nodes:null,edges:[]}),TypeError);
 assert.throws(()=>evidenceGraphProjection(sample,{filter:'execute'}),TypeError);
 assert.equal(EVIDENCE_TYPE_LABELS.review_step,'人工核验');
});
