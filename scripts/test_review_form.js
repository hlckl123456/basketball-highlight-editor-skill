// No browser available or installed for this check. This is a JS logic test,
// not visual/browser QA, and its simulated user decisions are never applied.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const page=fs.readFileSync(process.argv[2],'utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements={};let blob;
function el(tag){const e={tag,value:'',textContent:'',style:{},children:[],append(...x){this.children.push(...x)},click(){}};
Object.defineProperty(e,'id',{set(v){this._id=v;elements[v]=this},get(){return this._id}});return e}
for(const id of ['choices','download','reviewer','message']){elements[id]=el('div');elements[id].id=id}
const context={document:{getElementById:id=>elements[id],createElement:el},Blob,
 URL:{createObjectURL:b=>{blob=b;return 'blob:local-test'},revokeObjectURL(){}},JSON,Object};
vm.runInNewContext(js,context);
elements.download.onclick();assert.equal(blob,undefined);
assert.match(elements.message.textContent,/请填写/);
elements.reviewer.value='SIMULATED UI TEST; NOT A REAL USER';
for(const [id,v] of Object.entries({c0001:'keep',c0002:'reject',c0003:'keep',c0004:'reject'}))elements['decision-'+id].value=v;
elements.download.onclick();
blob.text().then(t=>{const d=JSON.parse(t);assert.equal(d.project_revision,10);assert.equal(d.player_id,'purple2');assert.deepEqual(d.decisions,{c0001:'keep',c0002:'reject',c0003:'keep',c0004:'reject'});console.log('PASS: missing-review guard, four choices, exported current revision/player/decisions; no download or project mutation performed.');});
