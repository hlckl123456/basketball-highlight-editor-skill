const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const ROOT=process.cwd(),dir=path.join(ROOT,'work/unnumbered-demo'),timing=JSON.parse(fs.readFileSync(path.join(dir,'timing-cues.json')));
const executable=process.env.CHROME_EXECUTABLE;
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:executable,args:['--autoplay-policy=no-user-gesture-required']});
const proofs=[];
for(const scene of timing.scenes.filter(s=>!process.env.DEMO_ONLY||s.id===process.env.DEMO_ONLY)){
 const ctx=await browser.newContext({viewport:{width:1600,height:900},recordVideo:{dir:path.join(dir,'raw-recordings'),size:{width:1600,height:900}}});const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const isReview=['review','decide'].includes(scene.id);let url='http://127.0.0.1:8768/'+(isReview?'case/project/review-before-confirm.html':'presentation.html?scene='+scene.id);
 await page.goto(url,{waitUntil:'load'});if(errors.length)throw Error(JSON.stringify(errors));if(!isReview){await page.evaluate(()=>window.demoReady);await page.locator('h1,h2,.big-call').first().waitFor();}
 await page.addStyleTag({content:`#demo-mouse{position:fixed;width:22px;height:22px;border:3px solid #bc6c38;border-radius:50%;pointer-events:none;z-index:99999;transform:translate(-50%,-50%);background:#fff9;box-shadow:0 1px 8px #0002;left:1550px;top:60px}`});
 await page.evaluate(()=>{let d=document.createElement('div');d.id='demo-mouse';document.body.append(d);window.addEventListener('mousemove',e=>{d.style.left=e.clientX+'px';d.style.top=e.clientY+'px'})});
 if(!isReview)await page.locator('#demo-mouse').evaluate(e=>e.remove());
 const move=async(loc)=>{const b=await loc.boundingBox();if(b)await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:20})};
 if(isReview){
  await page.addStyleTag({content:'body{font-size:22px;padding-bottom:280px}select,input,button{font-size:22px}article video{width:780px}article pre{font-size:15px}'});
  await page.evaluate(()=>{let n=document.createElement('div');n.id='recording-note';n.textContent='录屏标注 · 公园无号码案例 · test_operator';Object.assign(n.style,{position:'fixed',top:'14px',right:'18px',font:'16px system-ui',color:'#315d43',padding:'9px 14px',background:'#e5efdf',border:'1px solid #cedbc4',borderRadius:'16px',zIndex:9999});document.body.append(n)});
 }
 if(scene.id==='review'){
  await page.locator('article').nth(0).evaluate(e=>e.scrollIntoView({block:'start'}));await page.locator('article').nth(0).locator('video').evaluate(async v=>{v.muted=true;v.loop=true;await v.play()});
 }else if(scene.id==='decide'){
  await page.locator('#choices').evaluate(e=>e.parentElement.scrollIntoView({block:'center'}));
 }
 await page.waitForTimeout(500);const start=Date.now(),duration=scene.duration*1000;
 const until=async(ms)=>{const rest=start+ms-Date.now();if(rest>0)await page.waitForTimeout(rest)};
 if(scene.id==='review'){
  await until(5500);await page.locator('article').nth(0).locator('video').evaluate(v=>v.pause());await page.locator('article').nth(2).evaluate(e=>e.scrollIntoView({block:'start',behavior:'smooth'}));await page.waitForTimeout(500);await page.locator('article').nth(2).locator('video').evaluate(async v=>{v.muted=true;v.loop=true;await v.play()});
 }else if(scene.id==='decide'){
  const reviewer=page.locator('#reviewer');await move(reviewer);await reviewer.fill('test_operator 演示');await until(1300);
  for(const [i,[id,value]] of Object.entries([['c0001','keep'],['c0002','keep'],['c0003','keep'],['c0004','keep'],['c0005','keep'],['c0006','reject'],['c0007','reject'],['c0008','reject']])){
   const loc=page.locator('#decision-'+id);await move(loc);await loc.selectOption(value);await loc.press('Tab');if(await loc.inputValue()!==value)throw Error('Decision mismatch '+id);await until(1500+Number(i)*900);
  }
  await page.locator('#reviewer').evaluate(e=>e.blur());
  proofs.push({scene:scene.id,decisions:await page.locator('#choices select').evaluateAll(ss=>ss.map(s=>({id:s.id,value:s.value}))),user_confirmation_submitted:false});
 }
 if(scene.id==='result')await page.locator('video').evaluate(async v=>{v.currentTime=0;await v.play()});
 await until(Math.min(duration-700,Math.max(850,duration*.65)));await page.screenshot({path:path.join(dir,'captures',scene.id+'.png')});
 if(!isReview)proofs.push({scene:scene.id,title:await page.title(),heading:await page.locator('h1,h2,.big-call').first().textContent()});
 await until(duration);const video=page.video();await page.close();await video.saveAs(path.join(dir,'captures',scene.id+'.webm'));await ctx.close();
 proofs.push({scene:scene.id,url,title:isReview?'篮球候选复核':'篮球集锦 Skill · 使用演示',errors,recording:path.relative(ROOT,path.join(dir,'captures',scene.id+'.webm'))});console.log('Recorded',scene.id,scene.duration,'errors',errors.length);
 if(errors.length)throw Error(JSON.stringify(errors));
}
await browser.close();fs.writeFileSync(path.join(dir,process.env.DEMO_ONLY?'capture-proof-'+process.env.DEMO_ONLY+'.json':'capture-proof.json'),JSON.stringify({browserPlugin:'not available; used existing Playwright and Chrome in isolated local context',viewport:[1600,900],actualReviewPage:true,proofs},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
