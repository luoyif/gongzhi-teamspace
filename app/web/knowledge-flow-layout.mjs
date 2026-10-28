/**
 * Evidence graph layout and selection. No network, no inferred edges or
 * synthetic approvals. Used by the visual graph and tested in Node.
 */
export const EVIDENCE_TYPE_LABELS=Object.freeze({
  workspace:'公司',project:'项目',task:'任务',message:'讨论消息',
  run:'AI 执行',tool_event:'工具事件',source_upload:'原始上传',
  document:'项目资料',review_step:'人工核验',handoff:'员工接力',
  published_knowledge:'团队共享知识'
});
const TYPE_LAYERS=Object.freeze({
  workspace:0,task:0,project:1,message:1,run:2,source_upload:2,
  tool_event:3,handoff:3,review_step:4,document:5,published_knowledge:6
});
const LIMITS=Object.freeze({
  workspace:1,task:5,project:7,message:7,run:7,tool_event:6,
  source_upload:6,handoff:6,review_step:7,document:7,published_knowledge:10
});
const APPROVED=new Set(['workspace','project','task','document','review_step','published_knowledge']);
const ORIGINS=new Set(['workspace','project','task','message','source_upload','run','tool_event','document']);

export function evidenceGraphProjection(graph,{filter='all'}={}){
  if(!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges))throw new TypeError('Invalid graph');
  if(!['all','origin','reviewed'].includes(filter))throw new TypeError('Unsupported graph filter');
  const whitelist=filter==='origin'?ORIGINS:filter==='reviewed'?APPROVED:null;
  const selected=new Map(),byType=new Map(),displayCounts={};
  for(const node of graph.nodes){
    if(!node || typeof node.id!=='string' || typeof node.type!=='string')continue;
    if(whitelist && !whitelist.has(node.type))continue;
    if(filter==='reviewed' && node.type==='review_step' && !node.approval_recorded)continue;
    if(filter==='reviewed' && node.type==='document' && node.adopted===false)continue;
    const collection=byType.get(node.type)||[];
    collection.push(node);
    byType.set(node.type,collection);
  }
  const visualTypes=[...byType.keys()].sort((a,b)=>(TYPE_LAYERS[a]??10)-(TYPE_LAYERS[b]??10) || a.localeCompare(b));
  for(const type of visualTypes){
    const rows=byType.get(type)||[];
    const sorted=[...rows].sort((a,b)=>{
      if(type==='message')return (b.seq||0)-(a.seq||0);
      if(type==='review_step')return (a.ordinal||0)-(b.ordinal||0);
      if(type==='run')return String(b.created_at||'').localeCompare(String(a.created_at||''));
      return String(a.title||a.id).localeCompare(String(b.title||b.id),'zh-CN');
    });
    const limited=sorted.slice(0,LIMITS[type]??5);
    for(const item of limited)selected.set(item.id,item);
    displayCounts[type]={total:rows.length,visible:limited.length};
  }
  const orderedTypes=[...new Set([...selected.values()].map(x=>x.type))].sort(
    (a,b)=>(TYPE_LAYERS[a]??10)-(TYPE_LAYERS[b]??10) || a.localeCompare(b)
  );
  const nodes=[];
  const column=196;
  for(let col=0;col<orderedTypes.length;col++){
    const type=orderedTypes[col];
    const group=[...selected.values()].filter(n=>n.type===type);
    for(let i=0;i<group.length;i++){
      nodes.push({...group[i],layout_x:44+col*column,layout_y:88+i*82,
       layout_col:col,layout_row:i});
    }
  }
  const ids=new Set(nodes.map(n=>n.id)),edgeKeys=new Set();
  const edges=graph.edges.filter(e=>{
    if(!e || !ids.has(e.from)||!ids.has(e.to)||typeof e.relation!=='string')return false;
    const key=e.from+'\0'+e.to+'\0'+e.relation;
    if(edgeKeys.has(key))return false;
    edgeKeys.add(key);
    return true;
  }).map(e=>({from:e.from,to:e.to,relation:e.relation}));
  const maxRows=Math.max(1,...orderedTypes.map(type=>nodes.filter(n=>n.type===type).length));
  return {
    nodes,edges,types:orderedTypes,displayCounts,
    width:Math.max(420,88+orderedTypes.length*column),
    height:Math.max(220,144+maxRows*82),
    partial:Boolean(graph.partial)||Object.values(displayCounts).some(x=>x.visible<x.total),
    totalNodes:graph.nodes.length,totalEdges:graph.edges.length,
  };
}
