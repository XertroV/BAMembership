#!/usr/bin/python

## CONFIG

logfilename = './signupLog.log'
# replace this string with your own
pubKey = 'xpub68BnL7sEYGy26evGwZ1ZSzafjwgdkWZ6WAc3vWR8zXPBpRPkvnC9eUkpqhXuHTcuDQihYgwD5nSWVGFUtuibLdcQrQuRfh3jX5q9L1cMaux'

# this is used in the redis db - must be exact
orgName = 'bitcoinAustralia'

## IMPORTS

from pycoin.wallet import Wallet
pubWallet = Wallet.from_wallet_key(pubKey)

from flask import Flask
from flask import request, render_template
app = Flask(__name__)

import logging
log_handler = logging.FileHandler(logfilename)
log_handler.setLevel(logging.WARNING)
app.logger.addHandler(log_handler)

from Crypto.Hash import SHA256
import time

# DEBUG STUFF FOR PAYMENTS
"""
## Payment stuff, should only record public key

#### DEBUG START ####
# You can generate a wallet in the following way
#privWallet = Wallet.from_master_secret('DebugDONOTUSE!!!!')
#privKey = privWallet.wallet_key(as_private=True)

# normally you'd set pubKey as a string, manually
pubKey = 'xpub661MyMwAqRbcEw72MGUKw2Yv1bnAg64pad8MhMuFHDUorGBTbCBk2GTRwLjxjbLkDfHFPwtDRrzJAmQdgoU7ZYEjEb3bs2BysnXKCaJa8h7'
#pubKey = privWallet.wallet_key(as_private=False)
pubWallet = Wallet.from_wallet_key(pubKey)
#### DEBUG END ####
"""

	
## FUNCTIONS

def getAddressFromRoot(index):
	global pubWallet
	address = pubWallet.subkey_for_path(index).bitcoin_address()
	return address
	
def getPaymentAddress(memberid):
	# considered using the 1/ subpath, but that's redundant and less safe:
	# payment request maker should only be able to generate addresses for payment, so all must be valid.
	return getAddressFromRoot(str(int(memberid)))
	
def sha256Hash(plaintext):
	h = SHA256.new()
	h.update(plaintext)
	return h.digest()
	
def escapeHtml(submittedData):
	# stackoverflow.com/questions/11548499
	escapes = {
		'\"':'&quot;',
		'\'':'&#39;',
		'<':'&lt;',
		'>':'&gt;',
	}
	submittedData = submittedData.replace('&','&amp;')
	for seq, esc in escapes.iteritems():
		submittedData = submittedData.replace(seq, esc)
	return submittedData
	
	
## CLASSES

class Database:
	def __init__(self):
		global orgName
		import redis
		self.r = redis.StrictRedis(host='localhost', port=6379, db=0)
		self.orgName = orgName
		
	def checkEmailExists(self, email):
		return self.r.exists('%s:members:emailHashToId:%s' % (self.orgName, sha256Hash(email)))
		
	def getNewMemberNumber(self): # increment usercounter and get new member number
		return self.r.incr('%s:members:counter' % self.orgName)
		
	def setUserDetails(self,details): # details is a dict of keyvalue pairs to set - keep at arms length from db
		'''details should be a dict with keys 'resAddress','name','email','id' '''
		memberid = int(details['id'])
		resAddress = details['resAddress']
		name = details['name']
		email = details['email']
		tier = details['tier']
		listPublicly = details['listPublicly']
		
		prefix = '%s:members:%d' % (self.orgName, memberid)
		paymentAddress = getPaymentAddress(memberid)
		self.r.set('%s:resAddress' % (prefix,), resAddress)
		self.r.set('%s:name' % (prefix,), name)
		self.r.set('%s:email' % (prefix,), email)
		self.r.set('%s:paymentAddress' % (prefix,), paymentAddress)
		self.r.set('%s:active' % (prefix,), 'false')
		self.r.set('%s:tier' % (prefix,), tier)
		self.r.set('%s:listPublicly' % (prefix,), listPublicly)
		
		self.r.set('%s:members:emailHashToId:%s' % (self.orgName, sha256Hash(email)), memberid)
		self.r.set('%s:members:paymentAddressToId:%s' % (self.orgName, paymentAddress), memberid) 
		
	def getFee(self, tierID):
		fee = self.r.get('%s:tiers:%s:cost' % (self.orgName, str(tierID)))
		if self.r.get('%s:tiers:%s:active' % (self.orgName, str(tierID))) != 'true':
			return None
		return fee
		
	def addPaymentRequest(self,memberid,amount,description,date):
		prefix = '%s:members:%d:payments' % (self.orgName, int(memberid))
		newPaymentID = self.r.incr('%s:counter' % prefix)
		prefix += ':%s' % newPaymentID
		self.r.set('%s:amount' % prefix, amount)
		self.r.set('%s:description' % prefix, description)
		self.r.set('%s:daterequested' % prefix, date)
		self.r.set('%s:paid' % prefix, 'false')
		
	def addComment(self,memberid,comment):
		path = '%s:members:%s:comments' % (self.orgName, str(memberid))
		self.r.rpush(path, comment)
		
	def listTiers(self,activeRequired=False):
		prefix = '%s:tiers' % self.orgName
		numTiers = self.r.get('%s:counter' % prefix)
		if numTiers == None:
			return []
		numTiers = int(numTiers)
		toRet = []
		for i in range(numTiers):
			if activeRequired:
				if self.r.get('%s:%d:active' % (prefix, i+1)) == 'false':
					continue
			toAdd = [i+1]
			for f in ['shortName','description','cost','duration','suggestedSize','active','founding']:
				toAdd += [self.r.get('%s:%d:%s' % (prefix, i+1, f))]
			toRet += [toAdd]
		return toRet
		
	def tierShortName(self,tierid):
		return self.r.get('%s:tier:%d:shortName' % (self.orgName, int(tierid))) 

