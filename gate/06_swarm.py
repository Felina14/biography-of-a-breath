"""Companion breaths: rewind 24 extra parcels released in a ring around the city, so the
studio can show a river of air converging on it (and how much paths spread = uncertainty).
Usage: python gate/06_swarm.py out/journey_London_850.json"""
import importlib.util, json, math, sys
spec = importlib.util.spec_from_file_location("traj", "gate/02_trajectory.py"); tr = importlib.util.module_from_spec(spec); spec.loader.exec_module(tr)
J = json.load(open(sys.argv[1])); lev = "10" if J["level"].startswith("10") else "850"
end = J["points"][-1]; T = tr.T
paths = []
for k in range(24):
    r_km = 25 + 35 * (k % 3); ang = 2 * math.pi * k / 24
    la = end["lat"] + (r_km / 111.0) * math.cos(ang); lo = end["lon"] + (r_km / (111.0 * math.cos(math.radians(end["lat"])))) * math.sin(ang)
    t, h, pts = T[-1], -900.0, []
    for n in range(int((T[-1] - T[0]) / 900) + 1):
        if n % 4 == 0: pts.append([round(((lo + 180) % 360) - 180, 4), round(la, 4)])
        if t + h < T[0] or abs(la) > 85: break
        la, lo = tr.step(t, la, lo, h, lev); t += h
    pts.reverse(); paths.append(pts)
J["swarm"] = paths
spread = [tr.hav((p[0][1], p[0][0]), (J["points"][0]["lat"], J["points"][0]["lon"])) for p in paths]
J["swarm_spread_km"] = round(sorted(spread)[len(spread) // 2], 0)
json.dump(J, open(sys.argv[1], "w"), indent=1)
print(f"{len(paths)} companion breaths; median start {J['swarm_spread_km']:.0f} km from the main breath's start")
