import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    BOLUS_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessBolus:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.BOLUS in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessBolus: querying for last uploaded entry")
        last_upload = self.nightscout.last_uploaded_entry(BOLUS_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout bolus upload: %s" % last_upload_time)

        # TODO EXTENDED BOLUSES
        bolusCompletedEvents = []
        bolusEventsForId = {}
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if event.bolusid not in bolusEventsForId.keys():
                bolusEventsForId[event.bolusid] = {}

            bolusEventsForId[event.bolusid][type(event)] = event

            if type(event) == eventtypes.LidBolusCompleted:
                if last_upload_time and arrow.get(event.eventTimestamp) < last_upload_time:
                    if self.pretend:
                        logger.info("Skipping bolusCompletedEvent before last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                    continue

                bolusCompletedEvents.append(event)

        bolusCompletedEvents.sort(key=lambda e: e.eventTimestamp)



        ns_entries = []
        for bolusCompleted in bolusCompletedEvents:
            m = bolusEventsForId[bolusCompleted.bolusid]

            ns_entries.append(self.bolus_to_nsentry(
                bolusCompleted,
                bolusRequested1 = m.get(events.LidBolusRequestedMsg1),
                bolusRequested2 = m.get(events.LidBolusRequestedMsg2),
                bolusRequested3 = m.get(events.LidBolusRequestedMsg3),
            ))

        return ns_entries

    def write(self, ns_entries):
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload to Nightscout: %s" % entry)
            else:
                logger.info("Uploading to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry)
            count += 1

        return count


    def bolus_to_nsentry(self, bolusCompleted, bolusRequested1, bolusRequested2, bolusRequested3):
        suffixes = []
        if bolusRequested2 and bolusRequested2.useroverride == eventtypes.LidBolusRequestedMsg2.UseroverrideEnum.Yes:
            suffixes.append('(Override)')

        if bolusRequested2 and bolusRequested2.declinedcorrection == eventtypes.LidBolusRequestedMsg2.DeclinedcorrectionEnum.Yes:
            suffixes.append('(Declined Correction)')

        suffix = (' ' + (' '.join(suffixes))) if suffixes else ''

        event_ids = []
        for e in [bolusCompleted, bolusRequested1, bolusRequested2, bolusRequested3]:
            if e:
                event_ids.append(e.eventId)


        return NightscoutEntry.bolus(
            bolus = bolusCompleted.insulindelivered,
            carbs = bolusRequested1.carbamount if bolusRequested1 and bolusRequested1.carbamount>0 else None,
            created_at = bolusCompleted.eventTimestamp.format(),
            notes = (eventtypes.LidBolusRequestedMsg2.OptionsMap[bolusRequested2.optionsRaw] if bolusRequested2 else '') + suffix,
            bg = bolusRequested1.BG if bolusRequested1 and bolusRequested1.BG > 0 else None,
            pump_event_id = ",".join(event_ids)
        )