## ROUTES (PAGES)

@app.route("/membership", methods=["POST","GET"])
def membership():
	if request.method == 'GET':
		tiers = db.listTiers()
		return render_template('form.html',tiers=tiers,totalTiers=len(tiers))
	elif request.method == 'POST':
		try:
			email = escapeHtml(request.form['memberEmail'])
			name = escapeHtml(request.form['memberName'])
			resAddress = escapeHtml(request.form['memberAddress'])
			allowed = escapeHtml(request.form['memberAllowed'])
			dontList = escapeHtml(request.form['memberPublic'])
			tier = int(request.form['memberTier'])
		except:
			return '{"error":"Submitted fields incorrect; general exception"}'
		if '' in [email, name, resAddress]:
			return '{"error":"One of name, email or address is blank"}'
		if db.checkEmailExists(email):
			return '{"error":"Email address already exists"}'
		if allowed != 'true':
			return '{"error":"You must be an Australian Resident or Citizen to join"}'
		if max([len(resAddress), len(email), len(name)]) > 512:
			return '{"error":"All fields must be less than 512 characters long."}'
		if db.getFee(tier) == None:
			return '{"error":"No Membership Selected."}'
		listPublicly = 'false' if dontList == 'true' else 'true'
			
		memberid = db.getNewMemberNumber()
		db.setUserDetails({
			'id':memberid,
			'resAddress':resAddress,
			'name':name,
			'email':email,
			'tier':tier,
			'listPublicly':listPublicly,
		})
		address = getPaymentAddress(memberid)
		amount = db.getFee(tier)
		comment = "Bitcoin%20Australia%20Membership"
		uri = "bitcoin:%s?amount=%s&label=%s" % (address, amount, comment)
		
		db.addPaymentRequest(memberid,amount,'Membership 365 days, tier %s' % str(tier),int(time.time()))
		
		return '{"address":"%s","amount":"%s","uri":"%s","error":"none"}' % (address, amount, uri)
		
@app.route("/memberlist")
def memberlist():
	activeTest = True
	if 'debug' in request.args and request.args['debug'] == 'true':
		activeTest = False
	maxid = int(db.r.get('%s:members:counter' % orgName))
	ret = ''
	for i in range(maxid):
		memberid = i+1
		if activeTest:
			if db.r.get('%s:members:%d:active' % (orgName, memberid)) != 'true':
				continue
			if db.r.get('%s:members:%d:listPublicly' % (orgName, memberid)) == 'false':
				continue
			ret += '%d | ' % memberid
			for stuff in ['name']:
				ret += db.r.get('%s:members:%d:%s' % (orgName, memberid, stuff))
			ret += '<br>'
		else:
			ret += '%d | ' % memberid
			for stuff in ['name','email','paymentAddress']:
				ret += db.r.get('%s:members:%d:%s' % (orgName, memberid, stuff)) + ' | '
			ret += '<br>'
	return ret	

## MAIN - RUN APP

if __name__ == "__main__":
	global db
	db = Database()
	app.run()
