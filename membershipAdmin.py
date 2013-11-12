#!/usr/bin/python

import sys
from pycoin.wallet import Wallet
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

# change these

orgName = 'bitcoinAustralia'

# debug or config vars

printRaw = False

# first entry in list should be the short human identifier (like a name)
dbmap = {
	"tiers":['shortName','description','cost','duration','founding','suggestedSize','active'],
	"members":['name','tier','active','activeFrom','activeFor','email','founding','paymentAddress'],
	"payments":['description','amount','daterequested','daterecieved','paid'],
}

## HELPER FUNCTIONS

def loopQuestion(question, validatorFunction):
	while True:
		try:
			ans = validatorFunction(raw_input(question))
			return ans
		except KeyboardInterrupt:
			sys.exit()
		except:
			pass

## WALLET FUNCTIONS

def printGeneratedHDPrivKeys():
	privKeyString = raw_input('Input privkey > ')
	fromIndex = loopQuestion('From index (starting at 1) > ', int)
	toIndex = loopQuestion('To index (inclusive) > ', int)
	smaller = min(fromIndex, toIndex)
	larger = max(fromIndex, toIndex)
	
	if smaller < 0:
		print 'Error: min index must be greater than or equal to 1'
		return
	
	genPrivateKeys(privKeyString, [str(i) for i in range(smaller, larger+1)])
	

def genPrivateKeys(privKey, listOfPaths=[]):
	privWallet = Wallet.from_wallet_key(privKey)
	print '%5s | %s | %s' % ('path', 'wif', 'addr')
	for path in listOfPaths:
		print '%5s | %s | %s' % (path, privWallet.subkey_for_path(path).wif(), privWallet.subkey_for_path(path).bitcoin_address())

## FUNCITONS - MAP TO COMMANDS

def endProgram():
	sys.exit()
	
def confirmWrite(loc, val):
	ans = ''
	while ans != 'y':
		print 'Warning!'
		print 'About to set the following:'
		print '%s -> %s' % (loc, val)
		ans = raw_input(' Confirm OKAY (press <y>); Ctrl-c or <n> to end > ')
		if ans == 'n':
			return False
	return True
	
def resetMemberCounter():
	def validator(v):
		return v == 'y'
	print 'WARNING: ABOUT TO RESET MEMBER COUNTER'
	print 'ALL DATA MAY BE LOST!'
	print 'THIS IS PROBABLY NOT WHAT YOU WANT TO DO!'
	print ''
	ans = raw_input('Reset the member counter? (y/n) (Ctrl-c to kill) > ')
	if ans != 'y':
		print 'Recieved %s; not \'y\' did not reset counter.' % ans
		return
	loc = '%s:members:counter' % orgName
	val = 0
	confirmWrite(loc,val)
	r.set(loc,val)
	print '%s -> %s SET' % (loc,str(val))
	print 'Done'
	
def getGeneric(itemType,itemPath):
	lastItem = r.get('%s:counter' % itemPath)
	lastItem = int(lastItem)
	toRet = [['id']+dbmap[itemType]]
	for i in range(lastItem):
		toAdd = [i+1]
		for info in dbmap[itemType]:
			toAdd += [r.get('%s:%d:%s' % (itemPath, i+1, info))]
		toRet += [toAdd]
	return toRet

def getMembers(activeTest=False):
	lastMember = r.get('%s:members:counter' % orgName)
	lastMember = int(lastMember)
	toRet = [] 
	toRet += [['id']+dbmap['members']]
	for i in range(lastMember):
		toAdd = [i+1]
		active = r.get('%s:members:%d:%s' % (orgName, i+1, 'active'))
		if activeTest:
			if active != 'true':
				continue
		for info in dbmap['members']:
			toAdd += [r.get('%s:members:%d:%s' % (orgName, i+1, info))]
		toRet += [toAdd]
	return toRet
	
def getActiveMembers():
	return getMembers(activeTest=True)

def getTiers():
	return getGeneric('tiers','%s:tiers' % orgName)
	totalTiers = r.get('%s:tiers:counter' % orgName)
	if totalTiers == None:
		return None
	totalTiers = int(totalTiers)
	toRet = []
	fields = dbmap['tiers']
	toRet += [['id']+fields]
	for i in range(totalTiers):
		toAdd = [i+1]
		for f in fields:
			toAdd += [r.get('%s:tiers:%d:%s' % (orgName, i+1, f))]
		toRet += [toAdd]
	return toRet
		
		
def getPayments(memberid):
	memberid = str(memberid)
	totalPayments = r.get('%s:members:%s:payments:counter' % (orgName, memberid))
	if totalPayments == None:
		return None
	totalPayments = int(totalPayments)
	toRet = []
	fields = dbmap['payments']
	toRet += [['id']+fields]
	for i in range(totalPayments):
		toAdd = [i+1]
		for f in fields:
			toAdd += [r.get('%s:members:%s:payments:%d:%s' % (orgName, memberid, i+1, f))]
		toRet += [toAdd]
	return toRet
	
def getComments(memberid):
	memberid = str(memberid)
	comments = r.get('%s:members:%s:comments' % (orgName, memberid))
	return comments
	
def printGeneric(name, toPrint):
	allItems = toPrint
	if allItems == None:
		print 'No %s; try add%s' % (name, name[:-1].capitalize())
		return
	for row in allItems:
		for item in row:
			if not printRaw:
				print '%10s |' % str(item)[:10],
			else:
				print '%s |' % str(item),
		print ''
			
def printTiers():
	printGeneric('tiers',getTiers())
	
def printMembers(activeTest=False):
	printGeneric('members',getMembers(activeTest=activeTest))
		
def printActiveMembers():
	printMembers(activeTest=True)
	
