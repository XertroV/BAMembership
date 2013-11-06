#!/usr/bin/python

## CONFIG

logfilename = './signupLog.log'
# replace this string with your own
pubKey = 'xpub661MyMwAqRbcEw72MGUKw2Yv1bnAg64pad8MhMuFHDUorGBTbCBk2GTRwLjxjbLkDfHFPwtDRrzJAmQdgoU7ZYEjEb3bs2BysnXKCaJa8h7'

## IMPORTS

from pycoin.wallet import Wallet
pubWallet = Wallet.from_wallet_key(pubKey)

from flask import Flask
from flask import request
app = Flask(__name__)

import logging
log_handler = logging.FileHandler(logfilename)
log_handler.setLevel(logging.WARNING)
app.logger.addHandler(log_handler)

from Crypto.Hash import SHA256

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

## HTML

# this will eventually be a customizable template
form_html = """
	<!--<script src="https://code.jquery.com/jquery-1.10.1.min.js"></script>-->
	<script src="http://127.0.0.1/jquery-1.10.1.min.js"></script>
	<div id="memberForm">
		<form role="form">
			<div class="form-group">
				<label for="memberName">Name</label>
				<input type="text" class="form-control" id="memberName" name="memberName">
			</div>
			<div class="form-group">
				<label for="memberEmail">Email Address</label>
				<input type="email" class="form-control" id="memberEmail" name="memberEmail">
			</div>
			<div class="form-group">
				<label for="memberAddress">Residential Address</label>
				<input type="textbox" class="form-control" id="memberAddress" name="memberAddress">
			</div>
			<div class="checkbox">
				<label><input type="checkbox" id="memberAllowed" name="memberAllowed"> I am a citizen or permenant resident of Australia, OR, an incorporated or registered legal entitiy according to the relevant Australian state or federal law.</label>
			</div>
			<button type="button" id="memberSubmit">Submit and get payment address</button>
		</form>
	</div>
	<div id="loadingPayment" style="display:none;">
		<h3>Loading<span id="loadingAnimation"></span></h3>
	</div>
	<div id="memberPaymentAddress" style="display:none;">
		<p>Please pay <span id="paymentAmount"></span> to:</p>
		<h3 id="addressToPay"></h3>
		<a id="bitcoinURI" src=""><img id="bitcoinQR" src=""></a>
		
		<p>Once you've sent payment there is nothing more you are required to do. Your membership will be manually processed and you will be emailed when it is complete.</p>
		<p>Kind Regards,<br>Bitcoin Australia</p>
		<!--- THIS IS DEBUG STUFF -->
		<p>
			<button type="button" id="paymentGoBack">Back</button>
		</p>
	</div>
	<div id="memberError" style="display:none;">
		<h3 class="error">Error: <span id="errorReport"></span></h3>
		<p>
			<button type="button" id="errorGoBack">Back</button>
		</p>
	</div>
	<script type="text/javascript">
	$("#memberSubmit").click(function(){
		$("#memberForm").slideUp(200);
		$("#loadingPayment").slideDown(200);
		$.ajax({
			"success":function(data, z, y){
				console.log(data);
				paymentDetails = JSON.parse(data);
				if(paymentDetails["error"] == "none"){
					$("#paymentAmount").html(paymentDetails["amount"]);
					$("#addressToPay").html(paymentDetails["address"]);
					$("#bitcoinURI").attr("href",paymentDetails["uri"]);
					$("#bitcoinQR").attr("src","https://chart.googleapis.com/chart?cht=qr&chs=300x300&chl="+encodeURIComponent(paymentDetails["uri"]));
					$("#loadingPayment").slideUp(200);
					$("#memberPaymentAddress").slideDown(200);
				}else{
					$("#errorReport").html(paymentDetails["error"]);
					$("#loadingPayment").slideUp(200);
					$("#memberError").slideDown(200);
				}
			},
			"type":"POST",
			"url":"membership",
			"data":{
				"memberEmail":$("#memberEmail").val(),
				"memberName":$("#memberName").val(),
				"memberAddress":$("#memberAddress").val(),
				"memberAllowed":$("#memberAllowed").is(":checked")
			},
		});
	});
	$("#errorGoBack").click(function(){
		$("#memberError").slideUp(200);
		$("#memberForm").slideDown(200);
	});
	$("#paymentGoBack").click(function(){
		$("#memberPaymentAddress").slideUp(200);
		$("#memberForm").slideDown(200);
	});
	
	loadingAnimCounter = 0;
	loadingAnimation = function(){
		if($("#loadingPayment").is(":visible")){
			loadingAnimCounter += 1;
			$("#loadingAnimation").html(["",".","..","..."][loadingAnimCounter % 4]);
		}
		setTimeout(loadingAnimation,500);
	}
	loadingAnimation();
	</script>
	"""
	
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
		return self.r.incr('bitcoinAustralia:lastmemberid')
	def setUserDetails(self,details): # details is a dict of keyvalue pairs to set - keep at arms length from db
		'''details should be a dict with keys 'resAddress','name','email','id' '''
		memberid = int(details['id'])
		resAddress = details['resAddress']
		name = details['name']
		email = details['email']
		
		self.r.set('%s:members:%d:resAddress' % (self.orgName, memberid), resAddress)
		self.r.set('%s:members:%d:name' % (self.orgName, memberid), name)
		self.r.set('%s:members:%d:email' % (self.orgName, memberid), email)
		self.r.set('%s:members:%d:paid' % (self.orgName, memberid), 'false')
		self.r.set('%s:members:%d:paymentAddress' % (self.orgName, memberid), getPaymentAddress(memberid))
		
		self.r.sadd('%s:uncertainMembersSet' % self.orgName, memberid)
		self.r.set('%s:members:emailHashToId:%s' % (self.orgName, sha256Hash(email)), memberid)
	def getIndividualFeeYearly(self):
		fee = self.r.get('%s:membership:feeIndividualYearly' % self.orgName)
		return '0.0012345'
	def setIndividualFeeYearly(self, fee):
		fee = str(fee)
		return self.r.set('%s:membership:feeIndividualYearly' % self.orgName, fee)

## ROUTES (PAGES)

@app.route("/membership", methods=["POST","GET"])
def stage1():
	if request.method == 'GET':
		global form_html
		return form_html
	elif request.method == 'POST':
		try:	
			email = request.form['memberEmail']
			name = request.form['memberName']
			resAddress = request.form['memberAddress']
			allowed = request.form['memberAllowed']
		except:
			return '{"error":"Submitted fields incorrect"}'
		if '' in [email, name, resAddress]:
			return '{"error":"One of name, email or address is blank"}'
		if db.checkEmailExists(email):
			return '{"error":"Email address already exists"}'
		if allowed != 'true':
			return '{"error":"You must be an Australian Resident or Citizen to join"}'
		memberid = db.getNewMemberNumber()
		db.setUserDetails({
			'id':memberid,
			'resAddress':resAddress,
			'name':name,
			'email':email
		})
		address = getPaymentAddress(memberid)
		amount = db.getIndividualFeeYearly()
		comment = "Bitcoin%20Australia%20Membership"
		uri = "bitcoin:%s?amount=%s&label=%s" % (address, amount, comment)
		return '{"address":"%s","amount":"%s","uri":"%s","error":"none"}' % (address, amount, uri)

## MAIN - RUN APP

if __name__ == "__main__":
	global db
	db = Database()
	app.run()
