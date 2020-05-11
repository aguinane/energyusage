"""
    energy.api
    ~~~~~~~~~
    Define the energy site API
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
from metering import get_data_range
from . import db
from .models import get_meter_api_key


api = Blueprint("api", __name__)


@api.route("/api/v1.0/data-range", methods=["GET"])
def data_range():
    """ Get the available data range of a meter """
    try:
        meter_id = int(request.headers["X-meterid"])
    except KeyError:
        try:
            meter_id = int(request.values["meterid"])
        except KeyError:
            msg = "ERROR: Must specify a HTTP header of meterid "
            return msg, 400
    first_record, last_record = get_data_range(meter_id)

    return jsonify({"first_record": first_record, "last_record": last_record})