def printPayments():
	memberid = raw_input('Payments of what Member ID? > ')
	printGeneric('payments',getPayments(memberid))
	
def printComments():
	memberid = raw_input('Comments on which Member ID? > ')
	comments = getComments(memberid)
	for c in comments:
		print c
		
def numGeneric(itemType):
	return int(r.get('%s:%s:counter' % (orgName, itemType)))
		
def numTiers():
	return numGeneric('tiers')
	
def numMembers():
	return numGeneric('members')
	
def addTier():
	details = {}
	details['shortName'] = raw_input(' Short Name > ')
	details['description'] = raw_input(' Description > ')
	details['cost'] = raw_input(' Cost (in BTC) > ')
	details['duration'] = raw_input(' Duration (in seconds) > ')
	details['founding'] = ''
	while details['founding'] not in ['true','false']:
		details['founding'] = raw_input(' Is a founding member? (\'true\' or \'false\') > ')
	details['suggestedSize'] = raw_input(' Suggested Size (for organisations) > ')
	
	tierID = r.incr('%s:tiers:counter' % orgName)
	for k,v in details.iteritems():
		r.set('%s:tiers:%s:%s' % (orgName, tierID, k), v)
	r.set('%s:tiers:shortNameToID:%s' % (orgName, details['shortName']), tierID)
	r.rpush('%s:tiers:shortNameList' % orgName, details['shortName'])
	print 'Created tier with ID %s' % tierID
	print 'This tier is currently deactive. To activate, please use activateTier'
	
def activateTier():
	idToMod = raw_input('Tier ID to activate > ')
	r.set('%s:tiers:%s:active' % (orgName, idToMod), 'true')
	print 'Activated Tier %s: %s' % (idToMod, r.get('%s:tiers:%s:shortName' % (orgName, idToMod)))
	
def deactivateTier():
	idToMod = raw_input('Tier ID to deactivate > ')
	r.set('%s:tiers:%s:active' % (orgName, idToMod), 'false')
	print 'Deactivated Tier %s: %s' % (idToMod, r.get('%s:tiers:%s:shortName' % (orgName, idToMod)))
	
def activateMember():
	idToMod = raw_input('Member ID to activate > ')
	r.set('%s:members:%s:active' % (orgName, idToMod), 'true')
	print 'Activated Member %s: %s' % (idToMod, r.get('%s:members:%s:name' % (orgName, idToMod)))
	
def deactivateMember():
	idToMod = raw_input('Member ID to deactivate > ')
	r.set('%s:members:%s:active' % (orgName, idToMod), 'true')
	print 'Deactivated Member %s: %s' % (idToMod, r.get('%s:members:%s:name' % (orgName, idToMod)))
	
	
def modGeneric(itemType):
	if itemType == 'tiers':
		itemName = 'Tiers'
	elif itemType == 'members':
		itemName = 'Members'
	else:
		itemName = itemType
		
	nameField = dbmap[itemType][0]
	for i in range(numGeneric(itemType)):
		t = r.get('%s:%s:%d:%s' % (orgName, itemType, i+1, nameField))
		print '    %s. %s' % (i+1, t)
		
	idToMod = raw_input(' ID To Modify > ')
	
	print 'Fields:',
	for f in dbmap[itemType]:
		print f,
	print ''
		
	inputField = ''
	while inputField not in dbmap[itemType]:
		inputField = raw_input(' Field to modify > ')
		
	newValue = raw_input(' New Value > ')
	dbLocation = '%s:%s:%s:%s' % (orgName, itemType, idToMod, inputField)
	if not confirmWrite(dbLocation, newValue):
		print 'No write will happen - bailing out'
		return False
	r.set(dbLocation, newValue)
	
	print 'Generic Done'
	return (itemType,idToMod,inputField,newValue)
		
	
def modTier():
	itemType,idToMod,field,newValue = modGeneric('tiers')
	
	if field == 'shortName':
		r.set('%s:tiers:shortNameToID:%s' % (orgName, newValue), idToMod)
		r.rpush('%s:tiers:shortNameList' % orgName, newValue)
	
	print 'Custom Done'
	
def modMember():
	itemType,idToMod,field,newValue = modGeneric('members')
	
	if field == 'email':
		r.set('%s:members:emailHashToID:%s' % (orgName, sha256Hash(newValue)), idToMod)
		
	print 'Custom Done'
	
## HELP AND HELPERS

def printHelp():
	print """Use -raw as an argument to not format or truncate output
	Commands: """
	for i in functionMap.keys():
		print '%s,' % i,
	print ''

functionMap = {
	"printMembers":printMembers,
	"printActiveMembers":printActiveMembers,
	"printTiers":printTiers,
	"printPayments":printPayments,
	"printComments":printComments,
	"printGeneratedHDPrivKeys":printGeneratedHDPrivKeys,
	"help":printHelp,
	"exit":endProgram,
	"addTier":addTier,
	"modTier":modTier,
	"activateTier":activateTier,
	"deactivateTier":deactivateTier,
	"activateMember":activateMember,
	"deactivateMember":deactivateMember,
	"resetMemberCounter":resetMemberCounter,
}

## MAIN - RUN APP

def exCommand(command):
	if command not in functionMap.keys():
		print 'Error: command nonexistant.'
		printHelp();
	else:
		functionMap[command]()
	

if __name__ == "__main__":
	if len(sys.argv) > 1:
		if '-raw' in sys.argv:
			printRaw = True
			sys.argv.remove('-raw')
		command = sys.argv[1]
		exCommand(command)
		sys.exit()
	while True:
		command = raw_input('$> ')
		if command not in functionMap.keys():
			exCommand(command)
	
	
