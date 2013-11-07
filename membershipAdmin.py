#!/usr/bin/python

import sys
from pycoin.wallet import Wallet
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

## FUNCITONS - MAP TO COMMANDS

def printHelp():
	print """Commands: 
	exit, help, printAllMembers
	"""

def endProgram():
	sys.exit()

def getAllMembers():
	lastMember = int(r.get('bitcoinAustralia:lastmemberid'))
	toRet = []
	for i in range(lastMember):
		toAdd = []
		for info in ['name','email','resAddress','paymentAddress']:
			toAdd += [r.get('bitcoinAustralia:members:%d:%s' % (i+1, info))]
		toRet += [toAdd]
	return toRet
	
def printAllMembers():
	allMembers = getAllMembers()
	for row in allMembers:
		for thing in row:
			print thing,
		print
		


## MAIN - RUN APP

functionMap = {
	"printAllMembers":printAllMembers,
	"help":printHelp,
	"exit":endProgram,
}

if __name__ == "__main__":
	while True:
		command = raw_input('$> ')
		if command not in functionMap.keys():
			print 'Error: command nonexistant.'
		else:
			functionMap[command]()
	
	
