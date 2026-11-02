"""Build web/index.html: the live app. Explore mode (click anywhere / search a city) -> calls the
Journey API -> fills the studio template with the live result and plays it.
Usage: python tools/build_web.py API_URL AMAZON_LOCATION_KEY [region]"""
import json, re, sys, pathlib
API, KEY = sys.argv[1].rstrip("/"), sys.argv[2]; REGION = sys.argv[3] if len(sys.argv) > 3 else "us-east-1"
STYLE = f"https://maps.geo.{REGION}.amazonaws.com/v2/styles/Hybrid/descriptor?key={KEY}"
src = pathlib.Path("gate/05_studio.py").read_text()
T = re.search(r'html = r"""(.*?)"""\n', src, re.S).group(1)
T = T.replace("__STYLE__", STYLE).replace('onclick="location.reload()"', 'onclick="location.href=location.pathname"')
page = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Biography of a Breath</title>
<meta name=description content="Click anywhere on Earth and rewind the last 72 hours of the air arriving there, through live NOAA winds.">
<link href="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.css" rel=stylesheet>
<script src="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500&family=Inter:wght@400;600&display=swap" rel=stylesheet>
<style>body{margin:0;background:#050912;color:#eef3ff;font:14px Inter,system-ui;overflow:hidden}#map{position:absolute;inset:0}
.maplibregl-ctrl-bottom-right .maplibregl-ctrl-attrib{margin:0 6px 6px 0;opacity:.55;transform:scale(.85);transform-origin:bottom right}.maplibregl-ctrl-attrib.maplibregl-compact{min-height:20px;background:rgba(8,14,32,.5)!important;color:#cfdaf3}.maplibregl-ctrl-attrib.maplibregl-compact a{color:#cfdaf3}
.glass{background:rgba(8,14,32,.62);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.08);border-radius:16px}
#hero{position:absolute;left:20px;top:18px;padding:18px 20px;width:min(420px,calc(100vw - 40px))}
#hero h1{font:500 28px Fraunces,serif;margin:0 0 6px}#hero p{margin:0 0 12px;color:#9fb0d0;line-height:1.45}
input{width:100%;box-sizing:border-box;font:inherit;padding:11px 13px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.06);color:#eef3ff}
#res div{padding:8px 10px;border-radius:8px;cursor:pointer}#res div:hover{background:rgba(143,227,255,.12)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.stories{display:grid;gap:6px;margin-top:12px}.stories .lbl{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#9fb0d0}
.chip.story{display:block;border-radius:12px;padding:8px 11px;font-size:13px;background:rgba(255,179,143,.1);border:1px solid rgba(255,179,143,.22)}.chip.story small{display:block;color:#9fb0d0;font-size:11px;margin-top:1px}
.chip.story:hover{background:rgba(255,179,143,.18)}.tag{margin:12px 0 0!important;font-size:12px;color:#ffcf9f!important}
@media(max-width:700px){#hero{left:10px;top:10px;width:calc(100vw - 20px);padding:12px 14px;max-height:52vh;overflow:auto}#hero h1{font-size:20px}#hero p{font-size:12.5px;margin-bottom:8px}
 .chips{display:none}#hero.mini>*:not(h1){display:none}#hero.mini h1{margin:0;font-size:16px}#hero.mini h1:after{content:' ⌄';color:#9fb0d0}.chip.story{padding:6px 10px;font-size:12px}#pick{bottom:10px;width:calc(100% - 20px)}#pick b{font-size:16px}#load{font-size:18px;padding:0 20px}}.chip{padding:6px 10px;border-radius:999px;background:rgba(143,227,255,.12);cursor:pointer;font-size:12px}
.row{display:flex;gap:8px;align-items:center;margin-top:10px;color:#9fb0d0;font-size:12px}.row.dir{flex-direction:column;align-items:flex-start;gap:6px;font-size:13px;color:#eef3ff}
#load{position:absolute;inset:0;display:none;place-items:center;background:rgba(5,9,18,.6);font:500 24px Fraunces,serif;text-align:center}
#load small{display:block;font:400 14px Inter;color:#9fb0d0;margin-top:8px}
#pick{position:absolute;left:50%;bottom:28px;transform:translate(-50%,20px);padding:14px 18px;display:flex;gap:16px;align-items:center;opacity:0;pointer-events:none;transition:all .4s}
#pick.on{opacity:1;transform:translate(-50%,0);pointer-events:auto}#pick b{font:500 18px Fraunces,serif}#pick small{display:block;color:#9fb0d0}
#pick{flex-direction:column;align-items:stretch;gap:12px;max-width:560px;width:calc(100% - 32px)}
#pick .pk_btns{display:flex;gap:10px}#pick button{flex:1;font:600 15px Inter;padding:12px 16px;border-radius:16px;border:0;background:linear-gradient(135deg,#8fe3ff,#b7a6ff);color:#061023;cursor:pointer;text-align:center}
#pick button small{display:block;font:500 11px Inter;color:#22304f;margin-top:2px}#pick #pk_fwd{background:linear-gradient(135deg,#ffd38f,#ff9fb7)}
#pk_here{margin-top:8px;font-size:13px;color:#dfe8ff;padding:8px 10px;border-radius:10px;background:rgba(143,227,255,.08);border:1px solid rgba(143,227,255,.18)}
@media(max-width:600px){#pick .pk_btns{flex-direction:column}}
.pin{width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 0 0 6px rgba(143,227,255,.35),0 0 28px #8fe3ff;animation:pp 1.6s ease-in-out infinite}
@keyframes pp{50%{box-shadow:0 0 0 12px rgba(143,227,255,.12),0 0 34px #8fe3ff}}#wind{position:absolute;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:1}#windcap{position:absolute;right:44px;bottom:12px;font-size:11px;color:#9fb0d0;opacity:.75;z-index:2}
#hero{z-index:3;box-sizing:border-box}#hero *{box-sizing:border-box}#pick,#load{z-index:6}
#hero .lead{font-size:15px;color:#cfdaf3;line-height:1.5;margin:0 0 14px}
#me{width:100%;font:600 16px Inter;padding:14px 16px;border-radius:14px;border:0;cursor:pointer;color:#061023;background:linear-gradient(135deg,#8fe3ff,#b7a6ff);box-shadow:0 8px 30px rgba(143,227,255,.25);margin-bottom:10px}
#me:hover{filter:brightness(1.08)}
.try{font-size:12.5px;color:#9fb0d0;margin:10px 0 0!important}.try a.chip{display:inline;background:none;padding:0;color:#ffcf9f;text-decoration:underline;text-decoration-color:rgba(255,207,159,.4);cursor:pointer;font-size:12.5px;border-radius:0}
details.opts{margin-top:10px;font-size:12px;color:#9fb0d0}details.opts summary{cursor:pointer;list-style:none}details.opts summary::-webkit-details-marker{display:none}
#guide{position:absolute;left:0;top:0;z-index:4;transition:transform 1.4s cubic-bezier(.2,.7,.2,1),opacity .6s;pointer-events:none;opacity:0}#guide.on{opacity:1}
.gbub{position:absolute;left:92px;top:6px;width:max-content;max-width:250px;background:#fff;color:#14203b;padding:9px 13px;border-radius:16px 16px 16px 4px;font:500 13px/1.4 Inter;box-shadow:0 8px 30px rgba(0,0,0,.35)}
#intro{position:fixed;inset:0;z-index:20;background:#03060d;display:grid;place-items:center;align-content:center;gap:26px;cursor:pointer;transition:opacity 1.4s}#intro.gone{opacity:0;pointer-events:none}
#intro .breath{width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,#e8fbff 0,#8fe3ff 38%,rgba(143,227,255,0) 70%);animation:breathe 4s ease-in-out infinite}
#intro p{font:500 30px Fraunces,serif;color:#eef3ff;margin:0;text-align:center;padding:0 24px;transition:opacity .7s;min-height:1.3em}#intro small{color:#5d6b88;font-size:11px}
@keyframes breathe{0%,100%{transform:scale(.55);opacity:.5}50%{transform:scale(1.3);opacity:1}}
@media(max-width:700px){#guide{display:none}#windcap{right:40px;bottom:8px}#hero .lead{font-size:13px}#me{font-size:15px;padding:12px}#intro p{font-size:22px}}
.puff{position:relative;width:96px;height:96px;pointer-events:none;filter:drop-shadow(0 0 16px rgba(143,227,255,.8))}
.puff svg{width:96px;height:96px;animation:bob 1.8s ease-in-out infinite}
.puff .trail{fill:none;stroke:#eafaff;stroke-linecap:round;stroke-dasharray:30 12;animation:flow .7s linear infinite;opacity:.85}
.puff .trail.t2{animation-duration:.42s;opacity:.7}
.puff .trail.t3{animation-duration:.66s;opacity:.55}
.puff .body{animation:sway 1.4s ease-in-out infinite;transform-origin:48px 30px}
.puff .curl{fill:none;stroke:#ffffff;stroke-width:3;stroke-linecap:round;animation:curl 1.2s ease-in-out infinite;transform-origin:48px 30px}
.puff .eye{animation:blink 4.2s infinite;transform-origin:center;transform-box:fill-box}
.puff.cold svg{animation:bob 2.4s ease-in-out infinite,shiver .18s linear infinite}
.puff.cold .body{fill:#d9efff}
.puff.hot .body{fill:#fff1d6}
.puff.hot .cheek{opacity:.9}
.puff.night .eye{transform:scaleY(.35)}
.puff .drops{opacity:0;transition:opacity .4s}
.puff.rain .drops{opacity:1}
.puff .drops line{stroke:#9fd0ff;stroke-width:2;stroke-linecap:round;animation:fall .7s linear infinite}
.puff.talk .mouth{animation:talk .22s ease-in-out infinite alternate}
.puff .mouth{transform-origin:center;transform-box:fill-box}
@keyframes flow{to{stroke-dashoffset:-42}}@keyframes sway{50%{transform:skewX(-6deg)}}@keyframes curl{50%{transform:rotate(-14deg)}}@keyframes bob{50%{transform:translateY(-5px)}}@keyframes blink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}@keyframes fall{from{transform:translateY(-4px);opacity:1}to{transform:translateY(10px);opacity:0}}
</style></head><body>
<div id=map></div>
<canvas id=wind></canvas><div id=windcap></div>
<div id=hero class=glass><h1>Biography of a Breath</h1>
<p class=lead>Every breath has a past and a future.<br>Find out where yours has been, and who breathes it next.</p>
<button id=me>📍 Trace the air I'm breathing</button>
<input id=q placeholder="…or search any place on Earth" autocomplete=off><div id=res></div>
<p class=try>or try: <a class=chip data-c="30.9010,75.8573,Ludhiana">Ludhiana in stubble season</a> · <a class=chip data-c="13.0827,80.2707,Chennai">Chennai's rain</a> · <a class=chip data-c="-8.7612,-63.9004,Porto Velho">the Amazon</a></p>
<details class=opts><summary>⚙ options</summary><div class=row><label><input type=radio name=lev value=850 checked style="width:auto"> air ~1.5 km up</label><label><input type=radio name=lev value=10 style="width:auto"> at ground level</label></div>
<div class=chips><span class=chip data-c="51.5074,-0.1278,London">London</span><span class=chip data-c="6.5244,3.3792,Lagos">Lagos</span><span class=chip data-c="40.7128,-74.006,New York">New York</span><span class=chip data-c="-33.8688,151.2093,Sydney">Sydney</span></div></details></div>
<div id=guide class=puff><svg viewBox="0 0 96 96">
   <path class="trail" stroke-width="3.2" d="M2 56 C16 58 26 50 23 41 C21 35 13 36 15 42"/>
   <path class="trail t2" stroke-width="3" d="M94 46 C80 44 70 52 73 61 C75 67 83 66 81 60"/>
   <path class="trail t3" stroke-width="2.4" d="M4 76 C18 80 30 76 34 70"/><path class="trail t2" stroke-width="2.4" d="M92 82 C80 84 70 80 66 74"/>
   <g class=drops><line x1=38 y1=74 x2=36 y2=80 /><line x1=50 y1=84 x2=48 y2=90 style="animation-delay:.25s"/><line x1=60 y1=72 x2=58 y2=78 style="animation-delay:.5s"/></g>
   <path class=body fill="#ffffff" d="M48 16 C61 16 67 27 67 36 C67 48 57 56 52 66 C48 74 51 84 60 88 C46 90 38 80 41 68 C33 59 29 48 29 36 C29 26 36 16 48 16 Z"/>
   <ellipse class=eye cx=41.5 cy=35 rx=3 ry=4.2 fill="#14203b"/><ellipse class=eye cx=54.5 cy=35 rx=3 ry=4.2 fill="#14203b"/>
   <circle cx=42.6 cy=33.6 r=1.1 fill="#fff"/><circle cx=55.6 cy=33.6 r=1.1 fill="#fff"/>
   <ellipse class=cheek cx=36 cy=41 rx=3.2 ry=1.9 fill="#ff9fb0" opacity=".45"/><ellipse class=cheek cx=60 cy=41 rx=3.2 ry=1.9 fill="#ff9fb0" opacity=".45"/>
   <ellipse class=mouth cx=48 cy=43 rx=2.8 ry=1.3 fill="#14203b"/></svg><div class=bubble></div><div class=gbub>Click anywhere on Earth.<br>I'll tell you where your air has been.</div></div>
<div id=intro><div class=breath></div><p id=intro_t>Breathe in…</p><small>tap to skip</small></div>
<div id=pick class=glass><div class=pk_top><b id=pk_name>Here</b><small id=pk_xy></small><div id=pk_here>Checking the forecast here…</div></div>
<div class=pk_btns><button id=pk_go>Release Puff<small>where this air came from · where it goes next</small></button></div></div><div id=load><div>Tracing 72 hours back and 72 hours ahead…<small>NOAA GFS · Overture Maps · Natural Earth</small></div></div>
<script>
(()=>{   // loader lives in its own scope so nothing leaks into the journey page it writes
const API='__API__', KEY='__KEY__', REGION='__REGION__', TEMPLATE=__TEMPLATE__;
const Q=new URLSearchParams(location.search);
let PIN=null,SEL=null;
function go(lat,lon,name){const lev=document.querySelector('input[name=lev]:checked').value;location.search=new URLSearchParams({lat:lat.toFixed(4),lon:lon.toFixed(4),level:lev,...(name?{name}:{})})}
async function playJourney(){document.getElementById('load').style.display='grid';
 let J;try{const r=await fetch(`${API}/?${Q}`);J=await r.json();if(!r.ok)throw new Error(J.error||r.status)}catch(e){document.getElementById('load').innerHTML=`<div>Couldn't rewind this breath.<small>${e.message} — <a style="color:#8fe3ff" href="${location.pathname}">try another place</a></small></div>`;return}
 const rep={__NAME__:J.name,__ARR__:J.arrival_utc.slice(0,16).replace('T',' ')+' UTC',__HRS__:String(Math.round(J.points[0].hours_ago)),
  __LEVEL__:J.level.startsWith('10')?'air at ground level':'air ~1.5 km up',__KM__:Math.round(J.total_km).toLocaleString(),__NSTOPS__:String(J.places.length),['__'+'API__']:API};
 let h=TEMPLATE;for(const[k,v]of Object.entries(rep))h=h.split(k).join(String(v).replace(/[<>]/g,''));h=h.split('__DATA__').join(JSON.stringify(J).replace(/</g,'\\u003c'));
 document.open();document.write(h);document.close()}
if(Q.get('lat')&&!Q.get('pick')){playJourney()}else{
 const map=new maplibregl.Map({container:'map',style:`https://maps.geo.${REGION}.amazonaws.com/v2/styles/Hybrid/descriptor?key=${KEY}`,center:[78,20],zoom:1.8,attributionControl:{compact:true}});
 map.once('load',()=>setTimeout(()=>document.querySelectorAll('.maplibregl-ctrl-attrib').forEach(e=>e.classList.remove('maplibregl-compact-show')),1500));
 map.on('style.load',()=>{try{map.setProjection({type:'globe'})}catch(e){}});
 map.getCanvas().style.cursor='crosshair';
 const el=document.createElement('div');el.className='pin';PIN=new maplibregl.Marker({element:el});
 document.querySelector('#hero h1').onclick=()=>document.getElementById('hero').classList.remove('mini');
 window.choose=(lat,lon,name,fly)=>{SEL={lat,lon,name};if(innerWidth<700)document.getElementById('hero').classList.add('mini');PIN.setLngLat([lon,lat]).addTo(map);
  document.getElementById('pk_name').textContent=name?`The air over ${name}`:'The air right here';
  const hereEl=document.getElementById('pk_here');hereEl.textContent='Checking the forecast here…';const mine=SEL;
  fetch(`${API}/?here=1&lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}`).then(r=>r.json()).then(h=>{if(SEL!==mine)return;hereEl.textContent=(h.headline?('☁ '+h.headline):'Forecast unavailable here')+(h.headline?' · NOAA GFS forecast':'')}).catch(()=>{if(SEL===mine)hereEl.textContent='Forecast unavailable right now'});
  document.getElementById('pk_xy').textContent=`${Math.abs(lat).toFixed(2)}°${lat>=0?'N':'S'}, ${Math.abs(lon).toFixed(2)}°${lon>=0?'E':'W'} · click elsewhere to move the pin`;
  document.getElementById('pick').classList.add('on');if(fly)map.flyTo({center:[lon,lat],zoom:Math.max(map.getZoom(),4.5),duration:1800})};
 map.on('click',e=>choose(e.lngLat.lat,e.lngLat.lng,null,false));
 document.getElementById('pk_go').onclick=()=>SEL&&go(SEL.lat,SEL.lon,SEL.name);
 if(Q.get('pick')){const lv=Q.get('level');if(lv){const r=document.querySelector(`input[name=lev][value="${lv}"]`);if(r)r.checked=true}
  map.once('load',()=>choose(+Q.get('lat'),+Q.get('lon'),Q.get('name')||null,true))}
 document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{const[a,b,n]=c.dataset.c.split(',');choose(+a,+b,n,true)});
 // ---- intro: one breath before the globe
 const intro=document.getElementById('intro'),it=document.getElementById('intro_t');let introDone=false;
 const endIntro=()=>{if(introDone)return;introDone=true;intro.classList.add('gone');setTimeout(()=>intro.remove(),1500);startGuide()};
 intro.onclick=endIntro;
 if(Q.get('pick')){endIntro()}else{const seq=[[2000,'…and out.'],[4200,'That air has been somewhere you have never been.'],[7600,null]];
  seq.forEach(([t,txt])=>setTimeout(()=>{if(introDone)return;if(!txt){endIntro();return}it.style.opacity=0;setTimeout(()=>{it.textContent=txt;it.style.opacity=1},500)},t))}
 // ---- the visitor's own air
 document.getElementById('me').onclick=e=>{const b=e.currentTarget;if(!navigator.geolocation){b.textContent='Location not available - search instead';return}
  b.textContent='Finding the air around you…';navigator.geolocation.getCurrentPosition(p=>{b.textContent="📍 Trace the air I'm breathing";choose(p.coords.latitude,p.coords.longitude,null,true)},
  ()=>{b.textContent='Location blocked - click the globe or search instead'},{enableHighAccuracy:false,timeout:10000,maximumAge:600000})};
 // ---- Puff waits on the globe and drifts towards the pointer
 const guide=document.getElementById('guide');let gx=innerWidth*.62,gy=innerHeight*.3,gOn=false;
 function placeGuide(){guide.style.transform=`translate(${gx}px,${gy}px)`}
 function startGuide(){if(innerWidth<700)return;placeGuide();guide.classList.add('on');gOn=true}
 addEventListener('mousemove',e=>{if(!gOn||document.getElementById('pick').classList.contains('on'))return;const tx=Math.min(innerWidth-360,Math.max(460,e.clientX+60)),ty=Math.min(innerHeight-160,Math.max(40,e.clientY-120));gx+=(tx-gx)*.18;gy+=(ty-gy)*.18;placeGuide()});
 const _choose=window.choose;window.choose=(...a)=>{guide.classList.remove('on');gOn=false;spinning=false;_choose(...a)};
 // ---- idle spin until the visitor touches the globe
 let spinning=true;['mousedown','touchstart','wheel'].forEach(ev=>map.getCanvas().addEventListener(ev,()=>spinning=false,{passive:true}));
 (function spin(){if(spinning&&map.loaded()){const c=map.getCenter();map.setCenter([c.lng+0.04,c.lat])}requestAnimationFrame(spin)})();
 // ---- the planet breathing: live NOAA wind as streaks on the globe
 const cv=document.getElementById('wind'),cx=cv.getContext('2d');let W=null,parts=[];const N=innerWidth<700?700:1500;
 function fit(){cv.width=innerWidth*devicePixelRatio;cv.height=innerHeight*devicePixelRatio;cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px'}fit();addEventListener('resize',fit);
 fetch(`${API}/?wind=1`).then(r=>r.json()).then(d=>{if(!d.u)return;W=d;document.getElementById('windcap').textContent=`Live wind ~1.5 km up · NOAA GFS ${d.time_utc.replace('T',' ')} UTC`;
  for(let i=0;i<N;i++)parts.push(seed());requestAnimationFrame(flow)}).catch(()=>{});
 function seed(){if(map.getZoom()>2.4){const b=map.getBounds(),w=b.getWest(),e=b.getEast(),so=Math.max(-85,b.getSouth()),no=Math.min(85,b.getNorth());
   return{lon:((w+Math.random()*((e-w+360)%360||360))+540)%360-180,lat:so+Math.random()*(no-so),age:Math.random()*120|0}}
  return{lon:Math.random()*360-180,lat:Math.asin(Math.random()*2-1)*180/Math.PI*0.95,age:Math.random()*120|0}}
 function uv(lat,lon){const fi=(W.lat0-lat)/W.step,fj=(((lon-W.lon0)%360+360)%360)/W.step;const i0=Math.max(0,Math.min(W.nlat-2,Math.floor(fi))),j0=Math.floor(fj)%W.nlon,j1=(j0+1)%W.nlon,a=fi-i0,b=fj-Math.floor(fj);
  const g=(A,i,j)=>A[i*W.nlon+j];const f=A=>(1-a)*(1-b)*g(A,i0,j0)+(1-a)*b*g(A,i0,j1)+a*(1-b)*g(A,i0+1,j0)+a*b*g(A,i0+1,j1);return[f(W.u),f(W.v)]}
 function visible(lat,lon){const c=map.getCenter(),r=Math.PI/180;const cosd=Math.sin(lat*r)*Math.sin(c.lat*r)+Math.cos(lat*r)*Math.cos(c.lat*r)*Math.cos((lon-c.lng)*r);return cosd>0.12}
 let lastZ=null,userMove=false;map.on('move',()=>{if(!spinning)userMove=true});
 function flow(){if(!document.getElementById('pick').classList.contains('on')||true){
   const z=map.getZoom().toFixed(3);if(z!==lastZ||userMove){cx.clearRect(0,0,cv.width,cv.height);if(z!==lastZ)parts.forEach(p=>Object.assign(p,seed()));lastZ=z;userMove=false}
   cx.globalCompositeOperation='destination-in';cx.fillStyle='rgba(0,0,0,0.94)';cx.fillRect(0,0,cv.width,cv.height);cx.globalCompositeOperation='source-over';
   const k=0.022/Math.pow(1.85,Math.max(0,map.getZoom()-1.8)),dpr=devicePixelRatio;cx.lineWidth=(map.getZoom()>3?1.9:1.5)*dpr;
   for(const p of parts){const [u,v]=uv(p.lat,p.lon),sp=Math.hypot(u,v);const lat2=Math.max(-85,Math.min(85,p.lat+v*k)),lon2=p.lon+u*k/Math.max(.2,Math.cos(p.lat*Math.PI/180));
    if(visible(p.lat,p.lon)&&visible(lat2,lon2)){const a=map.project([p.lon,p.lat]),b=map.project([lon2,lat2]);if(Math.abs(a.x-b.x)<40&&Math.abs(a.y-b.y)<40){
     cx.strokeStyle=`rgba(${sp>15?'200,240,255':'255,255,255'},${Math.min(.7,.22+sp/30)})`;cx.beginPath();cx.moveTo(a.x*dpr,a.y*dpr);cx.lineTo(b.x*dpr,b.y*dpr);cx.stroke()}}
    p.lat=lat2;p.lon=((lon2+540)%360)-180;if(++p.age>140||sp<0.3)Object.assign(p,seed(),{age:0})}}
  requestAnimationFrame(flow)}
 let tm;document.getElementById('q').oninput=e=>{clearTimeout(tm);const v=e.target.value.trim();if(v.length<3){res.innerHTML='';return}
  tm=setTimeout(async()=>{try{const r=await fetch(`https://places.geo.${REGION}.amazonaws.com/v2/search-text?key=${KEY}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({QueryText:v,MaxResults:5,BiasPosition:map.getCenter().toArray()})});
   const d=await r.json();res.innerHTML='';(d.ResultItems||[]).forEach(it=>{const el=document.createElement('div');el.textContent=it.Title;el.onclick=()=>{res.innerHTML='';choose(it.Position[1],it.Position[0],(it.Title||'').split(',')[0],true)};res.appendChild(el)})}catch(err){res.textContent='Search unavailable'}},300)}}
})();
</script></body></html>"""
page = page.replace("__API__", API).replace("__KEY__", KEY).replace("__REGION__", REGION).replace("__TEMPLATE__", json.dumps(T).replace("</", "<\\/"))
pathlib.Path("web/index.html").write_text(page); print("wrote web/index.html", len(page) // 1024, "KB")
