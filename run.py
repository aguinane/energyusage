import logging
import logging.config
import sys
import yaml
from energy import app
from energy.views import *

if __name__ == '__main__':

    if not os.path.exists('logs'):
        os.makedirs('logs')

    if not os.path.exists('logs'):
        logging.info('Creating logs folder')
        os.makedirs('logs')

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        logging.info('Creating upload folder')
        os.makedirs(app.config['UPLOAD_FOLDER'])

    if not os.path.isfile(app.config['DATABASE']):
        logging.info('Creating database')
        from energy import db
        db.create_all()

    with open('logging.yaml', 'rt') as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
    app.run(host='0.0.0.0', debug=True, threaded=False)

