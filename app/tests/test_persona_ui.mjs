import test from 'node:test';
import assert from 'node:assert/strict';
import {messageSide,defaultAvatarIndex,PRESET_AVATARS} from '../web/persona-ui.mjs';
test('self human messages align right by ID, not display name',()=>{assert.equal(messageSide({kind:'human',author_id:7},'7'),'self');assert.equal(messageSide({kind:'human',author_id:8,author_name:'same'},7),'peer');});
test('AI identity is never confused with current human',()=>assert.equal(messageSide({kind:'assistant',author_id:7},7),'agent'));
test('preset assignment is stable across page renders',()=>assert.equal(defaultAvatarIndex('human','42'),defaultAvatarIndex('human','42')));
test('human and employee sets remain distinct',()=>{assert.equal(PRESET_AVATARS.human.length,12);assert.equal(PRESET_AVATARS.agent.length,8);assert.equal(PRESET_AVATARS.human.some(x=>PRESET_AVATARS.agent.includes(x)),false);});
test('assigned indices remain within preset range and diverse',()=>{const values=Array.from({length:40},(_,i)=>defaultAvatarIndex('human',String(i)));assert(values.every(x=>x>=0&&x<12));assert(new Set(values).size>6);});
