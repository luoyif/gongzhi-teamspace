// Presentation-only helpers. Authorization and persistence stay in existing APIs.
export const PRESET_AVATARS={human:['🙂','🦊','🐼','🐱','🐻','🐨','🐯','🦉','🐸','🐧','🐰','🦁'],agent:['🤖','💻','🎨','🔬','📄','🧪','🧠','🛰️']};
export function messageSide(message,currentUserId){return message.kind==='human'&&Number(message.author_id)===Number(currentUserId)?'self':message.kind==='assistant'?'agent':'peer';}
export function defaultAvatarIndex(kind,id){let n=2166136261;for(const ch of kind+':'+id){n^=ch.codePointAt(0);n=Math.imul(n,16777619);}return (n>>>0)%PRESET_AVATARS[kind].length;}
export function avatarNode(kind,id,name,profile=null){
 const node=document.createElement('span');node.className='avatar persona-avatar '+(kind==='agent'?'ai persona-ai':'persona-human');node.dataset.avatarKind=kind;node.dataset.avatarId=String(id);node.setAttribute('role','img');node.setAttribute('aria-label',(kind==='agent'?'AI员工：':'成员：')+name);updateAvatar(node,profile);return node;
}
export function updateAvatar(node,profile){
 const kind=node.dataset.avatarKind;const i=profile?.preset??defaultAvatarIndex(kind,node.dataset.avatarId);node.dataset.preset=String(i%6);
 if(profile?.image_data&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(profile.image_data)&&profile.image_data.length<150000){const image=document.createElement('img');image.src=profile.image_data;image.alt=node.getAttribute('aria-label');node.replaceChildren(image);}
 else node.textContent=profile?.emoji||PRESET_AVATARS[kind][i]||PRESET_AVATARS[kind][0];
}
