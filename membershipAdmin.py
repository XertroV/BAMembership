#!/usr/bin/python



## MAIN - RUN APP

if __name__ == "__main__":
	import redis
	r = redis.StrictRedis(host='localhost', port=6379, db=0)
	lastMember = int(r.get('bitcoinAustralia:lastmemberid'))
	for i in range(lastMember):
		for info in ['name','email','resAddress','paymentAddress']:
			print r.get('bitcoinAustralia:members:%d:%s' % (i+1, info)),
		print ''
