#!/usr/bin/python

import sys, time
from pycoin.wallet import Wallet
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

from config import *

# change these

orgName = config['orgName']

# debug or config vars

printRaw = False

# first entry in list should be the short human identifier (like a name)
dbmap = {
	"tiers":['shortName','description','cost','duration','founding','suggestedSize','active'],
	"members":['name','tier','active','activeFrom','activeFor','email','founding','paymentAddress','listPublicly'],
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
			
def paymentAddressToMemberId(addr):
	'''return (<worked>,<payload>) as <bool>,<string>, like True,id or False,'nonexistant' '''
	path = '%s:members:paymentAddressToId:%s' % (orgName, addr)
	if not r.exists(path):
		return (False,'Nonexistant Address')
	memberId = r.get(path)
	return (True,memberId)
	
def scrapeKeys(loc,fields,idmax,idmin=1):
	'''Get all fields from loc:<id>:field - loop over id range, inclusive'''
	toRet = []
	for i in range(idmin,idmax+1):
		toAdd = [i]
		for field in fields:
			toAdd += [r.get('%s:%d:%s' % (loc,i,field))]
		toRet += [toAdd]
	return toRet

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
	
def acknowledgeWrite(loc, val):
	print 'Confirmed: %s -> %s' % (loc, val)
	
def addComment(memberid,comment):
	path = '%s:members:%s:comments' % (orgName, str(memberid))
	r.rpush(path, comment)
	
def requestMemberId():
	return loopQuestion('Member ID to activate > ', int)
	

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
		
def wifPrivKeyToXpub(privKey):
	privWallet = Wallet.from_master_secret(privKey)
	return (privWallet.wallet_key(as_private=False), privWallet.wallet_key(as_private=True))

## FUNCITONS - MAP TO COMMANDS

	
def resetMemberCounter():
	def validator(v):
		return v == 'y'
	print 'WARNING: ABOUT TO RESET MEMBER COUNTER'
	print 'ALL DATA MAY BE LOST!'
	print 'THIS IS PROBABLY NOT WHAT YOU WANT TO DO!'
	print 'DATA WILL BE LOST'
	ans = raw_input('Reset the member counter? (y/n) (Ctrl-c to kill) > ')
	if ans != 'y':
		print 'Recieved %s; not \'y\': did not reset counter.' % ans
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
	if lastMember == None:
		print 'No members yet.'
		return
	lastMember = int(lastMember)
	toRet = [] 
	toRet += [['id']+dbmap['members']]
	# custom implementation of scrapeKeys
	for i in range(1,lastMember+1):
		toAdd = [i]
		active = r.get('%s:members:%d:%s' % (orgName, i, 'active'))
		if activeTest:
			if active != 'true':
				continue
		for field in dbmap['members']:
			toAdd += [r.get('%s:members:%d:%s' % (orgName, i, field))]
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
	toRet += scrapeKeys('%s:tiers' % orgName, fields, totalTiers)
	return toRet
		
		
def getPayments(memberId):
	memberId = str(memberId)
	totalPayments = r.get('%s:members:%s:payments:counter' % (orgName, memberId))
	if totalPayments == None:
		return None
	totalPayments = int(totalPayments)
	toRet = []
	fields = dbmap['payments']
	toRet += [['id']+fields]
	toRet += scrapeKeys('%s:members:%s:payments' % (orgName, memberId), fields, totalPayments)
	return toRet
	
def getComments(memberId):
	memberId = str(memberId)
	comments = r.get('%s:members:%s:comments' % (orgName, memberId))
	return comments
	
def getMemberTier(memberId):
	memberId = str(memberId)
	tierId = r.get('%s:members:%s:tier' % (orgName, memberId))
	return tierId
	
def getGenericField(loc, idToGet, field):
	return r.get('%s:%s:%s' % (loc, str(idToGet), field))
	
def getTierField(tierId, field):
	loc = '%s:tiers' % orgName
	return getGenericField(loc, tierId, field)
	
def getMemberField(memberId, field):
	loc = '%s:members' % orgName
	return getGenericField(loc, memberId, field)
	
def setGenericField(loc, idToMod, field, value):
	return r.set('%s:%s:%s' % (loc, str(idToMod), field), value)
	
def setTierField(tierId, field, value):
	loc = '%s:tiers' % orgName
	return setGenericField(loc, tierId, field, value)
	
def setMemberField(memberId, field, value):
	loc = '%s:members' % orgName
	return setGenericField(loc, memberId, field, value)
	
	
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
	memberId = raw_input('Payments of what Member ID? > ')
	printGeneric('payments',getPayments(memberId))
	
def printComments():
	memberId = raw_input('Comments on which Member ID? > ')
	comments = getComments(memberId)
	for c in comments:
		print c
		
def numGeneric(itemType):
	return int(r.get('%s:%s:counter' % (orgName, itemType)))
		
def numTiers():
	return numGeneric('tiers')
	
def numMembers():
	return numGeneric('members')
	
def addTier(shortName=None,description=None,cost=None,duration=None,founding=None,suggestedSize=None,tierId=None):
	details = {}
	details['shortName'] = raw_input(' Short Name > ') if shortName == None else shortName
	details['description'] = raw_input(' Description > ') if description == None else description
	details['cost'] = raw_input(' Cost (in BTC) > ') if cost == None else cost
	details['duration'] = raw_input(' Duration (in seconds) > ') if duration == None else duration
	
	def getFounding():
		ans = ''
		while ans not in ['true','false']:
			ans = raw_input(' Is a founding member? (\'true\' or \'false\') > ')
		return ans
	details['founding'] = getFounding() if founding == None else founding
	
	details['suggestedSize'] = raw_input(' Suggested Size (for organisations) > ') if suggestedSize == None else suggestedSize
	
	if tierId == None:
		tierId = r.incr('%s:tiers:counter' % orgName)
	
	for k,v in details.iteritems():
		r.set('%s:tiers:%s:%s' % (orgName, tierId, k), v)
	r.set('%s:tiers:shortNameToId:%s' % (orgName, details['shortName']), tierId)
	r.rpush('%s:tiers:shortNameList' % orgName, details['shortName'])
	print 'Created tier with ID %s' % tierId
	print 'This tier is currently deactive. To activate, please use activateTier'
	
def activateTier(idToMod=None):
	if idToMod == None:
		idToMod = raw_input('Tier ID to activate > ')
	r.set('%s:tiers:%s:active' % (orgName, idToMod), 'true')
	print 'Activated Tier %s: %s' % (idToMod, r.get('%s:tiers:%s:shortName' % (orgName, idToMod)))
	
def deactivateTier():
	idToMod = raw_input('Tier ID to deactivate > ')
	r.set('%s:tiers:%s:active' % (orgName, idToMod), 'false')
	print 'Deactivated Tier %s: %s' % (idToMod, r.get('%s:tiers:%s:shortName' % (orgName, idToMod)))
	
def activateMember():
	print 'WARNING: you should probably be using extendMember'
	idToMod = requestMemberId()
	r.set('%s:members:%s:active' % (orgName, idToMod), 'true')
	print 'Activated Member %s: %s' % (idToMod, r.get('%s:members:%s:name' % (orgName, idToMod)))
	
def deactivateMember():
	idToMod = raw_input('Member ID to deactivate > ')
	r.set('%s:members:%s:active' % (orgName, idToMod), 'true')
	print 'Deactivated Member %s: %s' % (idToMod, r.get('%s:members:%s:name' % (orgName, idToMod)))
	
	
def modGeneric(itemType):
	itemType = itemType.rsplit(':',1)[-1]
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
		r.set('%s:tiers:shortNameToId:%s' % (orgName, newValue), idToMod)
		r.rpush('%s:tiers:shortNameList' % orgName, newValue)
	
	print 'Custom Done'
	
def modMember():
	itemType,idToMod,field,newValue = modGeneric('members')
	
	if field == 'email':
		r.set('%s:members:emailHashToId:%s' % (orgName, sha256Hash(newValue)), idToMod)
		
	print 'Custom Done'
	
def modPayment(memberId):
	itemType,idToMod,field,newValue = modGeneric('members:%s:payments' % memberId)

def requestAddressReturnMemberId():
	address = raw_input('Bitcoin address receiving payment > ')
	reply = paymentAddressToMemberId(address)
	if reply[1] == True:
		print 'Fail: %s' % reply[1]
		return None
	memberId = reply[1]
	return memberId
	
def registerPayment(memberId=None):
	if memberId == None:
		memberId = requestAddressReturnMemberId()
	if memberId == None:
		return None
	name = r.get('%s:members:%s:name' % (orgName, memberId))
	print 'Member: %s; %s' % (memberId, name)
	
	# get payment amount and use that to find what it's a payment for - one day.
	# payAmount = loopQuestion('Please enter the payment amount > ',float)
	possiblePayments = getPayments(memberId)
	printGeneric('possible payments', possiblePayments)
	
	paymentId = loopQuestion('Enter ID of payment to register as recieved > ',int)
	
	loc = "%s:members:%s:payments:%d:paid" % (orgName, memberId, paymentId)
	print '#'
	if r.get(loc) == 'true':
		print 'Already marked as paid. Aborting.'
		return None
	if not confirmWrite(loc,'true'):
		print 'Write not confirmed, will not mark payment as paid. End.'
		return None
	r.set(loc,'true')
	acknowledgeWrite(loc,'true')
	
	addComment(memberId,'Marked payment %s as paid.' % paymentId)
	
	return paymentId
	
def membershipPaymentCycle():
	# TODO
	# Maybe change the name
	# It will register a payment and activate a member and extend a member all at once.
	
	memberId = requestAddressReturnMemberId()
	paymentId = registerPayment(memberId)
	
	# extend user
	extendMember(memberId)
	
def extendMember(memberId=None):
	if memberId == None:
		memberId = requestMemberId()
	if memberId == None:
		print 'No memberId, bailing out.'
		return None
	tierId = getMemberTier(memberId)
	duration = getTierField(tierId,'duration')
	print 'Extending Member %s - %s' % (memberId, getMemberField(memberId, 'name'))
	# get active, if not active, activate and set activeFrom and activeFor
	# else, extend activeFor
	active = getMemberField(memberId,'active')
	addComment(memberId,'Extending user for %s sec' % duration)
	if active != 'true':
		print 'Member not active'
		print 'Activating and setting activeFrom to now and activeFor'
		setMemberField(memberId,'active','true')
		setMemberField(memberId,'activeFrom',int(time.time()))
		setMemberField(memberId,'activeFor',duration)
		acknowledgeWrite('active,activeFrom,activeFor','true,now,%s' % duration)
		print 'Member %s - %s active' % (memberId, getMemberField(memberId, 'name'))
		return
	print 'Member already active, incrementing activeFor'
	activeFor = r.incrby('%s:members:%s:activeFor' % (orgName, memberId), int(duration))
	acknowledgeWrite('activeFor',activeFor)	
	print 'Member %s - %s active' % (memberId, getMemberField(memberId, 'name'))
	return
	
def printWifPrivKeyToXpub():
	privkey = loopQuestion('Copypaste WIF privkey> ',str)
	print wifPrivKeyToXpub(privkey)
	
## DB MAINTENANCE

def exportDatabase():
	# TODO
	# need to collect members and tiers (and members:payments)
	# output as binary? maybe specify output file?
	# as there are possibly unsafe binary sequences in the data (is there?) some will need to be stored as hex (if it's an ascii file)
	# store everything as hex? it would make it a little difficult to read, and reading would be nice
	# raw hashes are stored, can't be ascii
	# they can be reconstructed though
	# why bother reconstructing?
	pass
	
	
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
	"printWifPrivKeyToXpub":printWifPrivKeyToXpub,
	"help":printHelp,
	"exit":endProgram,
	"addTier":addTier,
	"modTier":modTier,
	"activateTier":activateTier,
	"deactivateTier":deactivateTier,
	"activateMember":activateMember,
	"deactivateMember":deactivateMember,
	"modMember":modMember,
	"resetMemberCounter":resetMemberCounter,
	"registerPayment":registerPayment,
	"membershipPaymentCycle":membershipPaymentCycle,
	"extendMember":extendMember,
	"exportDatabase":exportDatabase,
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
		endProgram()
	while True:
		command = raw_input('$> ')
		if command not in functionMap.keys():
			exCommand(command)
	
	
