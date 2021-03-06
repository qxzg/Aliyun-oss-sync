import json

with open('sha256-rebuild.json', 'r') as fobj:
    nsha = json.load(fobj)
with open('sha256-old.json', 'r') as fobj:
    osha = json.load(fobj)

dif = osha.keys() - nsha.keys()
for i in iter(dif):
    print(osha[i])