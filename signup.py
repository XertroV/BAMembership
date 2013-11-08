#!/usr/bin/python

## CONFIG

logfilename = './signupLog.log'
# replace this string with your own
pubKey = 'xpub661MyMwAqRbcEw72MGUKw2Yv1bnAg64pad8MhMuFHDUorGBTbCBk2GTRwLjxjbLkDfHFPwtDRrzJAmQdgoU7ZYEjEb3bs2BysnXKCaJa8h7'

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

# this is used in the redis db
orgName = 'bitcoinAustralia'
	
## FUNCTIONS

def getAddressFromRoot(index):
	global pubWallet
	address = pubWallet.subkey_for_path(index).bitcoin_address()
	return address
	
def getPaymentAddress(memberid):
	return getAddressFromRoot('1/'+str(memberid))
	
def sha256Hash(plaintext):
	h = SHA256.new()
	h.update(plaintext)
	return h.digest()
	
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
		
		self.r.set('%s:members:%d:resAddress' % (self.orgName, memberid), resAddress)
		self.r.set('%s:members:%d:name' % (self.orgName, memberid), name)
		self.r.set('%s:members:%d:email' % (self.orgName, memberid), email)
		self.r.set('%s:members:%d:paymentAddress' % (self.orgName, memberid), getPaymentAddress(memberid))
		self.r.set('%s:members:%d:active' % (self.orgName, memberid), 'false')
		
		self.r.set('%s:members:emailHashToId:%s' % (self.orgName, sha256Hash(email)), memberid)
	def getFee(self, tierID):
		fee = self.r.get('%s:tiers:%s:cost' % (self.orgName, str(tierID)))
		return fee
	def addPaymentRequest(self,memberid,amount,description,date):
		prefix = '%s:members:%d:payments' % (self.orgName, int(memberid))
		newPaymentID = self.r.incr('%s:counter' % prefix)
		prefix += ':%s' % newPaymentID
		self.r.set('%s:amount' % prefix, amount)
		self.r.set('%s:description' % prefix, description)
		self.r.set('%s:daterequested' % prefix, date)
		self.r.set('%s:paid' % prefix, 'false')
	def listTiers(self):
		prefix = '%s:tiers' % self.orgName
		numTiers = self.r.get('%s:counter' % prefix)
		if numTiers == None:
			return []
		numTiers = int(numTiers)
		toRet = []
		for i in range(numTiers):
			toAdd = [i+1]
			for f in ['shortName','description','cost','duration','suggestedSize','active']:
				toAdd += [self.r.get('%s:%d:%s' % (prefix, i+1, f))]
			toRet += [toAdd]
		return toRet

## ROUTES (PAGES)

@app.route("/membership", methods=["POST","GET"])
def membership():
	if request.method == 'GET':
		tiers = db.listTiers()
		return render_template('form.html',tiers=tiers)
	elif request.method == 'POST':
		try:	
			email = request.form['memberEmail']
			name = request.form['memberName']
			resAddress = request.form['memberAddress']
			allowed = request.form['memberAllowed']
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
		memberid = db.getNewMemberNumber()
		db.setUserDetails({
			'id':memberid,
			'resAddress':resAddress,
			'name':name,
			'email':email
		})
		address = getPaymentAddress(memberid)
		amount = db.getFee(tier)
		comment = "Bitcoin%20Australia%20Membership"
		uri = "bitcoin:%s?amount=%s&label=%s" % (address, amount, comment)
		
		db.addPaymentRequest(memberid,amount,'Membership 365 days, tier %s' % str(tier),int(time.time()))
		
		return '{"address":"%s","amount":"%s","uri":"%s","error":"none"}' % (address, amount, uri)
		
@app.route("/memberlist")
def memberlist():
	maxid = int(db.r.get('bitcoinAustralia:lastmemberid'))
	ret = ''
	for i in range(maxid):
		for stuff in ['name','email','paymentAddress']:
			ret += db.r.get('bitcoinAustralia:members:%d:%s' % (i+1, stuff)) + ' | '
		ret += '<br>'
	return ret	

## MAIN - RUN APP

if __name__ == "__main__":
	global db
	db = Database()
	app.run()
