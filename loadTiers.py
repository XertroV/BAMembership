#!/usr/bin/python

'''loadTiers.py will read from loadTiers.json and write these into the redis database.'''

import json
from membershipAdmin import *

with open('loadTiers.json','r') as f:
	tiersToLoad = json.load(f)
ttl = tiersToLoad

validFields = [
	'shortName',
	'description',
	'cost',
	'duration',
	'founding',
	'suggestedSize',
	'active',
	]
	
	
# this should eventually be replaced by addTier in membershipAdmin
ids = tiersToLoad.keys()
ids.sort()
maxId = max([int(i) for i in ids])
r.set('%s:tiers:counter' % orgName, str(maxId))
print 'counter set to', maxId
for tierId in ids:
	t = tierId
	addTier(ttl[t]['shortName'],ttl[t]['description'],ttl[t]['cost'],ttl[t]['duration'],ttl[t]['founding'],ttl[t]['suggestedSize'],t)
	if ttl[t]['active'] == 'true':
		activateTier(t)
	
	
