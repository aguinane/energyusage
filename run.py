import logging
import logging.config
import yaml
import os
from energy import app


def setup_files():
    """ Set up files and folders on first run """
    if not os.path.exists('logs'):
        logging.info('Creating logs folder')
        os.makedirs('logs')

    if not os.path.exists('data'):
        logging.info('Creating data directory')
        os.makedirs('data')

    if not os.path.exists('data/uploads'):
        logging.info('Creating uploads directory')
        os.makedirs('data/uploads')

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        logging.info('Creating upload folder')
        os.makedirs(app.config['UPLOAD_FOLDER'])

    if not os.path.isfile(app.config['DATABASE']):
        logging.info('Creating database')
        from energy import db
        db.create_all()


if __name__ == '__main__':

    setup_files()
    with open('logging.yaml', 'rt') as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
    app.run(host='0.0.0.0', debug=True, threaded=False)

