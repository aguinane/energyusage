import os
import logging
import click
from metering import refresh_daily_stats
from metering import refresh_monthly_stats
from metering import refresh_daily_segments
from config import UPLOAD_FOLDER, DATABASE


@click.group()
def cli():
    pass


@cli.command()
def first_run():
    click.echo("Creating data directories")
    """ Set up files and folders on first run """
    if not os.path.exists("logs"):
        logging.info("Creating logs folder")
        os.makedirs("logs")

    if not os.path.exists("data"):
        logging.info("Creating data directory")
        os.makedirs("data")

    if not os.path.exists("data/uploads"):
        logging.info("Creating uploads directory")
        os.makedirs("data/uploads")

    if not os.path.exists(UPLOAD_FOLDER):
        logging.info("Creating upload folder")
        os.makedirs(UPLOAD_FOLDER)

    if not os.path.isfile(DATABASE):
        logging.info("Creating database")
        from energy import db

        db.create_all()

    click.echo("Done!")


@cli.command()
@click.option("--meterid", default=1, help="The meter ID")
def update_metering(meterid):
    click.echo(f"Refreshing daily stats for meter {meterid}")
    refresh_daily_stats(meterid)
    click.echo(f"Refreshing daily segments for meter {meterid}")
    # refresh_daily_segments(meterid)
    click.echo(f"Refreshing monthly stats for meter {meterid}")
    refresh_monthly_stats(meterid)
    click.echo("Done!")


if __name__ == "__main__":
    LOG_FORMAT = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"
    logging.basicConfig(level="INFO", format=LOG_FORMAT)
    cli()
