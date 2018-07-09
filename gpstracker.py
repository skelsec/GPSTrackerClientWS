#!/usr/bin/env python3

import json
import logging
import logging.config
import platform
import asyncio
import ssl
import datetime
import pytz
import glob
import tempfile
import os

from constants import tracker_config, logformat

from dateutil.parser import parse
import websockets
import aiohttp
from aiogps import gps, client



# https://github.com/aaugustin/websockets

logging.getLogger("aiogps").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

CLIENT_VERSION = '0.0.1'

class UniversalEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			return obj.isoformat()
		
		return obj

class GPSTrackerRegister:
	def __init__(self):
		self.bootstrap_url = None

		self.server_url = None
		self.ws_uri = '/tracker'

		self.client_id = None
		self.bootstrap_code = None
		self.registration_email = None

	@staticmethod
	def from_config(cf):
		"""
		Loads config file (cf) and creates GPSTracker object
		"""
		with open(cf) as f:
			data = json.load(f)
		t = GPSTrackerRegister()
		t.bootstrap_url =data['BOOTSTRAP']['BOOTSTRAP_URL']
		t.bootstrap_code = data['BOOTSTRAP']['BOOTSTRAP_CODE']
		t.bootstrap_email = data['BOOTSTRAP']['BOOTSTRAP_EMAIL']

		t.client_id = data['UPLOADER']['TRACKER_NAME']
		t.server_url = data['UPLOADER']['UPLOAD_URL']
		t.ws_uri = data['UPLOADER']['WS_URI']

		return t

	async def setup(self):
		pass
		#setup logging

	async def start(self):
		logging.info('Starting bootstrap')
		try:
			async with aiohttp.ClientSession() as session:
				req_data = {}
				req_data['bootstrap_code'] = self.bootstrap_code
				req_data['email'] = self.bootstrap_email

				async with session.put(self.bootstrap_url, json = req_data) as resp:
					resp = await resp.json()

			if resp['status'] != 'ok':
				logging.error('Server returned with error! Data: %s' % json.dumps(resp))
				return

			logging.debug('Recieved necessray data! Generating config file')
			tconf = tracker_config
			logging.debug('Writing certfile')
			with open(tconf['client_cert'], 'wb') as f:
				f.write(resp['data']['cert'].encode())

			logging.debug('Writing keyfile')
			with open(tconf['client_key'], 'wb') as f:
				f.write(resp['data']['key'].encode())

			logging.debug('Writing config file')
			tconf['server'] = self.server_url
			tconf['clinet_id'] = self.client_id
			tconf['ws_uri'] = self.ws_uri
			with open('config.json','w') as f:
				json.dump(tconf, f)

			logging.info('Done setting up the tracker!')
		
		except:
			logging.exception('Failed bootstrap!')

class GPSTrackerData:
	def __init__(self, client_info, pos):
		self.client_info = client_info
		self.position = pos

	def to_dict(self):
		t = {}
		t['info'] = self.client_info.to_dict()
		t['position'] = self.position.to_dict()
		return t

class GPSPosition:
	def __init__(self, gpsdata):

		self.lat	= gpsdata.get('lat',0)
		self.lon	= gpsdata.get('lon',0)
		self.alt	= gpsdata.get('alt',0)
		self.speed		= gpsdata.get('speed',0)
		self.time	= parse(gpsdata.get('time','1990-01-01')).replace(tzinfo=pytz.UTC)
		self.ept		= gpsdata.get('ept',0)
		self.epx		= gpsdata.get('epx',0)
		self.epy		= gpsdata.get('epy',0)
		self.epv		= gpsdata.get('epv',0)
		self.track		= gpsdata.get('track',0)
		self.climb		= gpsdata.get('climb',0)
		self.eps		= gpsdata.get('eps',0)
		self.mode		= gpsdata['mode']

	def to_dict(self):
		t = {}
		t['lat'] = self.lat
		t['lon'] = self.lon
		t['alt'] = self.alt
		t['speed'] = self.speed
		t['time'] = self.time
		t['ept'] = self.ept
		t['epx'] = self.epx
		t['epy'] = self.epy
		t['epv'] = self.epv
		t['track'] = self.track
		t['climb'] = self.climb
		t['eps'] = self.eps
		t['mode'] = self.mode
		return t


