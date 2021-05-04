import logging
import datetime
import arrow
import time

from .util import timeago
from .api.common import ApiException
from .sync.basal import (
    process_ciq_basal_events,
    add_csv_basal_events,
    ns_write_basal_events
)
from .sync.bolus import (
    process_bolus_events,
    ns_write_bolus_events
)
from .sync.iob import (
    process_iob_events,
    ns_write_iob_events
)
from .parser.tconnect import TConnectEntry

logger = logging.getLogger(__name__)

"""
Given a TConnectApi object and start/end range, performs a single
cycle of synchronizing data within the time range.
If pretend is true, then doesn't actually write data to Nightscout.
"""
def process_time_range(tconnect, nightscout, time_start, time_end, pretend):
    logger.info("Downloading t:connect ControlIQ data")
    try:
        ciqTherapyTimelineData = tconnect.controliq.therapy_timeline(time_start, time_end)
    except ApiException as e:
        # The ControlIQ API returns a 404 if the user did not have a ControlIQ enabled
        # device in the time range which is queried. Since it launched in early 2020,
        # ignore 404's before February.
        if e.status_code == 404 and time_start.date() < datetime.date(2020, 2, 1):
            logger.warn("Ignoring HTTP 404 for ControlIQ API request before Feb 2020")
            ciqTherapyTimelineData = None
        else:
            raise e

    logger.info("Downloading t:connect CSV data")
    csvdata = tconnect.ws2.therapy_timeline_csv(time_start, time_end)

    readingData = csvdata["readingData"]
    iobData = csvdata["iobData"]
    csvBasalData = csvdata["basalData"]
    bolusData = csvdata["bolusData"]

    if readingData and len(readingData) > 0:
        lastReading = readingData[-1]['EventDateTime'] if 'EventDateTime' in readingData[-1] else 0
        lastReading = TConnectEntry._datetime_parse(lastReading)
        logger.debug(readingData[-1])
        logger.info("Last CGM reading from t:connect: %s (%s)" % (lastReading, timeago(lastReading)))
    else:
        logger.warn("No last CGM reading is able to be determined")

    added = 0

    basalEvents = process_ciq_basal_events(ciqTherapyTimelineData)
    if csvBasalData:
        logger.debug("CSV basal data found: processing it")
        add_csv_basal_events(basalEvents, csvBasalData)
    else:
        logger.debug("No CSV basal data found")

    added += ns_write_basal_events(nightscout, basalEvents, pretend=pretend)

    bolusEvents = process_bolus_events(bolusData)
    added += ns_write_bolus_events(nightscout, bolusEvents, pretend=pretend)

    iobEvents = process_iob_events(iobData)
    added += ns_write_iob_events(nightscout, iobEvents, pretend=pretend)

    logger.info("Wrote %d events to Nightscout this process cycle")
    return added