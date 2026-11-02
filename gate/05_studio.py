"""Studio preview: globe intro, glowing air stream with drifting particles, follow-cam,
drone dives into 3D streets at each stop, postcards, odometer, data-driven sound.
Usage: python gate/05_studio.py out/journey_London_10.json [AMAZON_LOCATION_API_KEY] [region]
Without a key it uses OpenFreeMap (3D buildings) so you can preview tonight; with a key it
uses Amazon Location 'Hybrid' (satellite + labels) for the drone views."""
import json, sys, pathlib
J = json.load(open(sys.argv[1]))
KEY = sys.argv[2] if len(sys.argv) > 2 else ""
REGION = sys.argv[3] if len(sys.argv) > 3 else "ap-south-1"
STYLE = (f"https://maps.geo.{REGION}.amazonaws.com/v2/styles/Hybrid/descriptor?key={KEY}" if KEY
         else "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json")
html = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Biography of a Breath — __NAME__</title>
<link href="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.css" rel=stylesheet>
<script src="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500&family=Inter:wght@400;600&display=swap" rel=stylesheet>
<style>
:root{--ink:#eef3ff;--dim:#9fb0d0;--glass:rgba(8,14,32,.62);--air:#8fe3ff;--warm:#ffcf7a}
*{box-sizing:border-box}body{margin:0;background:#050912;color:var(--ink);font:14px Inter,system-ui;overflow:hidden}
#map{position:absolute;inset:0}
.glass{background:var(--glass);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.08);border-radius:16px}
#title{position:absolute;left:20px;top:18px;padding:14px 18px;max-width:420px}
#title h1{font:500 22px Fraunces,serif;margin:0 0 4px}#title p{margin:0;color:var(--dim)}
#hud{position:absolute;left:50%;top:18px;transform:translateX(-50%);display:flex;gap:18px;padding:10px 18px;font-variant-numeric:tabular-nums}
#hud div{text-align:center}#hud b{display:block;font-size:18px}#hud span{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
#diary{position:absolute;right:20px;top:18px;max-height:46vh;width:290px;background:rgba(8,14,32,.45);padding:14px 16px;overflow:auto}
#diary h3{margin:0 0 8px;font:500 16px Fraunces,serif}.entry{padding:8px 0;border-top:1px solid rgba(255,255,255,.07);opacity:0;transform:translateY(6px);transition:all .6s}
.entry.on{opacity:1;transform:none}.entry small{color:var(--dim)}
#entries{position:relative}#entries:before{content:'';position:absolute;left:13px;top:10px;bottom:10px;width:1px;background:linear-gradient(rgba(143,227,255,.35),rgba(255,255,255,.05))}
.entry{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:start;border-top:0!important;padding:7px 0!important}
.entry .ic{position:relative;width:27px;height:27px;border-radius:50%;display:grid;place-items:center;font-size:13px;background:#0d1730;border:1px solid rgba(255,255,255,.14)}
.entry .tx{font-size:13px;line-height:1.35;padding-top:3px}.entry .tx small{display:block;font-size:11px;color:var(--dim);margin-top:1px}
.entry.k-hazard .ic{border-color:rgba(255,140,90,.6);background:#2a1610}.entry.k-town .ic,.entry.k-reach .ic{border-color:rgba(143,227,255,.6)}.entry.k-here .ic,.entry.k-start .ic{border-color:rgba(255,207,122,.7)}
.entry.k-here{background:rgba(255,207,122,.07);border-radius:10px;padding:7px 6px!important}
#card{position:absolute;left:50%;bottom:120px;transform:translate(-50%,20px);padding:16px 22px;min-width:320px;text-align:center;opacity:0;transition:all .6s;pointer-events:none}
#card.on{opacity:1;transform:translate(-50%,0)}#card h2{margin:0;font:500 26px Fraunces,serif}#card p{margin:4px 0 0;color:var(--dim)}
#bar{position:absolute;left:20px;right:20px;bottom:20px;padding:14px 18px;display:flex;align-items:center;gap:16px}
button{font:600 14px Inter;padding:11px 18px;border-radius:12px;border:0;background:linear-gradient(135deg,#8fe3ff,#b7a6ff);color:#061023;cursor:pointer}
#track{flex:1;height:6px;border-radius:3px;background:rgba(255,255,255,.1);position:relative}#fill{position:absolute;inset:0 auto 0 0;width:0;border-radius:3px;background:linear-gradient(90deg,#8fe3ff,#ffcf7a)}
#passport{position:absolute;inset:0;display:none;place-items:center;background:rgba(5,9,18,.55)}#passport .glass{padding:26px 32px;max-width:460px;text-align:center}
#passport h2{font:500 28px Fraunces,serif;margin:0 0 6px}.stamps{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:14px 0}
.stamp{border:1px dashed var(--warm);color:var(--warm);border-radius:8px;padding:4px 8px;font-size:12px;transform:rotate(-3deg)}
#story{position:absolute;left:0;right:0;top:38%;text-align:center;font:500 40px Fraunces,serif;text-shadow:0 2px 30px #000;opacity:0;transition:opacity 1s;pointer-events:none;padding:0 15%}
#story.on{opacity:1}
#h_ppw{display:none}#h_ppw b{color:#ffb38f}
#passport .glass.impact{max-width:600px;width:calc(100% - 24px);max-height:88vh;overflow:auto;text-align:left;padding:22px 24px;scrollbar-width:none;-ms-overflow-style:none}
#passport .glass.impact::-webkit-scrollbar{display:none}
#passport .glass.impact{position:relative}
.impact .x{position:absolute;top:12px;right:12px;width:32px;height:32px;min-width:0;padding:0;border-radius:50%;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:#eef3ff;font:400 20px/1 Inter,system-ui;cursor:pointer}
.impact .x:hover{background:rgba(255,255,255,.16)}
#rp_card{position:absolute;display:none;padding:10px 14px;cursor:pointer;font-size:12px;transition:background .2s}
#rp_card:hover,#rp_card:focus-visible{background:rgba(255,207,122,.12);outline:none}
#rp_card span{display:block;color:var(--warm);font-size:10px;letter-spacing:.14em;text-transform:uppercase}
#rp_card b{display:flex;justify-content:space-between;align-items:center;font:500 15px Fraunces,serif;margin-top:2px}
#rp_card b i{font:400 12px Inter,system-ui;color:var(--dim);font-style:normal}
.impact .lede{color:#cfdaf3;margin:4px 0 12px;line-height:1.45}.impact .lede b{color:#fff}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0 14px}.tile{border-radius:12px;padding:10px 12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
.tile b{display:block;font:600 20px Inter;font-variant-numeric:tabular-nums}.tile span{color:var(--dim);font-size:11px}.tile.t24 b{color:#ff8f8f}.tile.t48 b{color:#ffb38f}.tile.t72 b{color:#ffe08f}
.tl{display:grid;gap:4px;margin:6px 0 12px}.tlr{display:grid;grid-template-columns:96px 1fr 120px;gap:10px;align-items:center;font-size:12.5px;padding:5px 0;border-top:1px solid rgba(255,255,255,.06)}
.tlr .when{color:var(--dim);font-variant-numeric:tabular-nums}.tlr .when b{color:#eef3ff;font-weight:600}.tlr .bar{height:6px;border-radius:3px;background:rgba(255,255,255,.08);position:relative}
.tlr .bar i{position:absolute;inset:0 auto 0 0;border-radius:3px}.tlr .pop{font-size:11px;color:var(--dim);text-align:right}
.impact .why{font-size:12.5px;color:#dfe8ff;background:rgba(255,179,143,.08);border:1px solid rgba(255,179,143,.25);border-radius:10px;padding:9px 11px;margin:8px 0 12px}
.impact .acts{display:flex;gap:8px;flex-wrap:wrap}.impact .acts button{flex:1;min-width:130px}.impact .acts .ghost{background:rgba(255,255,255,.08);color:#eef3ff;border:1px solid rgba(255,255,255,.15)}
.aqc{display:inline-block;margin-top:2px;padding:0 6px;border:1px solid;border-radius:999px;font-size:10.5px;font-weight:600}
.impact .kick{margin:0;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--warm)}.impact h3{font:500 17px Fraunces,serif;margin:16px 0 6px}
.route{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:6px;align-items:center;margin:10px 0 12px;text-align:center}.route div{padding:8px 6px;border-radius:12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
.route div span{display:block;font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em}.route div b{font-size:13px}.route .now{border-color:rgba(255,207,122,.6);background:rgba(255,207,122,.08)}.route i{font-style:normal;font-size:11px;color:var(--dim);white-space:nowrap}
.tiles.six{grid-template-columns:repeat(3,1fr)}.tile b{font-size:17px}.disc{list-style:none;padding:0;margin:0;display:grid;gap:6px}.disc li{display:grid;grid-template-columns:24px 1fr;font-size:13px;line-height:1.4}
.chips2{display:flex;flex-wrap:wrap;gap:6px}.pc{font-size:12px;padding:4px 9px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1)}.pc.big{border-color:rgba(143,227,255,.5)}.pc small{color:var(--dim);margin-left:6px;font-size:10.5px}
.why.empty{font-size:13px;line-height:1.5}
@media(max-width:700px){.route{grid-template-columns:1fr;gap:4px}.route i{display:none}.tiles.six{grid-template-columns:1fr 1fr}}
.impact .fine{font-size:10.5px;color:var(--dim);margin-top:10px}
#story small{display:block;font:400 16px Inter;color:var(--dim);margin-top:8px}

.puff{position:relative;width:96px;height:96px;pointer-events:none;filter:drop-shadow(0 0 16px rgba(143,227,255,.8))}
.puff svg{width:96px;height:96px;animation:bob 1.8s ease-in-out infinite}
.puff .trail{fill:none;stroke:#eafaff;stroke-linecap:round;stroke-dasharray:30 12;animation:flow .7s linear infinite;opacity:.85}
.puff .trail.t2{animation-duration:.42s;opacity:.7}.puff .trail.t3{animation-duration:.66s;opacity:.55}
@keyframes flow{to{stroke-dashoffset:-42}}
.puff .body{animation:sway 1.4s ease-in-out infinite;transform-origin:48px 30px}@keyframes sway{50%{transform:skewX(-6deg)}}
.puff .curl{fill:none;stroke:#ffffff;stroke-width:3;stroke-linecap:round;animation:curl 1.2s ease-in-out infinite;transform-origin:48px 30px}
@keyframes curl{50%{transform:rotate(-14deg)}}
#windfx{position:absolute;inset:0;pointer-events:none}
@keyframes bob{50%{transform:translateY(-5px)}}
.puff .eye{animation:blink 4.2s infinite;transform-origin:center;transform-box:fill-box}
@keyframes blink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}
.puff.cold svg{animation:bob 2.4s ease-in-out infinite,shiver .18s linear infinite}.puff.cold .body{fill:#d9efff}
@keyframes shiver{50%{translate:1.5px 0}}
.puff.hot .body{fill:#fff1d6}.puff.hot .cheek{opacity:.9}
.puff.night .eye{transform:scaleY(.35)}
.puff .drops{opacity:0;transition:opacity .4s}.puff.rain .drops{opacity:1}
.puff .drops line{stroke:#9fd0ff;stroke-width:2;stroke-linecap:round;animation:fall .7s linear infinite}
@keyframes fall{from{transform:translateY(-4px);opacity:1}to{transform:translateY(10px);opacity:0}}
.puff.talk .mouth{animation:talk .22s ease-in-out infinite alternate}@keyframes talk{to{transform:scaleY(2.2)}}
.puff .mouth{transform-origin:center;transform-box:fill-box}
.bubble{position:absolute;left:92px;bottom:58px;width:max-content;max-width:300px;background:#fff;color:#14203b;padding:10px 14px;border-radius:16px 16px 16px 4px;
 font:500 14px/1.4 Inter;box-shadow:0 8px 30px rgba(0,0,0,.35);opacity:0;transform:translateY(6px) scale(.96);transition:all .35s}
.bubble.on{opacity:1;transform:none}
#mute{position:absolute;right:20px;bottom:92px;font:600 12px Inter;padding:7px 11px;border-radius:999px;background:rgba(8,14,32,.6);color:#eef3ff;border:1px solid rgba(255,255,255,.15);cursor:pointer}

#title{padding:10px 14px;max-width:340px}#title h1{font-size:17px;margin:0 0 2px}#title p{font-size:12px}
#hud{top:auto;bottom:22px;opacity:0;transition:opacity .8s;padding:8px 16px;gap:16px}#hud b{font-size:15px}#hud span{font-size:10px}
#diary{max-height:38vh;width:260px;background:rgba(8,14,32,.35)}#diary h3{font-size:14px}.entry{font-size:13px}
#start{position:absolute;left:50%;bottom:28px;transform:translateX(-50%);display:flex;gap:22px;align-items:center;padding:16px 22px;transition:opacity .8s}
#start.gone{opacity:0;pointer-events:none}#start .here{margin:8px 0 0;font-size:13px;color:#dfe8ff;padding:7px 10px;border-radius:10px;background:rgba(143,227,255,.08);border:1px solid rgba(143,227,255,.18);max-width:430px}#start .here:empty{display:none}
#s_flip{display:inline-block;margin-top:8px;font-size:12px;color:#8fe3ff;text-decoration:none}#s_flip:hover{text-decoration:underline}
#agent .home{margin-top:9px;padding-top:8px;border-top:1px solid rgba(255,255,255,.08);color:#dfe8ff;font-size:11.5px}#agent .home:empty{display:none}#agent .home span{color:var(--dim);display:block;font-size:10px;letter-spacing:.08em;text-transform:uppercase}#start .kicker{margin:0;color:var(--dim);letter-spacing:.12em;text-transform:uppercase;font-size:12px}
#start h2{font:500 30px Fraunces,serif;margin:2px 0}#start #play{white-space:nowrap}#start .sub{margin:0;color:var(--dim);font-size:13px}#start button{font-size:16px;padding:14px 26px;border-radius:999px}
#hint{position:absolute;left:20px;bottom:22px;padding:8px 14px;font-size:12px;color:var(--dim);opacity:0;transition:opacity .8s}#hint.on{opacity:1}
#mute{bottom:22px;right:20px}
#agent{position:absolute;left:20px;top:104px;width:250px;padding:12px 14px;font-size:12px;opacity:0;transition:opacity .8s;font-variant-numeric:tabular-nums}
#agent.on{opacity:1}#agent .ah{display:flex;justify-content:space-between;align-items:center;color:var(--dim);font-size:10px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px}
#agent .live{color:#7dffb0}#agent .live:before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:#7dffb0;margin-right:5px;animation:blinkdot 1.6s infinite}
@keyframes blinkdot{50%{opacity:.25}}#agent .place{font:500 16px Fraunces,serif;margin:0 0 1px}#agent .sub{color:var(--dim);margin:0 0 8px}
#agent .grid{display:grid;grid-template-columns:1fr 1fr;gap:5px 10px}#agent .grid div{display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.06);padding-bottom:3px}
#agent .grid span{color:var(--dim)}#agent .hz{margin-top:9px;display:flex;flex-wrap:wrap;gap:5px}
#agent .chip{padding:3px 8px;border-radius:999px;font-size:11px;background:rgba(255,120,80,.22);border:1px solid rgba(255,140,90,.5);color:#ffd9c8}
#agent .aq{margin-top:8px;display:flex;align-items:center;gap:8px;font-size:12px}#agent .aq:empty{display:none}#agent .aq i{width:10px;height:10px;border-radius:50%;flex:none}
#agent .aq b{font-variant-numeric:tabular-nums}#agent .aq small{color:var(--dim)}#agent .feel{margin-top:6px;font-style:italic;color:#dfe8ff;font-size:12px}#agent .feel:empty{display:none}
#agent .calm{color:var(--dim);font-size:11px}
@media(max-width:700px){#agent{top:auto;bottom:70px;left:10px;width:calc(100% - 20px)}}
@media(max-width:700px){
 #title{left:10px;right:10px;top:10px;max-width:none;padding:8px 12px}#title h1{font-size:16px;margin:0}#title p{display:none}
 #agent{left:10px!important;right:10px;width:auto!important;top:52px!important;bottom:auto!important;padding:8px 10px;font-size:11px}
 #agent .grid{grid-template-columns:1fr 1fr 1fr;gap:3px 8px}#agent .place{font-size:14px}#agent .sub{margin-bottom:5px}#agent .home{display:none}#agent .ah{margin-bottom:3px}
 #diary,#hint{display:none!important}
 #hud{left:10px;right:10px;transform:none;bottom:10px!important;gap:6px;padding:6px 8px;justify-content:space-around}#hud b{font-size:13px!important}#hud span{font-size:8.5px!important;letter-spacing:.04em}
 #start{left:10px;right:10px;transform:none;bottom:10px;flex-direction:column;align-items:stretch;gap:10px;padding:14px}#start h2{font-size:24px}#start button{width:100%}
 #card{min-width:0;width:calc(100% - 20px);bottom:70px;padding:10px 14px}#card h2{font-size:20px}
 #story{font-size:22px;padding:0 6%;top:62%}#story small{font-size:12px}
 .bubble{left:-70px;bottom:104px;max-width:230px;font-size:12.5px}
 .tlr{grid-template-columns:78px 1fr 70px}.tile b{font-size:16px}#passport .glass.impact{padding:16px}
}
.maplibregl-ctrl-bottom-right .maplibregl-ctrl-attrib{margin:0 6px 6px 0;opacity:.55;transform:scale(.85);transform-origin:bottom right}
.maplibregl-ctrl-attrib.maplibregl-compact{min-height:20px;background:rgba(8,14,32,.5)!important;color:#cfdaf3}.maplibregl-ctrl-attrib.maplibregl-compact a{color:#cfdaf3}
</style></head><body>
<div id=map></div><canvas id=windfx></canvas>
<div id=title class=glass><h1>Biography of a Breath</h1><p>The air arriving in <b>__NAME__</b> at __ARR__ — rewound __HRS__ hours through real NOAA winds (__LEVEL__).</p></div>
<div id=hud class=glass><div><b id=h_km>0</b><span>km travelled</span></div><div><b id=h_w>—</b><span>wind km/h</span></div><div><b id=h_c>—</b><span>°C</span></div><div id=h_ppw><b id=h_pp>0</b><span>people reached</span></div><div><b id=h_r>—</b><span id=h_rl>rain mm/h</span></div></div>
<div id=agent class=glass><div class=ah><span>Puff's field notes</span><span class=live>live data</span></div>
<p class=place id=a_place>—</p><p class=sub id=a_sub>—</p>
<div class=grid><div><span id=a_wl>Wind</span><b id=a_w>—</b></div><div><span>Ground gusts</span><b id=a_g>—</b></div><div><span>Temp</span><b id=a_t>—</b></div><div><span>Humidity</span><b id=a_h>—</b></div>
<div><span>Rain</span><b id=a_r>—</b></div><div><span>Visibility</span><b id=a_v>—</b></div></div>
<div class=aq id=a_aq></div><div class=feel id=a_feel></div><div class=hz id=a_hz></div><div class=home id=a_home></div></div>
<div id=rp_card class=glass role=button tabindex=0 aria-label="Reopen the journey report"><span>Journey report</span><b>The life of this breath <i>Open ›</i></b></div>
<div id=diary class=glass><h3>Puff's diary</h3><div id=entries></div></div>
<div id=story></div><div id=card class=glass><h2 id=c_name></h2><p id=c_meta></p></div>
<div id=start class=glass><div><p class=kicker>The air that reached</p><h2>__NAME__</h2><p class=sub>has a story to tell · or click anywhere to pick another spot</p><p class=here id=s_here></p><a id=s_flip href="#"></a></div><button id=play>Release Puff</button></div>
<div id=hint class=glass>Click anywhere on Earth to trace another breath</div>
<div id=passport><div class=glass><h2>Air Passport</h2><p id=p_sum></p><div class=stamps id=p_stamps></div><button onclick="location.reload()">Release another</button></div></div>
<script>
const J=__DATA__;(function(){let lastC=1e9;J.events=(J.events||[]).filter(e=>{if(e.kind!=='coast')return true;if(lastC-e.hours_ago<5)return false;lastC=e.hours_ago;return true})})();const P=J.points, HRS=P[0].hours_ago;let STOPS=(J.places||[]).slice();if(STOPS.length>6)STOPS=[0,1,2,3,4,5].map(i=>STOPS[Math.round(i*(STOPS.length-1)/5)]);
const FWD=J.direction==='forward',BOTH=J.direction==='both',MID=J.mid_hours||0;const lerp=(a,b,f)=>a+(b-a)*f;
function when(hAgo,long){const u=long?'hours':'h';if(BOTH){const r=MID-hAgo;return Math.abs(r)<.5?(long?'right now':'now'):r<0?`${(-r).toFixed(0)} ${u} ago`:`in ${r.toFixed(0)} ${u}`}return FWD?`in ${(HRS-hAgo).toFixed(0)} ${u}`:`${hAgo.toFixed(0)} ${u} ago`}
function at(h){ // h = hours ago (float) -> interpolated point
  let i=P.findIndex(p=>p.hours_ago<=h); if(i<=0) return P[Math.max(0,i)]; const a=P[i-1],b=P[i],f=(a.hours_ago-h)/(a.hours_ago-b.hours_ago);
  return {lat:lerp(a.lat,b.lat,f),lon:lerp(a.lon,b.lon,f),temp_c:lerp(a.temp_c,b.temp_c,f),wind_kmh:lerp(a.wind_kmh,b.wind_kmh,f),rain_mmh:lerp(a.rain_mmh,b.rain_mmh,f),km:lerp(a.km_from_start,b.km_from_start,f),land:b.land}}
function bearing(a,b){const y=Math.sin((b.lon-a.lon)*Math.PI/180)*Math.cos(b.lat*Math.PI/180),x=Math.cos(a.lat*Math.PI/180)*Math.sin(b.lat*Math.PI/180)-Math.sin(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.cos((b.lon-a.lon)*Math.PI/180);return Math.atan2(y,x)*180/Math.PI}
const map=new maplibregl.Map({container:'map',style:'__STYLE__',center:[P[P.length-1].lon,P[P.length-1].lat],zoom:4.2,pitch:0,attributionControl:{compact:true}});
map.once('load',()=>setTimeout(()=>document.querySelectorAll('.maplibregl-ctrl-attrib').forEach(e=>e.classList.remove('maplibregl-compact-show')),1500));
function err(m){const e=document.createElement('div');e.className='entry on';e.style.color='#ff9b9b';e.textContent='⚠ '+m;entries.prepend(e)}
window.onerror=(m)=>err(m);map.on('error',e=>err((e.error&&e.error.message)||'map error'));
map.on('style.load',()=>{
  map.addSource('full',{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:P.map(p=>[p.lon,p.lat])}}});
  map.addLayer({id:'full',type:'line',source:'full',paint:{'line-color':'#ffffff','line-opacity':.25,'line-width':1.5,'line-dasharray':[2,3]}});
  map.addSource('trail',{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:[[P[0].lon,P[0].lat],[P[0].lon,P[0].lat]]}}});
  map.addLayer({id:'trail-glow',type:'line',source:'trail',paint:{'line-color':'#8fe3ff','line-width':18,'line-blur':14,'line-opacity':.7}});
  map.addSource('night',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'night',type:'fill',source:'night',paint:{'fill-color':'#000814','fill-opacity':.38}},'full');
  map.addSource('swarm',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'swarm',type:'line',source:'swarm',paint:{'line-color':'#cfe9ff','line-width':1.2,'line-opacity':.35}});
  map.addSource('swarmhead',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'swarmhead',type:'circle',source:'swarmhead',paint:{'circle-radius':2.5,'circle-color':'#ffffff','circle-opacity':.7,'circle-blur':.5}});
  map.addSource('dwn',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'dwn-glow',type:'circle',source:'dwn',paint:{'circle-radius':['*',['get','r'],2.2],'circle-color':['get','c'],'circle-opacity':.18,'circle-blur':.8}});
  map.addLayer({id:'dwn',type:'circle',source:'dwn',paint:{'circle-radius':['get','r'],'circle-color':['get','c'],'circle-opacity':.85,'circle-stroke-color':'#ffffff','circle-stroke-width':1,'circle-stroke-opacity':.6}});
  map.addSource('ribbon',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'ribbon',type:'line',source:'ribbon',layout:{'line-cap':'round'},paint:{'line-color':['get','c'],'line-width':5}});
  map.addSource('air',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'air',type:'circle',source:'air',paint:{'circle-radius':['get','r'],'circle-color':['get','c'],'circle-opacity':['get','o'],'circle-blur':.4}});
  map.addSource('head',{type:'geojson',data:{type:'Point',coordinates:[P[0].lon,P[0].lat]}});
  map.addLayer({id:'halo',type:'circle',source:'head',paint:{'circle-radius':14,'circle-color':'#8fe3ff','circle-opacity':.18,'circle-blur':1}});
  puffEl=document.createElement('div');puffEl.className='puff';puffEl.innerHTML=`<svg viewBox="0 0 96 96">
   <path class="trail" stroke-width="3.2" d="M2 56 C16 58 26 50 23 41 C21 35 13 36 15 42"/>
   <path class="trail t2" stroke-width="3" d="M94 46 C80 44 70 52 73 61 C75 67 83 66 81 60"/>
   <path class="trail t3" stroke-width="2.4" d="M4 76 C18 80 30 76 34 70"/><path class="trail t2" stroke-width="2.4" d="M92 82 C80 84 70 80 66 74"/>
   <g class=drops><line x1=38 y1=74 x2=36 y2=80 /><line x1=50 y1=84 x2=48 y2=90 style="animation-delay:.25s"/><line x1=60 y1=72 x2=58 y2=78 style="animation-delay:.5s"/></g>
   <path class=body fill="#ffffff" d="M48 16 C61 16 67 27 67 36 C67 48 57 56 52 66 C48 74 51 84 60 88 C46 90 38 80 41 68 C33 59 29 48 29 36 C29 26 36 16 48 16 Z"/>
   <ellipse class=eye cx=41.5 cy=35 rx=3 ry=4.2 fill="#14203b"/><ellipse class=eye cx=54.5 cy=35 rx=3 ry=4.2 fill="#14203b"/>
   <circle cx=42.6 cy=33.6 r=1.1 fill="#fff"/><circle cx=55.6 cy=33.6 r=1.1 fill="#fff"/>
   <ellipse class=cheek cx=36 cy=41 rx=3.2 ry=1.9 fill="#ff9fb0" opacity=".45"/><ellipse class=cheek cx=60 cy=41 rx=3.2 ry=1.9 fill="#ff9fb0" opacity=".45"/>
   <ellipse class=mouth cx=48 cy=43 rx=2.8 ry=1.3 fill="#14203b"/></svg><div class=bubble></div>`;
  puffMk=new maplibregl.Marker({element:puffEl,anchor:'center'}).setLngLat([P[0].lon,P[0].lat]).addTo(map);
  STOPS.forEach(s=>{const el=document.createElement('div');el.style.cssText='width:10px;height:10px;border-radius:50%;background:#ffcf7a;box-shadow:0 0 12px #ffcf7a';s.m=new maplibregl.Marker({element:el}).setLngLat([s.lon,s.lat]).addTo(map)});
});
let puffEl,puffMk,LINES=null,spoken=new Set(),muted=false,curAudio=null;const API='__API__';
fetch(`${API}/narrate${location.search}`).then(r=>r.json()).then(d=>{LINES=(d.lines||[]).sort((a,b)=>b.hours_ago-a.hours_ago);if(AC)LINES.forEach(decodeLine)}).catch(()=>{LINES=[]});

async function decodeLine(l){if(l._buf||!l.audio_mp3_b64||!AC)return l._buf;const bin=atob(l.audio_mp3_b64),u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
 try{l._buf=await new Promise((res,rej)=>AC.decodeAudioData(u.buffer,res,rej))}catch(e){l._buf=null}return l._buf}
let speaking=false;
function speak(l,now){const b=puffEl.querySelector('.bubble');b.textContent=l.text;b.classList.add('on');puffEl.classList.add('talk');speaking=true;
 let ms=Math.max(2800,l.text.split(' ').length*340);pausedUntil=Math.max(pausedUntil,now+ms);
 const done=()=>{b.classList.remove('on');puffEl.classList.remove('talk');speaking=false;g&&g.gain.setTargetAtTime(.7,AC.currentTime,.4)};
 if(!muted&&AC){g.gain.setTargetAtTime(.18,AC.currentTime,.2);decodeLine(l).then(buf=>{if(!buf){setTimeout(done,ms);return}
   const src=AC.createBufferSource();src.buffer=buf;src.connect(voiceGain);src.start();curAudio=src;const dur=buf.duration*1000+350;
   pausedUntil=Math.max(pausedUntil,performance.now()+dur);src.onended=()=>setTimeout(done,250)})}else setTimeout(done,ms)}
const ARR=Date.parse(J.arrival_utc);
(function(){const H=J.here;if(H&&H.headline){document.getElementById('s_here').textContent='☁ Right here: '+H.headline+' (NOAA GFS forecast)';
  document.getElementById('a_home').innerHTML=`<span>${BOTH?'Right now at':'Back at'} __NAME__</span>${H.headline.replace(/[<>]/g,'')}`}
 const Qs=new URLSearchParams(location.search);Qs.set('dir',FWD?'back':'forward');const fl=document.getElementById('s_flip');fl.textContent=FWD?'⟲ or trace where this air came from':'Where will the air go from here? ⟶';fl.href='?'+Qs;
 if(!J.level.startsWith('10'))document.getElementById('a_wl').textContent='Wind ~1.5 km up';
 const place=()=>{const t=document.getElementById('title'),a=document.getElementById('agent');if(innerWidth>700)a.style.top=(t.offsetTop+t.offsetHeight+10)+'px'};place();addEventListener('resize',place);setTimeout(place,300)})();
if(BOTH){document.querySelector('#title p').innerHTML=`The air passing over <b>${J.name}</b> right now: where it came from over the last 72 hours of real NOAA winds, and where the latest forecast carries it next.`;
 document.querySelector('#start .kicker').textContent='The air passing over';document.querySelector('#start .sub').textContent='where it came from, and where it goes next · or click anywhere to pick another spot';
 document.getElementById('s_flip').style.display='none'}
if(FWD){document.querySelector('#title p').innerHTML=`The air leaving <b>${J.name}</b> at ${J.release_utc.slice(0,16).replace('T',' ')} UTC, followed 72 hours forward through the latest NOAA forecast.`;
 document.querySelector('#start .kicker').textContent='The air leaving';document.querySelector('#start .sub').textContent='where will it go, and who breathes it next?';
 document.querySelector('#diary h3').textContent='Where Puff is heading';}
map.on('click',e=>{if(mode==='dive')return;if(!running&&!document.getElementById('start').classList.contains('gone')){}const Qs=new URLSearchParams(location.search);
 location.search=new URLSearchParams({lat:e.lngLat.lat.toFixed(4),lon:e.lngLat.lng.toFixed(4),level:Qs.get('level')||'850'})});
map.getCanvas().style.cursor='crosshair';
const HASAQ=P.some(p=>p.aqi!=null);
function aqcol(a){return a==null?'#9fb0d0':a<=50?'#4fd18b':a<=100?'#ffd84d':a<=150?'#ff9f43':a<=200?'#ff5a5a':a<=300?'#b05cff':'#8c1d3a'}
function tcol(t){const st=[[-5,'#5aa9ff'],[5,'#9fe6ff'],[15,'#f4f7ff'],[25,'#ffcf7a'],[35,'#ff7a59']];for(let i=1;i<st.length;i++)if(t<=st[i][0])return st[i][1];return st[st.length-1][1]}
function night(ms){const d=new Date(ms),doy=(ms-Date.UTC(d.getUTCFullYear(),0,0))/864e5,dec=-23.44*Math.cos(2*Math.PI*(doy+10)/365)*Math.PI/180,
 sub=-((d.getUTCHours()+d.getUTCMinutes()/60)-12)*15,ring=[];for(let lo=-180;lo<=180;lo+=3){const la=Math.atan(-Math.cos((lo-sub)*Math.PI/180)/Math.tan(dec))*180/Math.PI;ring.push([lo,la])}
 const pole=dec>0?-90:90;ring.push([180,pole],[-180,pole],ring[0]);return{type:'Feature',geometry:{type:'Polygon',coordinates:[ring]}}}
const story=document.getElementById('story');function say(t,sub,ms){story.innerHTML=t+(sub?`<small>${sub}</small>`:'');story.classList.add('on');setTimeout(()=>story.classList.remove('on'),ms||2600)}
let lastHour=-1;
// --- sound: temperature -> pitch, wind -> pulse, rain -> soft noise, stop -> bell
let AC,g,noise,voiceGain; const PENTA=[0,2,4,7,9,12,14,16,19,21,24,26,28];
function audio(){AC=new (window.AudioContext||window.webkitAudioContext)();g=AC.createGain();g.gain.value=.7;g.connect(AC.destination);
 voiceGain=AC.createGain();voiceGain.gain.value=1;voiceGain.connect(AC.destination);
 const b=AC.createBuffer(1,AC.sampleRate,AC.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=Math.random()*2-1;noise=b}
function pluck(freq,vol,len){const o=AC.createOscillator(),e=AC.createGain(),f=AC.createBiquadFilter();o.type='triangle';o.frequency.value=freq;f.type='lowpass';f.frequency.value=2200;
 o.connect(f);f.connect(e);e.connect(g);const t=AC.currentTime;e.gain.setValueAtTime(0,t);e.gain.linearRampToValueAtTime(vol,t+.015);e.gain.exponentialRampToValueAtTime(.0001,t+len);o.start(t);o.stop(t+len+.05)}
function chime(){const o=AC.createOscillator(),e=AC.createGain();o.type='sine';o.frequency.value=1600+Math.random()*900;o.connect(e);e.connect(g);
 const t=AC.currentTime;e.gain.setValueAtTime(.025,t);e.gain.exponentialRampToValueAtTime(.0001,t+.35);o.start(t);o.stop(t+.4)}
function bell(){[523.25,659.25,783.99].forEach((f,i)=>setTimeout(()=>pluck(f,.06,1.6),i*90))}
let beat=0;
// --- particles: air flowing behind the head
let parts=[];function puff(p,brg,wind){for(let k=0;k<2;k++){const ang=(brg+180+(Math.random()-.5)*50)*Math.PI/180,sp=.008+Math.random()*.02;
 parts.push({lat:p.lat,lon:p.lon,dl:Math.cos(ang)*sp,dn:Math.sin(ang)*sp,age:0,c:p.rain_mmh>.2?'#9fd0ff':(p.temp_c>25?'#ffcf7a':'#bff3ff')})}}
// --- timeline
const KMPS=Math.max(15,J.total_km/50); // ~50 s of travel at constant visual speed (plus drone pauses)
let h=HRS,last=0,running=false,pausedUntil=0,dived=new Set(),evShown=new Set(),pulse=0,brg=0,mode='follow';
const ICON={region:'🗺',rain:'🌧',temp:'🌡',here:'📍',town:'🏘',reach:'👥',start:'✨',coast:'🏖',hazard:'⚠'};
function iconFor(kind,t){t=(t||'').replace(/<[^>]+>/g,'');if(kind==='hazard'){if(/snow/.test(t))return'❄';if(/air/.test(t))return'😷';if(/visib/.test(t))return'🌫';if(/gust/.test(t))return'💨';if(/thunder/.test(t))return'⛈';if(/rain/.test(t))return'🌧';if(/cold/.test(t))return'🥶';if(/heat/.test(t))return'🔆';return'⚠'}if(kind==='region'&&/^over the/.test(t))return'🌊';if(kind==='region')return'🏔';return ICON[kind]||'•'}
let lastKey=null,lastEl=null;
function entry(text,sub,kind){kind=kind||'note';const key=kind+'|'+text.replace(/<[^>]+>/g,'').replace(/[\d.,·]+/g,'#');
 if(key===lastKey&&lastEl&&lastEl.isConnected){lastEl._n=(lastEl._n||1)+1;lastEl.querySelector('small').textContent=`${sub} · ×${lastEl._n}`;lastEl.classList.remove('on');requestAnimationFrame(()=>lastEl.classList.add('on'));return}
 const e=document.createElement('div');e.className='entry k-'+kind;e.innerHTML=`<span class=ic>${iconFor(kind,text)}</span><span class=tx>${text.charAt(0).toUpperCase()+text.slice(1)}${sub?`<small>${sub}</small>`:''}</span>`;
 entries.prepend(e);lastKey=key;lastEl=e;while(entries.children.length>6)entries.lastChild.remove();requestAnimationFrame(()=>e.classList.add('on'))}
function card(s){c_name.textContent=s.name;c_meta.textContent=`${(s.country_name||s.country)} · ${when(s.hours_ago)} · ${s.temp_c} °C · ${s.rain_mmh>0.05?s.rain_mmh+' mm/h rain':'dry'} · ${s.dist_km} km from the path`;card_el.classList.add('on')}
const card_el=document.getElementById('card');
function dive(s){mode='dive';pausedUntil=performance.now()+6200;card(s);bell();entry(`Over <b>${s.name}</b> · ${s.temp_c} °C`,`${when(s.hours_ago)} · ${(s.country_name||s.country)}`,'town');
 map.flyTo({center:[s.lon,s.lat],zoom:13.2,pitch:66,bearing:brg,duration:2600,essential:true});
 setTimeout(()=>map.easeTo({bearing:brg+70,duration:2400,easing:t=>t}),2700);
 setTimeout(()=>{card_el.classList.remove('on');const p=at(h);map.flyTo({center:[p.lon,p.lat],zoom:J.total_km>1500?6.3:7.4,pitch:62,bearing:brg,duration:1600});setTimeout(()=>mode='follow',1600)},5200)}
const WFX=document.getElementById('windfx'),WX=WFX.getContext('2d');let STREAKS=[];
function fitWFX(){WFX.width=innerWidth*devicePixelRatio;WFX.height=innerHeight*devicePixelRatio}fitWFX();addEventListener('resize',fitWFX);
function windfx(p,dt){const W=WFX.width,H=WFX.height,w=Math.max(2,p.wind_kmh||0),want=Math.min(90,8+w*1.6),v=(.25+w/45)*H;
 while(STREAKS.length<want)STREAKS.push({x:Math.random()*W,y:H*(.2+Math.random()*.9),l:20+Math.random()*60,a:.05+Math.random()*.16,s:.6+Math.random()*.8});
 if(STREAKS.length>want)STREAKS.length=Math.floor(want);
 WX.clearRect(0,0,W,H);WX.lineCap='round';const col=p.rain_mmh>=.2?'170,210,255':(p.temp_c<0?'225,240,255':'255,255,255');
 for(const k of STREAKS){k.y-=v*k.s*dt;k.x+=Math.sin((k.y+k.x)/180)*12*dt*devicePixelRatio;if(k.y<-k.l){k.y=H+Math.random()*H*.2;k.x=Math.random()*W}
  const fade=Math.min(1,k.y/(H*.35));const len=k.l*(.6+w/60)*devicePixelRatio;
  WX.strokeStyle=`rgba(${col},${(k.a*fade).toFixed(3)})`;WX.lineWidth=1.2*devicePixelRatio;WX.beginPath();WX.moveTo(k.x,k.y);WX.lineTo(k.x,k.y+len);WX.stroke()}}
function near(h){let best=P[0],d=1e9;for(const q of P){const k=Math.abs(q.hours_ago-h);if(k<d){d=k;best=q}}return best}
let lastPanel=0;function panel(h,p,now){if(now-lastPanel<350)return;lastPanel=now;const q=near(h),n=q.near;
 let place=n?(n.km<8?'Over '+n.name:`${Math.round(n.km)} km from ${n.name}`):(q.region||(q.land?'Over land':'Over open water')),sub=n?(n.country||''):(q.region?(q.marine?'open water':'wild country, no towns nearby'):`${Math.abs(p.lat).toFixed(1)}°${p.lat>=0?'N':'S'}, ${Math.abs(p.lon).toFixed(1)}°${p.lon>=0?'E':'W'}`);
 if(n&&q.region&&!q.marine)sub+=(sub?' · ':'')+q.region;
 const sp=q.place;if(!n&&sp&&sp.km<=30){if(sp.kind==='district'){place=sp.name;sub=['district',sp.area,sp.country].filter(Boolean).join(' · ')}else{place=(sp.km<6?'Over ':`${sp.km} km from `)+sp.name;sub=[sp.area,sp.country].filter(Boolean).join(', ')+(q.region&&!q.marine?' · '+q.region:'')}}
 const utc=ARR-h*3600e3,loc=new Date(utc+p.lon/15*3600e3),hh=loc.getUTCHours(),mm=String(loc.getUTCMinutes()).padStart(2,'0');
 a_place.textContent=place;a_sub.textContent=`${sub} · ~${hh}:${mm} local ${hh>=6&&hh<18?'☀':'☾'} · ${when(h)}`;
 const f=(v,u,d=0)=>v==null?'n/a':(+v).toFixed(d)+u;
 a_w.textContent=f(p.wind_kmh,' km/h');a_g.textContent=f(q.gust_kmh,' km/h');a_t.textContent=f(p.temp_c,' °C',1);a_h.textContent=f(q.rh,'%');
 a_r.textContent=q.snowfall?'snow':(p.rain_mmh>=.05?p.rain_mmh.toFixed(1)+' mm/h':'dry');a_v.textContent=f(q.visibility_km,' km',1);
 const A=q.aqi;document.getElementById('a_aq').innerHTML=A==null?'':`<i style="background:${aqcol(A)}"></i><span>Air quality <b>AQI ${A}</b> · ${q.air}${q.pm25!=null?` <small>PM2.5 ${q.pm25}</small>`:''}</span>`;
 const fl=(q.feels||[])[0];document.getElementById('a_feel').textContent=fl?`“${fl.charAt(0).toUpperCase()+fl.slice(1)}”`:'';
 const hz=q.hazards||[];a_hz.innerHTML=hz.length?hz.map(x=>`<span class=chip>⚠ ${x}</span>`).join(''):'<span class=calm>No hazards right here, right now</span>'}
const DW=(J.downwind&&J.downwind.towns_list)||[];let dwShown=-1,dwLast=0;
const dwCol=h=>h<=24?'#ff6b6b':h<=48?'#ff9f5a':'#ffd36b';
function futureHours(h){return BOTH?MID-h:FWD?HRS-h:-1}
function downwindLayer(h,now,force){if(!DW.length||(!force&&now-dwLast<300))return;dwLast=now;const fh=futureHours(h);const on=DW.filter(t=>t.reached_in_hours<=fh);
 if(on.length===dwShown&&!force)return;const prev=dwShown;dwShown=on.length;
 map.getSource('dwn').setData({type:'FeatureCollection',features:on.map(t=>({type:'Feature',properties:{r:Math.max(4,Math.min(22,Math.sqrt(t.people_estimate||15000)/38)),c:t.aqi_arriving!=null?aqcol(t.aqi_arriving):dwCol(t.reached_in_hours)},geometry:{type:'Point',coordinates:[t.lon,t.lat]}}))});
 const ppl=on.reduce((a,t)=>a+(t.people_estimate||0),0);document.getElementById('h_ppw').style.display=fh>0?'block':'none';document.getElementById('h_pp').textContent=ppl>=1e6?(ppl/1e6).toFixed(1)+'M':ppl.toLocaleString();
 if(prev>=0)on.slice(prev).filter(t=>(t.people_estimate||0)>=100000).forEach(t=>entry(`Reaches <b>${t.name}</b>`,`${when(MID?MID-t.reached_in_hours:HRS-t.reached_in_hours)} · ${t.population?t.population.toLocaleString()+' people':'town'}`,'reach'))}
function frame(now){if(!running)return;const dt=Math.min(.05,(now-last)/1000);last=now;
 if(now>pausedUntil){const sp=Math.max(1,at(h).wind_kmh);h=Math.max(0,h-Math.min(6,Math.max(.25,KMPS/sp))*dt)}
 const p=at(h),q=at(Math.max(0,h-.5));brg=brg+((bearing(p,q)-brg+540)%360-180)*.05;
 // trail + head
 const done=P.filter(x=>x.hours_ago>=h).map(x=>[x.lon,x.lat]);done.push([p.lon,p.lat]);
 const seg=[];for(let i=1;i<P.length&&P[i].hours_ago>=h;i++)seg.push({type:'Feature',properties:{c:HASAQ?aqcol(P[i].aqi):tcol(P[i].temp_c)},geometry:{type:'LineString',coordinates:[[P[i-1].lon,P[i-1].lat],[P[i].lon,P[i].lat]]}});
 map.getSource('ribbon').setData({type:'FeatureCollection',features:seg});
 if(J.swarm){const k=Math.max(1,Math.ceil(HRS-h)+1);map.getSource('swarm').setData({type:'FeatureCollection',features:J.swarm.map(c=>({type:'Feature',geometry:{type:'LineString',coordinates:c.slice(0,Math.min(k,c.length)).length>1?c.slice(0,Math.min(k,c.length)):[c[0],c[0]]}}))});
  map.getSource('swarmhead').setData({type:'FeatureCollection',features:J.swarm.map(c=>({type:'Feature',geometry:{type:'Point',coordinates:c[Math.min(k,c.length)-1]}}))})}
 if(Math.floor(h)!==lastHour){lastHour=Math.floor(h);map.getSource('night').setData(night(ARR-h*3600e3))}
 map.getSource('trail').setData({type:'Feature',geometry:{type:'LineString',coordinates:done}});map.getSource('head').setData({type:'Point',coordinates:[p.lon,p.lat]});
 if(puffMk){puffMk.setLngLat([p.lon,p.lat]);
  puffEl.classList.toggle('cold',p.temp_c<8);puffEl.classList.toggle('hot',p.temp_c>27);puffEl.classList.toggle('rain',p.rain_mmh>=.2)}
 if(LINES&&!speaking)for(const l of LINES){if(!spoken.has(l.id)&&l.hours_ago>=h&&l.kind!=='arrive'){spoken.add(l.id);speak(l,now);break}}
 if(now>pausedUntil||mode==='dive')puff(p,brg,p.wind_kmh);parts.forEach(t=>{t.lat+=t.dl;t.lon+=t.dn;t.age+=dt});parts=parts.filter(t=>t.age<2.2);
 map.getSource('air').setData({type:'FeatureCollection',features:parts.map(t=>({type:'Feature',properties:{r:1.4+t.age*2.2,o:Math.max(0,.75-t.age/2.2),c:t.c},geometry:{type:'Point',coordinates:[t.lon,t.lat]}}))});
 if(mode==='follow')map.jumpTo({center:[p.lon,p.lat],bearing:brg,pitch:62,zoom:J.total_km>1500?6.3:7.4});
 if(mode==='follow')windfx(p,dt);else WX.clearRect(0,0,WFX.width,WFX.height);
 // HUD
 h_km.textContent=Math.round(p.km).toLocaleString();h_w.textContent=p.wind_kmh.toFixed(0);h_c.textContent=p.temp_c.toFixed(1);if(HASAQ){const nq=near(h);h_r.textContent=nq.aqi==null?'—':nq.aqi;h_r.style.color=aqcol(nq.aqi);document.getElementById('h_rl').textContent='air quality (AQI)'}else h_r.textContent=p.rain_mmh.toFixed(1);panel(h,p,now);downwindLayer(h,now);
 // sound: gentle pentatonic plucks; pitch from temperature, tempo from wind, rain -> droplet chimes
 if(now-pulse>Math.max(260,1300-p.wind_kmh*13)){pulse=now;beat++;const deg=Math.max(0,Math.min(PENTA.length-1,Math.round((p.temp_c+10)/3.5)));
  const base=261.63*Math.pow(2,PENTA[deg]/12);pluck(base,.05,1.4);if(beat%4===0)pluck(base*1.5,.025,1.8);if(beat%8===0)pluck(base/2,.03,2.2)}
 if(p.rain_mmh>=.2&&Math.random()<.06)chime();
 // events + stops
 (J.events||[]).forEach((e,k)=>{if(!evShown.has(k)&&e.hours_ago>=h&&e.kind!=='arrive'){evShown.add(k);entry(e.text,`${when(e.hours_ago)}`,e.kind);if(e.kind==='coast'&&now>pausedUntil)say(e.text.includes('to sea')?'Out over open water':'Landfall',`${when(e.hours_ago,1)}`,2200);if(e.kind==='region'&&now>pausedUntil)say(e.text.charAt(0).toUpperCase()+e.text.slice(1),`${when(e.hours_ago,1)}`,2400);if(e.kind==='rain'&&now>pausedUntil)say('Through the rain',`${when(e.hours_ago,1)}`,2200);if(e.kind==='here'){pausedUntil=Math.max(pausedUntil,now+4200);say(`Right now · over ${J.name}`,(J.here&&J.here.headline)||'',4000)}}});
 STOPS.forEach((s,k)=>{if(!dived.has(k)&&s.hours_ago>=h&&now>pausedUntil){dived.add(k);dive(s)}});
 if(h<=0&&now>pausedUntil){running=false;finish();return}
 requestAnimationFrame(frame)}
function finish(){downwindLayer(0,performance.now(),true);const b=new maplibregl.LngLatBounds();P.forEach(p=>b.extend([p.lon,p.lat]));(J.swarm||[]).forEach(c=>c.forEach(x=>b.extend(x)));
 map.fitBounds(b,{padding:120,pitch:0,bearing:0,duration:3500});
 if((FWD||BOTH)&&J.downwind)say(`${J.downwind.towns.toLocaleString()} towns · ${J.downwind.people.toLocaleString()} people downwind`,`${J.downwind.towns_within_24h} towns (${J.downwind.people_within_24h.toLocaleString()} people) within the first 24 hours`,4800);else say(J.swarm?`${J.swarm.length} neighbouring breaths. Each took its own road.`:'Home.',J.swarm?`They started a median ${J.swarm_spread_km} km apart, and all arrived in __NAME__.`:'',4200);
 setTimeout(finish2,4600)}
function arrLocal(hAhead,lon){const t0=Date.parse(J.now_utc||J.release_utc);const d=new Date(t0+hAhead*3600e3+lon/15*3600e3);
 return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getUTCDay()]+' ~'+String(d.getUTCHours()).padStart(2,'0')+':00'}
const fmtP=n=>n>=1e6?(n/1e6).toFixed(1)+' million':Math.round(n).toLocaleString();
const mi=k=>Math.round(k*0.621371).toLocaleString(),km=k=>Math.round(k).toLocaleString();
function stats(){const T=P.map(p=>p.temp_c),A=P.filter(p=>p.aqi!=null),W=P.reduce((a,p)=>p.wind_kmh>a.wind_kmh?p:a,P[0]);
 const rain=P.reduce((a,p)=>a+(p.temp_c>1?p.rain_mmh:0),0),snow=P.reduce((a,p)=>a+(p.temp_c<=1?p.rain_mmh:0),0),bad=A.filter(p=>p.aqi>=151).length,sc=[...new Set((J.settlements||[]).map(x=>x.country).filter(Boolean))],cc=sc.length?sc:((J.passport&&J.passport.countries)||[]);
 const seas=[...new Set(P.filter(p=>p.marine&&p.region).map(p=>p.region))];
 return {tmin:Math.min(...T),tmax:Math.max(...T),rain,snow,wind:W.wind_kmh,amin:A.length?Math.min(...A.map(p=>p.aqi)):null,amax:A.length?Math.max(...A.map(p=>p.aqi)):null,bad,countries:cc.length,seas}}
const DIC={snow:'❄',emptiness:'🏜',nearest_people:'🧭',coldest:'🥶',warmest:'🔆',cleanest:'🍃',dirtiest:'😷',unhealthy_hours:'⏱',here_vs_journey:'📍',fastest:'💨',rain:'🌧',seas:'🌊'};
function placesOnTheWay(){const seen=new Set(),out=[];
 (J.places||[]).forEach(s=>{if(!seen.has(s.name)){seen.add(s.name);out.push({name:s.name,h:s.hours_ago,big:true})}});
 (J.settlements||[]).forEach(s=>{if(!seen.has(s.name)){seen.add(s.name);out.push({name:(s.kind==='district'?'🗺 ':'')+s.name,h:MID?MID-s.rel_h:0,big:false})}});
 return out.sort((a,b)=>b.h-a.h).slice(0,18)}
function reportText(){const D=J.downwind||{},H=J.here,S=stats(),L=[];
 L.push(`Biography of a Breath · the air passing over ${J.name} (NOAA GFS run ${(J.now_utc||J.release_utc).slice(0,16).replace('T',' ')} UTC)`);
 if(BOTH)L.push(`Route: ${J.start_label} → ${J.name} (now) → ${J.end_label}. ${km(J.past_km)} km (${mi(J.past_km)} mi) in the last 72 h, ${km(J.future_km)} km (${mi(J.future_km)} mi) in the next 72 h.`);
 if(H&&H.headline)L.push('Right here: '+H.headline);
 L.push(`Weather on the way: ${S.tmin.toFixed(1)} to ${S.tmax.toFixed(1)} °C, ~${S.rain.toFixed(1)} mm of rain${S.snow>=.5?` and ~${S.snow.toFixed(1)} mm as snow`:''}, strongest wind ${Math.round(S.wind)} km/h.`);
 if(S.amin!=null)L.push(`Air quality on the way: AQI ${S.amin} to ${S.amax}${S.bad?`, ${S.bad} hours unhealthy`:''}.`);
 (J.discoveries||[]).forEach(d=>L.push('• '+d.text));
 if(D.towns)L.push(`Next 72 h: reaches ${D.towns} towns (~${fmtP(D.people)} people); within 24 h: ${D.towns_within_24h} towns (~${fmtP(D.people_within_24h)}).`);
 else if(D.nearest_town||J.nearest_town){const n=D.nearest_town||J.nearest_town;L.push(`No town of 15,000+ people breathes this air in the next 72 h. Nearest: ${n.name}, ${n.km_from_path} km from the path.`)}
 (D.towns_list||[]).slice(0,10).forEach(t=>L.push(`- ${t.name}, ${t.country}: ${arrLocal(t.reached_in_hours,t.lon)} local (in ${Math.max(1,Math.round(t.reached_in_hours))} h)${t.population?', '+t.population.toLocaleString()+' people':''}${t.aqi_arriving!=null?', AQI '+t.aqi_arriving+' arriving':''}`));
 L.push('Open-data screening view (NOAA GFS on AWS Open Data, CAMS air quality, Overture Maps, Amazon Location), not an official dispersion forecast.');L.push(location.href);return L.join('\n')}
function impactCard(){document.getElementById('hud').style.opacity=0;const D=J.downwind||{},H=J.here,S=stats(),box=document.querySelector('#passport .glass');box.classList.add('impact');
 const T=(D.towns_list||[]).slice(0,10),mx=Math.max(1,...T.map(t=>t.people_estimate||0)),n=D.nearest_town||J.nearest_town;
 const route=BOTH?`<div class=route><div><span>3 days ago</span><b>${J.start_label}</b></div><i>→ ${km(J.past_km)} km →</i><div class=now><span>right now</span><b>${J.name}</b></div><i>→ ${km(J.future_km)} km →</i><div><span>in 3 days</span><b>${J.end_label}</b></div></div>`:'';
 const tile=(v,l,c)=>`<div class=tile><b ${c?`style="color:${c}"`:''}>${v}</b><span>${l}</span></div>`;
 const tiles=`<div class="tiles six">${tile(`${km(J.total_km)} km`,`${mi(J.total_km)} miles in 6 days`)}${tile(`${S.tmin.toFixed(0)}° to ${S.tmax.toFixed(0)}°C`,'temperature on the way')}${S.snow>S.rain?tile(`${S.snow.toFixed(1)} mm`,'snow & sleet (water)'):tile(`${S.rain.toFixed(1)} mm`,'rain around Puff')}${tile(`${Math.round(S.wind)} km/h`,'strongest wind')}${S.amin!=null?tile(`AQI ${S.amin}–${S.amax}`,S.bad?`${S.bad} h unhealthy`:'air quality range',aqcol(S.amax)):''}${tile(`${S.countries||'—'}`,S.seas.length?`countries · ${S.seas.length} seas`:'countries')}</div>`;
 const disc=(J.discoveries||[]).length?`<h3>Puff's discoveries</h3><ul class=disc>${J.discoveries.map(d=>`<li><span>${DIC[d.kind]||'✦'}</span>${d.text}</li>`).join('')}</ul>`:'';
 const pl=placesOnTheWay();const way=pl.length?`<h3>Places on the way</h3><p class=fine style="margin:-2px 0 8px">Towns of 15,000+ people (outlined), villages and 🗺 districts named by Amazon Location Service</p><div class=chips2>${pl.map(x=>`<span class="pc${x.big?' big':''}">${x.name}<small>${when(x.h)}</small></span>`).join('')}</div>`:'';
 const dw=D.towns?`<h3>Who breathes this air next</h3><div class=tiles><div class="tile t24"><b>${fmtP(D.people_within_24h)}</b><span>people · ${D.towns_within_24h} towns · 24 h</span></div><div class="tile t48"><b>${fmtP(D.people_within_48h||0)}</b><span>people · 48 h</span></div><div class="tile t72"><b>${fmtP(D.people)}</b><span>people · ${D.towns} towns · 72 h</span></div></div>
   <div class=tl>${T.map(t=>`<div class=tlr><div class=when><b>${arrLocal(t.reached_in_hours,t.lon)}</b><br>in ${Math.max(1,Math.round(t.reached_in_hours))} h</div><div><b>${t.name}</b> <span style="color:var(--dim)">${t.country}</span><div class=bar><i style="width:${Math.max(4,100*(t.people_estimate||0)/mx)}%;background:${t.aqi_arriving!=null?aqcol(t.aqi_arriving):dwCol(t.reached_in_hours)}"></i></div></div><div class=pop>${t.population?t.population.toLocaleString()+' people':'town'}${t.aqi_arriving!=null?`<br><span class=aqc style="border-color:${aqcol(t.aqi_arriving)};color:${aqcol(t.aqi_arriving)}">AQI ${t.aqi_arriving}</span>`:''}</div></div>`).join('')}</div>
   ${(()=>{const bad=(D.towns_list||[]).filter(t=>(t.aqi_arriving||0)>=151);return bad.length?`<div class=why style="border-color:rgba(255,90,90,.45);background:rgba(255,90,90,.1)">⚠ This air arrives <b>unhealthy (AQI 151+)</b> in <b>${bad.length}</b> towns, home to ~<b>${fmtP(bad.reduce((a,t)=>a+(t.people_estimate||0),0))}</b> people.</div>`:''})()}
   <div class=why>If smoke, a gas leak or crop-burning smoke started at ${J.name} now, these are the people to warn first, in this order.</div>`
  :`<h3>Who breathes this air next</h3><div class="why empty">🏜 <b>No town of 15,000+ people breathes this air in the next 72 hours.</b>${n?` The nearest is <b>${n.name}</b>${n.country?`, ${n.country}`:''}${n.population?` (${n.population.toLocaleString()} people)`:''}, ${n.km_from_path} km from Puff's path.`:''} This is some of the emptiest air on Earth.</div>`;
 box.innerHTML=`<button class=x id=b_close aria-label="Close report" title="Close">×</button><p class=kick>Journey report</p><h2>The life of this breath</h2>${route}
  ${H&&H.headline?`<p class=lede>☁ Right now at <b>${J.name}</b>: ${H.headline}</p>`:''}${tiles}${disc}${way}${dw}
  <div class=acts><button id=b_copy>Copy report</button><button id=b_share class=ghost>Share</button><button class=ghost onclick="location.href=location.pathname">Try another place</button></div>
  <p class=fine>NOAA GFS winds (AWS Open Data) · air quality: CAMS via Open-Meteo · towns: Overture Maps · settlements: Amazon Location Service. A screening view for awareness, not an official dispersion forecast.</p>`;
 document.getElementById('b_copy').onclick=async e=>{try{await navigator.clipboard.writeText(reportText());e.target.textContent='Copied ✓'}catch(_){e.target.textContent='Copy failed'}};
 document.getElementById('b_share').onclick=async e=>{const d={title:'Biography of a Breath · '+J.name,text:reportText(),url:location.href};try{if(navigator.share)await navigator.share(d);else{await navigator.clipboard.writeText(location.href);e.target.textContent='Link copied ✓'}}catch(_){}};
 passport.style.display='grid';rp_card.style.display='none';
 document.getElementById('b_close').onclick=closeReport;
 if(!window.rpBound){window.rpBound=1;
  passport.addEventListener('click',e=>{if(e.target===passport&&box.classList.contains('impact'))closeReport()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&passport.style.display==='grid'&&box.classList.contains('impact'))closeReport()});
  rp_card.onclick=openReport;rp_card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openReport()}};
  addEventListener('resize',placeRp)}}
function placeRp(){const a=document.getElementById('agent').getBoundingClientRect();rp_card.style.left=a.left+'px';rp_card.style.top=(a.bottom+8)+'px';rp_card.style.width=a.width+'px'}
function closeReport(){passport.style.display='none';placeRp();rp_card.style.display='block';rp_card.focus({preventScroll:true})}
function openReport(){rp_card.style.display='none';passport.style.display='grid'}
function finish2(){const al=(LINES||[]).find(l=>l.kind==='arrive');if(al)speak(al,performance.now());const pp=J.passport||{};
 if(BOTH||(FWD&&J.downwind)){impactCard();return}p_sum.innerHTML=`Your breath travelled <b>${Math.round(J.total_km).toLocaleString()} km</b> in ${HRS} hours, through <b>${(pp.countries||[]).length}</b> ${(pp.countries||[]).length===1?'country':'countries'} and past <b>${(pp.towns_20k_plus||pp.towns_15k_plus||STOPS.length).toLocaleString()}</b> towns.`;
 p_stamps.innerHTML=(pp.countries||[]).map(c=>`<span class=stamp>${c}</span>`).join('')+STOPS.map(s=>`<span class=stamp>${s.name}</span>`).join('');passport.style.display='grid'}
document.getElementById('play').onclick=()=>{audio();if(LINES)LINES.forEach(decodeLine);document.getElementById('start').classList.add('gone');document.getElementById('hud').style.opacity=1;document.getElementById('agent').classList.add('on');setTimeout(()=>document.getElementById('hint').classList.add('on'),9000);entry(BOTH?`Following the air that passes <b>__NAME__</b>`:`Released over <b>__NAME__</b>`,BOTH?'from 72 h ago to 72 h ahead':'now','start');
 const first=STOPS[0];if(BOTH){say('This is the air passing over __NAME__ right now.','where did it come from, and where will it go?',2600);setTimeout(()=>say(`72 hours ago, it was ${first&&first.hours_ago>HRS-6?'over '+first.name:(P[0].land?'over land':'over the sea')}.`,`Let's follow its whole life.`,2600),2800)}else if(FWD)say('This is the air leaving __NAME__ right now.','the latest NOAA forecast',2600);else say('This is the air that reached __NAME__ at __ARR__.','the latest NOAA weather run',2600);
 if(!BOTH)setTimeout(()=>FWD?say('Where will it go, and who breathes it next?',`Let's follow it for ${HRS} hours.`,2600):say(`${HRS} hours ago, it was ${first&&first.hours_ago>HRS-6?'over '+first.name:(P[0].land?'over land':'over the sea')}.`,`Let's follow it home.`,2600),2800);
 map.getSource('night').setData(night(ARR-HRS*3600e3));
 map.flyTo({center:[P[0].lon,P[0].lat],zoom:J.total_km>1500?6.3:7.4,pitch:62,duration:5400,essential:true});const t0=performance.now();
 (function wait(){if(LINES!==null||performance.now()-t0>22000){if(LINES===null)LINES=[];running=true;last=performance.now();requestAnimationFrame(frame)}else{if(performance.now()-t0>5600)say('Puff is remembering the journey…','writing the story from live weather',1500);setTimeout(wait,1600)}})()};
</script></body></html>"""
for k, v in {"__NAME__": J["name"], "__ARR__": J["arrival_utc"][:16].replace("T", " ") + " UTC", "__HRS__": str(int(J["points"][0]["hours_ago"])),
             "__LEVEL__": "air at ground level" if J["level"].startswith("10") else "air ~1.5 km up", "__KM__": f"{J['total_km']:,.0f}", "__NSTOPS__": str(len(J.get("places", []))), "__STYLE__": STYLE, "__DATA__": json.dumps(J)}.items():
    html = html.replace(k, v)
out = pathlib.Path(sys.argv[1]).with_name(pathlib.Path(sys.argv[1]).name.replace("journey_", "studio_")).with_suffix(".html")
out.write_text(html); print("Open in your browser:", out)