class GPSTrackerClient:
	def __init__(self, cid):
		self.version = CLIENT_VERSION
		self.platform = ','.join(platform.uname())
		self.id = cid

	def to_dict(self):
		t = {}
		t['version'] = self.version
		t['platform'] = self.platform
		t['id'] = self.id
		return t

class GPSTrackerBootstrap:
	def __init__(self):
		self.a = None

class GPSTracker:
	def __init__(self):
		self.client_info = None
		self.ws_uri = None
		self.ws_context = None
		self.ws = None

		self.datafile = None
		self.backupdir = None
		self.gps = None

	@staticmethod
	def from_config(cf):
		"""
		Loads config file (cf) and creates GPSTracker object
		"""
		with open(cf) as f:
			data = json.load(f)
		t = GPSTracker()
		t.client_info = GPSTrackerClient(data['server'])
		m = data['server'].find('://')
		if m != -1:
			server = data['server'][m+3:]
		else:
			server = data['server']
		server = server.replace('/','')
		print('wss://%s' % (server + data['ws_uri']))
		
		t.ws_uri = 'wss://%s' % (server + data['ws_uri'])
		
		cafile = None
		if 'cafile' in data and os.path.isfile(data['cafile']):
			cafile = data['cafile']

		context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
		context.load_cert_chain(certfile=data['client_cert'], keyfile=data['client_key'])
		t.ws_context = context
		t.datafile = data['datafile']
		t.backupdir = data['backupdir']

		return t

	async def setup(self):
		logging.config.dictConfig(logformat)
		self.ws = await websockets.connect(self.ws_uri, ssl= self.ws_context)
		self.gps = gps.GPS()
		await self.gps.connect()
		await self.gps.stream(gps.WATCH_ENABLE|gps.WATCH_NEWSTYLE)

	async def backuptask(self):
		await asyncio.sleep(10)
		while True:
			if self.ws:
				for filename in glob.glob(self.backupdir + '*'):
					with open(filename, 'rb') as f:
						data = json.load(f)
					try:
						await self.ws.send(json.dumps(data))
						os.remove(filename)
					except:
						logging.exception('backup re-send failed!')
						self.ws = None
			await asyncio.sleep(5)			

	async def keep_online(self):
		await asyncio.sleep(10)
		while True:
			if not self.ws:
				logging.debug('Reconnecting')
				try:
					self.ws = await websockets.connect(self.ws_uri, ssl= self.ws_context)
				except:
					pass
			await asyncio.sleep(10)

	async def start(self):
		loop = asyncio.get_event_loop()
		asyncio.ensure_future(self.keep_online(), loop=loop)
		asyncio.ensure_future(self.backuptask(), loop=loop)
		while True:
			try:
				#setup
				await self.setup()

				#recieve data from gps				
				async for data in self.gps:
					if data['class'] != 'TPV':
						continue
					
					jdata = json.dumps(GPSTrackerData(self.client_info ,GPSPosition(data)).to_dict(), cls=UniversalEncoder)

					try:
						with open(self.datafile,'wb') as f:
							f.write(jdata.encode() + b'\r\n')
					except:
						logging.exception('Failed to write file!')
						pass
					
					if self.ws:
						try:
							await self.ws.send(jdata)
						except:
							logging.exception('Send failed!')
							try:	
								self.ws.close()
							except:
								pass
							self.ws = None
					else:
						with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=self.backupdir) as temp:
							temp.write(jdata.encode() + b'\r\n')
							temp.flush()

			except Exception as e:
				logging.exception('GPSTracker main loop exception!')
				await asyncio.sleep(10)
				pass
		
if __name__ == '__main__':
	import argparse

	parser = argparse.ArgumentParser(description='GPS Tracker client')
	subparsers = parser.add_subparsers(help = 'commands')
	subparsers.required = True
	subparsers.dest = 'command'
	
	track_group = subparsers.add_parser('track', help='start tracking')
	track_group.add_argument('-c', '--config-file', default='config.json', help='config file')
	
	setup_group = subparsers.add_parser('setup', help='Performs setup to server')
	setup_group.add_argument('-c', '--config-file', help='config file', required = True)

	args = parser.parse_args()

	if args.command == 'track':
		logging.info('Starting tracking')
		tracker = GPSTracker.from_config(args.config_file)
		asyncio.get_event_loop().run_until_complete(tracker.start())

	elif args.command == 'setup':
		logging.basicConfig(level=logging.DEBUG)
		reg = GPSTrackerRegister.from_config(args.config_file)
		asyncio.get_event_loop().run_until_complete(reg.start())
