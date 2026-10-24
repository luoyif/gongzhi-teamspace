/** Date-only scheduling rules: work spans today through deadline, not afterward. */
export function dateKeyInZone(time=new Date(),zone='Asia/Shanghai'){
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(time);
 const get=name=>parts.find(p=>p.type===name)?.value;
 return get('year')+'-'+get('month')+'-'+get('day');
}
export const isoDay=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}/.test(value)?value.slice(0,10):'';
export function eventDay(value,zone='Asia/Shanghai'){
 if(!value||typeof value!=='string')return '';
 if(/^\d{4}-\d{2}-\d{2}$/.test(value))return value;
 const time=new Date(value);
 return Number.isNaN(time.valueOf())?'':dateKeyInZone(time,zone);
}
export function scheduleAt(item,day,today,zone='Asia/Shanghai'){
 const kind=item.kind;
 if(kind==='task'){
  if(!item.due_date&&!item.starts_at)return null;
  if(['cancelled','paused'].includes(item.status))return null;
  const due=isoDay(item.due_date||item.starts_at);
  if(!due)return null;
  if(item.status==='doing'&&due>=today&&day>=today&&day<=due)
   return {label:item.title,style:day===due?'deadline':'ongoing',due};
  if(day===due){
   const late=due<today&&!['done','cancelled','paused'].includes(item.status);
   return {label:item.title,style:late?'overdue':item.status==='done'?'completed':item.status==='review'?'review':'deadline',due};
  }
  return null;
 }
 if(item.status==='cancelled')return null;
 const start=eventDay(item.starts_at,zone);
 const end=eventDay(item.ends_at,zone)||start;
 // Inclusive multi-day display, with elapsed days visually dimmed.
 if(!start||day<start||day>(end>=start?end:start))return null;
 return {label:item.title,style:day<today?'past':'event',due:end};
}
export function entriesOnDay(items,day,today,zoneFor=()=> 'Asia/Shanghai'){
 return items.flatMap(item=>{
  const zone=zoneFor(item);
  const match=scheduleAt(item,day,typeof today==='function'?today(item):today,zone);
  return match?[{...item,...match}]:[];
 }).sort((a,b)=>(a.style==='ongoing'?0:a.style==='deadline'?1:2)-(b.style==='ongoing'?0:b.style==='deadline'?1:2));
}
export function agendaFrom(items,today,zoneFor=()=> 'Asia/Shanghai'){
 const future=[],overdue=[];
 for(const item of items){
  const zone=zoneFor(item);
  const current=typeof today==='function'?today(item):today;
  if(item.kind==='task'){
   const due=isoDay(item.due_date||item.starts_at);
   if(!due||['cancelled','paused','done'].includes(item.status))continue;
   const row={...item,sortDate:due};
   if(due<current)overdue.push(row);else future.push(row);
  }else{
   if(item.status==='cancelled')continue;
   const start=eventDay(item.starts_at,zone),end=eventDay(item.ends_at,zone)||start;
   if(end<current)continue;
   future.push({...item,sortDate:start<current?current:start});
  }
 }
 future.sort((a,b)=>a.sortDate.localeCompare(b.sortDate));
 overdue.sort((a,b)=>b.sortDate.localeCompare(a.sortDate));
 return {future:future.slice(0,30),overdue:overdue.slice(0,12)};
}
