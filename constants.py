tracker_config = {
	"server": "",
	"ws_uri" : "",
	"datafile": "positions/pos.gps",
	"backupdir": "backup/",
	"client_cert": "certs/client_cert",
	"client_key": "certs/client_key",
	"cafile": "certs/ca"
}

logformat = {
	'version': 1,
	'disable_existing_loggers': False,  # this fixes the problem
	'formatters': {
		'standard': {
			'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
		},
	},
	'handlers': {
		'default': {
			'level':'DEBUG',
			'formatter': 'standard',
			'class':'logging.StreamHandler',
		},
		'file': {
			'class': 'logging.handlers.RotatingFileHandler',
			'level': 'DEBUG',
			'formatter': 'standard',
			'filename': 'log/gpstracker.log',
			'mode': 'a',
			'maxBytes': 10485760,
			'backupCount': 5,
		},
	},
	'loggers': {
		'': {
			'handlers': ['default','file'],
			'level': 'DEBUG',
			'propagate': True
		}
	}
}