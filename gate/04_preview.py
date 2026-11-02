"""Gate step 4: one-file preview that animates the journey on a map and plays the
data as sound (temperature -> pitch, wind -> pulse rate, rain -> soft noise).
Usage: python gate/04_preview.py out/journey_Delhi_10.json  -> out/preview_Delhi_10.html"""
import json, sys, pathlib
J = json.load(open(sys.argv[1]))
html = """<!doctype html><meta charset=utf-8><title>Breath preview: NAME</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel=stylesheet>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>body{margin:0;font:14px system-ui;background:#0b1020;color:#e8ecf4}#m{position:absolute;inset:0}
#p{position:absolute;left:12px;top:12px;max-width:380px;background:#0b1020e6;padding:12px 14px;border-radius:10px}
button{font:inherit;padding:8px 14px;border-radius:8px;border:0;background:#7cc4ff;color:#06101f;cursor:pointer}
#o{font-variant-numeric:tabular-nums;margin:8px 0}#e{opacity:.9}</style>
<div id=m></div><div id=p><b>NAME</b> &middot; LEVEL &middot; arrived ARR<br>
<div id=o>press play</div><button id=b>&#9654; Release the breath</button><div id=e></div></div>
<script>
const J=DATA, P=J.points, E=J.events, PL=J.places||[];
const map=new maplibregl.Map({container:'m',style:'https://demotiles.maplibre.org/style.json',center:[P[0].lon,P[0].lat],zoom:4});
map.on('load',()=>{map.addSource('path',{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:P.map(p=>[p.lon,p.lat])}}});
 map.addLayer({id:'path',type:'line',source:'path',paint:{'line-color':'#7cc4ff','line-width':3,'line-opacity':.5}});
 const b=new maplibregl.LngLatBounds();P.forEach(p=>b.extend([p.lon,p.lat]));map.fitBounds(b,{padding:80});
 PL.forEach(s=>new maplibregl.Marker({color:'#ffd27c',scale:.6}).setLngLat([s.lon,s.lat]).setPopup(new maplibregl.Popup().setText(s.name+' — '+s.hours_ago+' h ago, '+s.temp_c+' C')).addTo(map));});
const dot=new maplibregl.Marker({color:'#fff'});
const scale=[0,2,4,7,9,12,14,16,19,21,24];
document.getElementById('b').onclick=()=>{
 const ac=new AudioContext(), g=ac.createGain(); g.gain.value=.12; g.connect(ac.destination);
 const osc=ac.createOscillator(); osc.type='triangle'; osc.connect(g); osc.start();
 const nb=ac.createBuffer(1,ac.sampleRate,ac.sampleRate), d=nb.getChannelData(0); for(let i=0;i<d.length;i++)d[i]=Math.random()*2-1;
 const DUR=30000, t0=performance.now(); let lastPulse=0, shown=new Set(); dot.setLngLat([P[0].lon,P[0].lat]).addTo(map);
 (function f(now){const x=Math.min(1,(now-t0)/DUR), i=Math.min(P.length-1,Math.floor(x*(P.length-1))), p=P[i];
  dot.setLngLat([p.lon,p.lat]);
  const deg=Math.max(0,Math.min(10,Math.round((p.temp_c+5)/4))); osc.frequency.setTargetAtTime(220*Math.pow(2,scale[deg]/12),ac.currentTime,.05);
  const gap=Math.max(120,900-p.wind_kmh*12); if(now-lastPulse>gap){lastPulse=now;g.gain.setTargetAtTime(.18,ac.currentTime,.01);g.gain.setTargetAtTime(.08,ac.currentTime+.05,.08);}
  if(p.rain_mmh>=0.2){const s=ac.createBufferSource(),ng=ac.createGain();ng.gain.value=Math.min(.15,.03+p.rain_mmh*.05);s.buffer=nb;s.connect(ng);ng.connect(ac.destination);s.start();s.stop(ac.currentTime+.04);}
  document.getElementById('o').textContent=`-${p.hours_ago.toFixed(0)} h · ${p.km_from_start.toFixed(0)} km · ${p.wind_kmh} km/h · ${p.temp_c} °C · ${p.rh}% · rain ${p.rain_mmh} mm/h`;
  E.forEach((e,k)=>{if(!shown.has(k)&&e.hours_ago>=p.hours_ago){shown.add(k);document.getElementById('e').innerHTML+=`<div>−${e.hours_ago.toFixed(0)} h: ${e.text}</div>`;}});
  if(x<1)requestAnimationFrame(f);else{osc.stop();}})(t0);};
</script>"""
for k, v in {"NAME": J["name"], "LEVEL": J["level"], "ARR": J["arrival_utc"], "DATA": json.dumps(J)}.items():
    html = html.replace(k, v)
out = pathlib.Path(sys.argv[1]).with_name(pathlib.Path(sys.argv[1]).name.replace("journey_", "preview_")).with_suffix(".html")
out.write_text(html); print("Open in your browser:", out)
